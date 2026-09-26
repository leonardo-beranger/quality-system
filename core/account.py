"""Senha do usuário — troca pelo próprio usuário e redefinição pelo admin.

Fica separado de `auth.py` porque grava rastro de auditoria em `activity_log`
(via `log.py`, que já importa `auth.py`): unir os dois criaria um import
circular. Nunca grava a senha em texto no log — só o fato de ter sido alterada.

As funções devolvem a CHAVE i18n do erro (ou None se deu certo), para a página
traduzir a mensagem no idioma escolhido.
"""

from __future__ import annotations

from .auth import _verificar_password, hash_password
from .config import TABLES, senha_padrao
from .db import run_query_safe, run_transaction_safe
from .log import log_update

TABLE = TABLES["quality_agent"]

MIN_PASSWORD_LEN = 8

# Marcadores gravados no log no lugar dos valores reais (nunca a senha nem o hash).
_LOG_ANTES = "(anterior)"
_LOG_DEPOIS = "(alterada)"


def _hash_e_nome(usuario_id: int) -> tuple[str | None, str | None, str | None]:
    """(hash guardado, nome, erro de banco) do usuário ativo `usuario_id`."""
    df, db_error = run_query_safe(
        f"SELECT password_hash, name FROM {TABLE} WHERE id = :id AND status = 'activate'",
        {"id": usuario_id},
        columns=["password_hash", "name"],
    )
    if db_error:
        return None, None, db_error
    if df.empty:
        return None, None, None
    fila = df.iloc[0]
    return (fila["password_hash"] or ""), fila["name"], None


def usa_senha_padrao(usuario_id: int) -> bool:
    """True se o usuário ainda usa a senha padrão do ano (`quality_{ano}`)."""
    guardado, _nome, db_error = _hash_e_nome(usuario_id)
    if db_error or not guardado:
        return False
    return _verificar_password(senha_padrao(), guardado)


def alterar_senha_propria(usuario_id: int, atual: str, nova: str, confirmacao: str) -> str | None:
    """Troca a senha do próprio usuário. Devolve a chave i18n do erro, ou None se deu certo."""
    if nova != confirmacao:
        return "pwd_error_no_coincide"
    if len(nova) < MIN_PASSWORD_LEN:
        return "pwd_error_curta"
    if nova == senha_padrao():
        return "pwd_error_padrao"

    guardado, nome, db_error = _hash_e_nome(usuario_id)
    if db_error:
        return "pwd_error_db"
    if not guardado or not _verificar_password(atual, guardado):
        return "pwd_error_atual"
    if nova == atual:
        return "pwd_error_igual"

    operaciones = [
        (f"UPDATE {TABLE} SET password_hash = :hash WHERE id = :id", {"hash": hash_password(nova), "id": usuario_id})
    ]
    operaciones += log_update("quality_agent", nome, {"password": _LOG_ANTES}, {"password": _LOG_DEPOIS})
    return "pwd_error_db" if run_transaction_safe(operaciones) else None


def redefinir_senha_padrao(nome_usuario: str) -> str | None:
    """Admin: volta a senha de `nome_usuario` para a padrão do ano. Devolve o erro de banco, ou None."""
    operaciones = [
        (f"UPDATE {TABLE} SET password_hash = :hash WHERE name = :nome", {"hash": hash_password(senha_padrao()), "nome": nome_usuario})
    ]
    operaciones += log_update("quality_agent", nome_usuario, {"password": _LOG_ANTES}, {"password": _LOG_DEPOIS})
    return run_transaction_safe(operaciones)
