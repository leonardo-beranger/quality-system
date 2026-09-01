"""Login de la app — usa la tabla `quality_agent` como base de usuarios.

`quality_agent` ganó las columnas `password_hash`, `role` ('admin' | 'viewer')
y `last_login`. El login es por email; solo quien tiene `password_hash`
definido y `status = 'activate'` puede entrar.

Compatibilidad con contraseñas pre-cargadas en texto plano (p. ej. '1234',
puestas a mano en el DW mientras no existía este módulo): si el hash guardado
no tiene forma de hash bcrypt, se compara como texto plano y — si coincide —
se reemplaza por un hash bcrypt real en el mismo momento (upgrade perezoso,
sin necesitar una migración aparte).

La sesión sobrevive a un F5/recarga del navegador: `st.session_state` se
reinicia en cada conexión nueva del navegador (eso es justamente lo que pasa
al recargar), así que el login se respalda además en una cookie firmada
(HMAC) que identifica al usuario. Al recargar, si la cookie es válida y no
expiró, la sesión se restaura sin pedir credenciales de nuevo.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import bcrypt
import extra_streamlit_components as stx
import streamlit as st
import streamlit.components.v1 as components

from .config import TABLES
from .db import run_query_safe, run_statement_safe
from .i18n import t

TABLE = TABLES["quality_agent"]
SESSION_KEY = "usuario"
COOKIE_NAME = "fqm_session"
COOKIE_TTL_SEGUNDOS = 12 * 60 * 60  # 12 horas


@st.cache_resource(show_spinner=False)
def _clave_secreta() -> bytes:
    """Clave de firma de la cookie de sesión — se genera una vez por proceso del servidor.

    No se persiste en disco a propósito: si el servidor Streamlit reinicia,
    las cookies emitidas antes quedan inválidas y el usuario simplemente
    tiene que loguearse de nuevo. Es una compensación aceptable a cambio de
    no tener que gestionar un secreto adicional en `db_config.json`.
    """
    return secrets.token_bytes(32)


def _cookie_manager() -> stx.CookieManager:
    # Sin @st.cache_resource: es un wrapper liviano sobre un componente de
    # Streamlit y debe recrearse en cada rerun (patrón estándar de la librería).
    # Solo se usa para LEER la cookie (`.get()`) — funciona de forma
    # confiable. Para ESCRIBIR (login) o BORRAR (logout) se usa
    # `_escrever_cookie`/`_apagar_cookie` abajo: el round-trip async de
    # `.set()`/`.delete()` de esta librería demostró no confirmar la
    # escritura a tiempo del rerun (probado a mano: la cookie no cambiaba).
    return stx.CookieManager(key="fqm_cookie_manager")


def _escrever_cookie_y_recargar(valor: str, ttl_segundos: int) -> None:
    """Escribe la cookie de sesión y recarga la página — todo desde el browser.

    `CookieManager.set()` (y `st.rerun()` inmediatamente después) no garantiza
    que el navegador reciba/ejecute la escritura antes de que Streamlit corte
    el ciclo para el rerun (confirmado a mano: la cookie no llegaba a
    escribirse). Acá el propio `<script>` hace `document.cookie = ...` y
    recién DESPUÉS dispara `window.top.location.reload()` — la recarga sólo
    ocurre una vez que la cookie ya está escrita, sin depender de ningún
    timing del lado de Python.
    """
    expira = (datetime.now(timezone.utc) + timedelta(seconds=ttl_segundos)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    valor_codificado = urllib.parse.quote(valor)
    components.html(
        f"<script>"
        f"document.cookie = '{COOKIE_NAME}={valor_codificado}; expires={expira}; path=/';"
        f"window.top.location.reload();"
        f"</script>",
        height=0,
    )
    st.stop()


def _apagar_cookie_y_recargar() -> None:
    components.html(
        f"<script>"
        f"document.cookie = '{COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/;';"
        f"window.top.location.reload();"
        f"</script>",
        height=0,
    )
    st.stop()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _es_hash_bcrypt(valor: str) -> bool:
    return valor.startswith(("$2a$", "$2b$", "$2y$"))


def _verificar_password(password: str, guardado: str) -> bool:
    if _es_hash_bcrypt(guardado):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), guardado.encode("utf-8"))
        except ValueError:
            return False
    # Contraseña pre-cargada en texto plano (aún no migrada a bcrypt).
    return password == guardado


def _crear_token(usuario_id: int) -> str:
    expira = int(time.time()) + COOKIE_TTL_SEGUNDOS
    payload = f"{usuario_id}:{expira}"
    firma = hmac.new(_clave_secreta(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{firma}"


def _validar_token(token: str) -> int | None:
    """Verifica firma y vencimiento del token de la cookie. Devuelve el id de usuario o None."""
    if not token or "." not in token:
        return None
    payload, firma = token.rsplit(".", 1)
    esperada = hmac.new(_clave_secreta(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, esperada):
        return None
    try:
        usuario_id_str, expira_str = payload.split(":")
        usuario_id, expira = int(usuario_id_str), int(expira_str)
    except ValueError:
        return None
    if time.time() > expira:
        return None
    return usuario_id


def usuario_actual() -> dict | None:
    return st.session_state.get(SESSION_KEY)


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)
    _apagar_cookie_y_recargar()


def _cargar_usuario_por_id(usuario_id: int) -> dict | None:
    """Recarga los datos del usuario desde la DB — nunca confía solo en el contenido de la cookie."""
    df, db_error = run_query_safe(
        f"SELECT id, name, email, role FROM {TABLE} WHERE id = :id AND status = 'activate'",
        {"id": usuario_id},
        columns=["id", "name", "email", "role"],
    )
    if db_error or df.empty:
        return None
    fila = df.iloc[0]
    return {"id": int(fila["id"]), "name": fila["name"], "email": fila["email"], "role": fila["role"] or "viewer"}


def _autenticar(email: str, password: str) -> tuple[dict | None, str | None]:
    """Valida email/contraseña contra `quality_agent`. Devuelve (usuario, error)."""
    df, db_error = run_query_safe(
        f"""
        SELECT id, name, email, password_hash, role
        FROM {TABLE}
        WHERE lower(email) = lower(:email) AND status = 'activate'
        """,
        {"email": email},
        columns=["id", "name", "email", "password_hash", "role"],
    )
    if db_error:
        return None, t("db_connection_error", error=db_error)

    if df.empty:
        return None, t("login_error_credenciales")

    fila = df.iloc[0]
    guardado = fila["password_hash"]
    if not guardado:
        return None, t("login_error_sin_password")

    if not _verificar_password(password, guardado):
        return None, t("login_error_credenciales")

    # Upgrade perezoso: si el hash guardado era texto plano, se reemplaza por
    # un hash bcrypt real ahora que sabemos que la contraseña es correcta.
    if not _es_hash_bcrypt(guardado):
        run_statement_safe(
            f"UPDATE {TABLE} SET password_hash = :hash WHERE id = :id",
            {"hash": hash_password(password), "id": int(fila["id"])},
        )

    run_statement_safe(
        f"UPDATE {TABLE} SET last_login = :ahora WHERE id = :id",
        {"ahora": datetime.now(), "id": int(fila["id"])},
    )

    usuario = {
        "id": int(fila["id"]),
        "name": fila["name"],
        "email": fila["email"],
        "role": fila["role"] or "viewer",
    }
    return usuario, None


def render_login() -> bool:
    """Muestra el formulario de login si aún no hay sesión. Devuelve True si está logueado."""
    if usuario_actual():
        return True

    cookies = _cookie_manager()

    # La cookie tarda un rerun en estar disponible (el componente recién
    # montado manda su valor de forma asíncrona) — este intento silencioso
    # de restaurar sesión no bloquea el formulario de abajo si todavía no
    # llegó, simplemente no encuentra nada esa primera vez.
    token = cookies.get(COOKIE_NAME)
    if token:
        usuario_id = _validar_token(token)
        if usuario_id:
            usuario = _cargar_usuario_por_id(usuario_id)
            if usuario:
                st.session_state[SESSION_KEY] = usuario
                return True

    st.title(t("login_title"), anchor=False)
    st.caption(t("login_caption"))

    with st.form("form_login"):
        email = st.text_input(t("login_field_email"))
        password = st.text_input(t("login_field_password"), type="password")
        entrar = st.form_submit_button(t("login_btn_entrar"), type="primary")

    if entrar:
        if not email or not password:
            st.error(t("login_error_campos_vacios"))
        else:
            usuario, error = _autenticar(email.strip(), password)
            if error:
                st.error(error)
            else:
                st.session_state[SESSION_KEY] = usuario
                _escrever_cookie_y_recargar(_crear_token(usuario["id"]), COOKIE_TTL_SEGUNDOS)

    return False
