"""Historial de Analisis — filtros y exportación de las líneas de análisis.

Consulta la tabla transaccional `ticket_analysis` (1 línea por pregunta/criterio)
tal como está en el banco, sin agregar por evaluación: el propósito de esta
página es exportar la información con exactamente las columnas de
`config.ANALISE_COLUMNS` (id, id_number, id_manager, id_analista,
id_analista_quality, question_id, fecha_analisis, analista_quality,
ticketnumber, idioma, region, manager, nombre_del_tecnico, pilar, pergunta,
nota, comentario, status_feedback).

El período consultado está limitado a MAX_MESES_PERIODO meses: la tabla tiene
mucho volumen, así que una consulta sin límite de fecha sería lenta/pesada —
tanto en pantalla como en la exportación. Los filtros se aplican en el SQL
(no en pandas), para que el banco devuelva solo lo necesario.

Manager y Técnico son listas desplegables (no texto libre) — las opciones
vienen de un SELECT DISTINCT sobre toda la tabla, cacheado 5 min. Status usa
los tres valores reales de `status_feedback` (siempre en inglés, ver
config.py) directamente como opción — sin traducción, misma convención ya
usada para el nombre de los pilares.
"""

import io
from datetime import timedelta

import pandas as pd
import streamlit as st

from core.config import (
    ANALISE_COLUMNS,
    FECHA_ANALISIS_FORMATO_PY,
    FECHA_ANALISIS_FORMATO_SQL_PY,
    MAX_FILAS_CONSULTA,
    MAX_MESES_PERIODO,
    STATUS_FEEDBACK_CANCELADO,
    STATUS_FEEDBACK_CONCLUIDO,
    STATUS_FEEDBACK_PENDIENTE,
    TABLES,
    sql_fecha_analisis,
)
from core.db import run_query_safe
from core.i18n import t
from core.ui import mostrar_error_db

st.title(t("hist_title"), anchor=False)
st.caption(t("hist_caption"))

T_ANALISE = TABLES["ticket_analysis"]


def _limite_inferior(data_fim) -> pd.Timestamp:
    """Fecha más antigua permitida para un período que termina en `data_fim`."""
    return pd.Timestamp(data_fim) - pd.DateOffset(months=MAX_MESES_PERIODO)


@st.cache_data(ttl=300, show_spinner=False)
def _opciones_manager():
    df, _err = run_query_safe(
        f"SELECT DISTINCT manager FROM {T_ANALISE} WHERE manager IS NOT NULL AND manager != '' ORDER BY manager",
        columns=["manager"],
    )
    return df["manager"].tolist()


@st.cache_data(ttl=300, show_spinner=False)
def _opciones_tecnico(manager: str | None):
    if manager:
        df, _err = run_query_safe(
            f"""
            SELECT DISTINCT nombre_del_tecnico FROM {T_ANALISE}
            WHERE manager = :manager AND nombre_del_tecnico IS NOT NULL AND nombre_del_tecnico != ''
            ORDER BY nombre_del_tecnico
            """,
            {"manager": manager},
            columns=["nombre_del_tecnico"],
        )
    else:
        df, _err = run_query_safe(
            f"SELECT DISTINCT nombre_del_tecnico FROM {T_ANALISE} WHERE nombre_del_tecnico IS NOT NULL AND nombre_del_tecnico != '' ORDER BY nombre_del_tecnico",
            columns=["nombre_del_tecnico"],
        )
    return df["nombre_del_tecnico"].tolist()


# Los filtros se muestran primero (no dependen del banco, salvo las opciones
# de los desplegables); la consulta principal se intenta después y, si falla,
# solo se avisa sin bloquear la página.
st.subheader(t("filtros_subheader"), anchor=False)
st.caption(t("periodo_limite_caption", meses=MAX_MESES_PERIODO))

hoje = pd.Timestamp.today().normalize().date()
periodo_default = (_limite_inferior(hoje).date(), hoje)

c1, c2, c3, c4 = st.columns(4)
periodo = c1.date_input(
    t("field_periodo"),
    value=periodo_default,
    max_value=hoje,
    help=t("periodo_help", meses=MAX_MESES_PERIODO),
)

manager_opts = [t("opt_todos")] + _opciones_manager()
manager_filtro = c2.selectbox(t("field_manager_filtro"), manager_opts)

# Cascata: as opções de Técnico dependem do Manager escolhido — mesma chave
# variável usada no Dashboard, pra resetar o Técnico quando o Manager muda em
# vez de tentar validar contra uma lista de opções que já mudou.
manager_para_tecnico = manager_filtro if manager_filtro != t("opt_todos") else None
tecnico_opts = [t("opt_todos")] + _opciones_tecnico(manager_para_tecnico)
tecnico_filtro = c3.selectbox(
    t("field_tecnico_req").replace(" *", ""), tecnico_opts, key=f"hist_tecnico_{manager_filtro}"
)

status_opts = [t("opt_todos"), STATUS_FEEDBACK_PENDIENTE, STATUS_FEEDBACK_CONCLUIDO, STATUS_FEEDBACK_CANCELADO]
status_filtro = c4.selectbox(t("field_status_filtro"), status_opts)

c5, c6 = st.columns(2)
ticket_filtro = c5.text_input(t("field_ticket").replace(" *", ""))
idq_filtro = c6.text_input(t("field_idq"))

# `date_input` con rango devuelve 1 sola fecha mientras el usuario no eligió la
# segunda: en ese caso se espera, en vez de consultar un período incompleto.
if not isinstance(periodo, (list, tuple)) or len(periodo) != 2:
    st.info(t("periodo_incompleto_aviso"))
    st.stop()

data_ini, data_fim = periodo

if data_ini > data_fim:
    data_ini, data_fim = data_fim, data_ini

# Recorte del período al máximo permitido. Se hace acá (y no solo en el
# date_input) porque el widget no puede limitar el largo del rango, solo sus
# extremos absolutos.
limite = _limite_inferior(data_fim).date()
if data_ini < limite:
    data_ini = limite
    st.warning(
        t(
            "periodo_limitado_aviso",
            meses=MAX_MESES_PERIODO,
            desde=data_ini.strftime("%d/%m/%Y"),
            hasta=data_fim.strftime("%d/%m/%Y"),
        )
    )

# `fecha_analisis` es texto ('DD/MM/YYYY HH:MM') — comparar la columna cruda
# con una fecha sería una comparación lexicográfica incorrecta. Se reordena
# con sql_fecha_analisis() antes de comparar, y los parámetros de fecha se
# formatean igual ('YYYY-MM-DD HH:MM') para que la comparación de texto sea
# equivalente a una comparación cronológica. El límite superior es exclusivo
# sobre el día siguiente — con BETWEEN se perderían los registros del último
# día con hora distinta de 00:00.
FECHA_EXPR = sql_fecha_analisis()
condiciones = [f"{FECHA_EXPR} >= :data_ini", f"{FECHA_EXPR} < :data_fim"]
params = {
    "data_ini": data_ini.strftime(FECHA_ANALISIS_FORMATO_SQL_PY),
    "data_fim": (data_fim + timedelta(days=1)).strftime(FECHA_ANALISIS_FORMATO_SQL_PY),
    "limite": MAX_FILAS_CONSULTA + 1,
}

# Manager/Técnico vienen de un desplegable (valor exacto de la base) — se
# comparan con igualdad. TicketNumber/IDQ siguen siendo texto libre — LIKE.
if manager_filtro != t("opt_todos"):
    condiciones.append("manager = :manager")
    params["manager"] = manager_filtro
if tecnico_filtro != t("opt_todos"):
    condiciones.append("nombre_del_tecnico = :nombre_del_tecnico")
    params["nombre_del_tecnico"] = tecnico_filtro
if status_filtro != t("opt_todos"):
    condiciones.append("status_feedback = :status_feedback")
    params["status_feedback"] = status_filtro

for columna, valor in [
    ("ticketnumber", ticket_filtro),
    ("id", idq_filtro),
]:
    if valor and valor.strip():
        condiciones.append(f"{columna} LIKE :{columna}")
        params[columna] = f"%{valor.strip()}%"

# El SELECT trae exactamente las columnas de ANALISE_COLUMNS — son las mismas
# que la app escribe y las que se exportan, sin agregar ni renombrar nada.
SQL_HISTORIAL = f"""
    SELECT {", ".join(ANALISE_COLUMNS)}
    FROM {T_ANALISE}
    WHERE {" AND ".join(condiciones)}
    ORDER BY {FECHA_EXPR} DESC
    LIMIT :limite
"""


@st.cache_data(ttl=300, show_spinner=False)
def cargar_historial(sql: str, params: dict):
    """Consulta el DW con caché de 5 min — evita re-consultar en cada rerun."""
    return run_query_safe(sql, params, columns=ANALISE_COLUMNS)


with st.spinner(t("consultando_spinner")):
    dados, db_error = cargar_historial(SQL_HISTORIAL, params)

if db_error:
    # No cachear un fallo: si la conexión (VPN/firewall) vuelve, la página debe
    # reintentar en el próximo rerun en vez de esperar el TTL de 5 minutos.
    cargar_historial.clear()

mostrar_error_db(db_error)

truncado = len(dados) > MAX_FILAS_CONSULTA
if truncado:
    dados = dados.head(MAX_FILAS_CONSULTA)
    st.warning(t("resultado_truncado_aviso", filas=f"{MAX_FILAS_CONSULTA:,}".replace(",", ".")))

# `fecha_analisis` vuelve del DW como texto ('DD/MM/YYYY HH:MM'). Se convierte
# a datetime real acá para que el orden en pantalla sea cronológico y no
# lexicográfico sobre el string.
if not dados.empty:
    dados["fecha_analisis"] = pd.to_datetime(
        dados["fecha_analisis"], format=FECHA_ANALISIS_FORMATO_PY, errors="coerce"
    )

st.subheader(t("resultado_subheader", n=len(dados)), anchor=False)
st.dataframe(dados, use_container_width=True, hide_index=True)

st.divider()
st.subheader(t("exportacion_subheader"), anchor=False)
st.caption(
    t(
        "exportacion_caption",
        desde=data_ini.strftime("%d/%m/%Y"),
        hasta=data_fim.strftime("%d/%m/%Y"),
        lineas=len(dados),
    )
)


@st.cache_data(show_spinner=False)
def a_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


@st.cache_data(show_spinner=False)
def a_excel(df: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


sufijo = f"{data_ini:%Y%m%d}_{data_fim:%Y%m%d}"

col_csv, col_xlsx = st.columns(2)
col_csv.download_button(
    t("btn_export_csv"),
    data=a_csv(dados),
    file_name=f"historial_analisis_{sufijo}.csv",
    mime="text/csv",
    use_container_width=True,
    disabled=dados.empty,
)
col_xlsx.download_button(
    t("btn_export_excel"),
    data=a_excel(dados, "Historial"),
    file_name=f"historial_analisis_{sufijo}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
    disabled=dados.empty,
)
