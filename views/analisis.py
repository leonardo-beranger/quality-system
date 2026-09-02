"""Analisis — Registrar, Editar, Aplicar Feedback, Cancelar y Eliminar evaluaciones en una sola página con pestañas.

Equivalente a los formularios "Hacer análisis" (registro), "Cargar para Editar",
"Cancelar" y "Eliminar" de la planilha original, agrupados en pestañas.

Ciclo de vida de `status_feedback` (valores sempre em inglês, ver config.py):
Registrar cria a avaliação como `Pending` (início do processo); a aba
"Aplicar Feedback" marca como `Applied` quando o feedback foi de fato
repassado ao técnico (fim do processo); Cancelar marca como `Cancelled`
(reversível, fora do ciclo normal).

Las columnas de `ticket_analysis` son las declaradas en config.ANALISE_COLUMNS.
El código de la evaluación mostrado como "IDQ" en la interfaz es la columna
`id` (texto completo, p. ej. 'IDQ12737'); `id_number` es solo la parte
numérica (p. ej. '12737'), sin el prefijo. El criterio es `pergunta` y el
técnico es `nombre_del_tecnico`.

Las preguntas vienen de la tabla `questions` (ver views/questions.py): el
registro de una evaluación nueva solo ofrece preguntas `active = 1`. Al editar
una evaluación existente, una pregunta que fue desactivada después de esa
evaluación **sigue apareciendo, editable**, si esa evaluación ya tenía una
respuesta para ella — así no se pierde/oculta una respuesta histórica solo
porque el criterio fue desactivado más tarde.

Um viewer vê Registrar e Aplicar Feedback — pode registrar avaliação nova e
confirmar que o feedback chegou ao técnico. Editar/Cancelar/Eliminar são
`role == 'admin'` apenas.
"""

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from core.auth import usuario_actual
from core.config import (
    FECHA_ANALISIS_FORMATO_PY,
    IDIOMA_OPTIONS,
    NOTA_OPTIONS,
    REGION_OPTIONS,
    STATUS_FEEDBACK_CANCELADO,
    STATUS_FEEDBACK_CONCLUIDO,
    STATUS_FEEDBACK_PENDIENTE,
    TABLES,
    sql_fecha_analisis,
)
from core.db import run_query_safe, run_transaction_safe
from core.i18n import t
from core.log import log_delete, log_insert, log_update
from core.ui import mostrar_error_db

st.title(t("analisis_page_title"), anchor=False)
st.caption(t("analisis_page_caption"))

T_ANALISE = TABLES["ticket_analysis"]
T_COMENTARIO = TABLES["general_comments"]
T_QUESTIONS = TABLES["questions"]
T_PILLARS = TABLES["pillars"]

SQL_QUESTIONS_COLUMNS = f"""
    q.id, p.name AS pillar, p.weight AS weight, q.label, q.description
    FROM {T_QUESTIONS} q
    JOIN {T_PILLARS} p ON p.id = q.pillar_id
"""

usuario = usuario_actual()
es_admin = usuario["role"] == "admin"

# Formato histórico del código de evaluación cuando la tabla está vacía.
ID_NUMBER_PREFIJO_DEFAULT = "IDQ"
ID_NUMBER_INICIAL = 10_001


def siguiente_idq() -> tuple[str | None, str | None]:
    """Calcula el próximo código IDQ (columna `id`) a partir del mayor ya existente.

    Devuelve (nuevo_idq, error) con el código completo (p. ej. 'IDQ10002'). El
    máximo se calcula sobre `id_number` (ya numérico, sin prefijo); el prefijo
    se deduce de un `id` existente.
    """
    df, error = run_query_safe(
        f"""
        SELECT MAX(CAST(id_number AS INTEGER)) AS ultimo,
               MIN(id) AS muestra
        FROM {T_ANALISE}
        """,
        columns=["ultimo", "muestra"],
    )
    if error:
        return None, error

    ultimo, muestra = None, None
    if not df.empty:
        ultimo, muestra = df.iloc[0]["ultimo"], df.iloc[0]["muestra"]

    if ultimo is None or pd.isna(ultimo):
        return f"{ID_NUMBER_PREFIJO_DEFAULT}{ID_NUMBER_INICIAL}", None

    prefijo = ID_NUMBER_PREFIJO_DEFAULT
    if isinstance(muestra, str):
        # 'IDQ10001' -> 'IDQ'; '10001' -> '' (columna sin prefijo)
        prefijo = re.sub(r"\d+$", "", muestra)

    return f"{prefijo}{int(ultimo) + 1}", None


def normalizar_idq(valor: str) -> str:
    """Normaliza lo escrito en el campo IDQ al código completo ('IDQXXXXXX').

    Acepta tanto el código completo (con o sin el prefijo en minúsculas) como
    solo el número (p. ej. '10001'), para que la búsqueda funcione igual en
    cualquiera de los dos casos.
    """
    valor = (valor or "").strip().upper()
    if not valor:
        return valor
    if valor.isdigit():
        return f"{ID_NUMBER_PREFIJO_DEFAULT}{valor}"
    return valor


def _entero_o_none(valor):
    """Convierte un valor de pandas (posible np.float64/NaN) a int de Python o None.

    Las FK numéricas (id_manager, id_analista, id_analista_quality...) vienen
    de dataframes con columnas nullable — el driver no sabe adaptar np.float64.
    """
    if valor is None or pd.isna(valor):
        return None
    return int(valor)


# El botón "Limpiar" no borra las claves de session_state una por una —
# Streamlit no garantiza que un widget vuelva a su valor por defecto solo
# porque su clave fue eliminada dentro del mismo ciclo de reruns. En cambio,
# se le agrega a cada clave un sufijo de "versión" que se incrementa al
# limpiar: eso fuerza a Streamlit a tratar los widgets como instancias nuevas
# (sin ningún estado previo), lo que sí resetea radios/selects/inputs de forma
# confiable.
if "reg_form_version" not in st.session_state:
    st.session_state["reg_form_version"] = 0


if es_admin:
    tab_registrar, tab_editar, tab_feedback, tab_cancelar, tab_eliminar = st.tabs(
        [t("reg_title"), t("edit_title"), t("feedback_tab_title"), t("cancel_title"), t("del_title")]
    )
else:
    # Viewer também vê Aplicar Feedback — é assim que um supervisor confirma
    # que o feedback chegou ao técnico, sem precisar de acesso admin.
    tab_registrar, tab_feedback = st.tabs([t("reg_title"), t("feedback_tab_title")])
    tab_editar = None
    tab_cancelar = None
    tab_eliminar = None


# ---------------------------------------------------------------------------
# Registrar nueva evaluación
# ---------------------------------------------------------------------------
with tab_registrar:
    st.subheader(t("reg_title"), anchor=False)
    st.caption(t("reg_caption"))

    agentes_df, err_agentes = run_query_safe(
        f"SELECT id, name as analista FROM {TABLES['quality_agent']} WHERE status = 'activate' ORDER BY analista",
        columns=["id", "analista"],
    )
    tecnicos_df, err_tecnicos = run_query_safe(
        f"SELECT id_analista, id_manager, name as analista, manager FROM {TABLES['analysts']} "
        "WHERE status = 'activate' ORDER BY analista",
        columns=["id_analista", "id_manager", "analista", "manager"],
    )
    # Solo preguntas ativas entram numa evaluación nova.
    active_questions_df, err_questions = run_query_safe(
        f"SELECT {SQL_QUESTIONS_COLUMNS} WHERE q.active = 1 ORDER BY q.id",
        columns=["id", "pillar", "weight", "label", "description"],
    )

    mostrar_error_db(err_agentes or err_tecnicos or err_questions)

    v = st.session_state["reg_form_version"]

    st.markdown(f"**{t('header_subheader')}**")
    c1, c2, c3, c4, c5 = st.columns(5)
    ticket_number = c1.text_input(t("field_ticket"), key=f"reg_ticket_{v}")
    analista_quality = c2.selectbox(
        t("field_analista_quality"), [""] + agentes_df["analista"].tolist(), key=f"reg_analista_{v}"
    )
    tecnico = c3.selectbox(t("field_tecnico_req"), [""] + tecnicos_df["analista"].tolist(), key=f"reg_tecnico_{v}")
    idioma = c4.selectbox(t("field_idioma"), [""] + IDIOMA_OPTIONS, key=f"reg_idioma_{v}")
    region = c5.selectbox(t("field_region"), [""] + REGION_OPTIONS, key=f"reg_region_{v}")

    manager_tecnico = ""
    id_analista = None
    id_manager = None
    if tecnico:
        fila = tecnicos_df.loc[tecnicos_df["analista"] == tecnico]
        if not fila.empty:
            manager_tecnico = fila.iloc[0]["manager"]
            id_analista = _entero_o_none(fila.iloc[0]["id_analista"])
            id_manager = _entero_o_none(fila.iloc[0]["id_manager"])
        st.caption(t("manager_tecnico_caption", manager=manager_tecnico or "—"))

    id_analista_quality = None
    if analista_quality:
        fila_aq = agentes_df.loc[agentes_df["analista"] == analista_quality]
        if not fila_aq.empty:
            id_analista_quality = _entero_o_none(fila_aq.iloc[0]["id"])

    st.divider()
    st.markdown(f"**{t('criterios_subheader')}**")

    respuestas = {}
    if active_questions_df.empty:
        st.warning(t("warn_sin_preguntas_activas"))
    for pillar, grupo in active_questions_df.groupby("pillar", sort=False):
        peso = grupo.iloc[0]["weight"]
        st.markdown(f"*{pillar}* (peso {peso})")
        for _, fila in grupo.iterrows():
            qid = int(fila["id"])
            rotulo = fila["label"]
            descripcion = fila["description"]
            col_nota, col_comentario = st.columns([1, 3])
            nota = col_nota.radio(
                rotulo, NOTA_OPTIONS, index=0, horizontal=True, key=f"reg_nota_{qid}_{v}", help=descripcion
            )
            comentario = col_comentario.text_input(
                "Comentario",
                key=f"reg_coment_{qid}_{v}",
                label_visibility="collapsed",
                placeholder=t("comentario_placeholder", rotulo=rotulo),
            )
            respuestas[qid] = {"pillar": pillar, "label": rotulo, "nota": nota, "comentario": comentario}

    st.divider()
    comentario_general = st.text_area(t("comentario_general_label"), key=f"reg_comentario_general_{v}")

    col_btn_registrar, col_btn_limpiar = st.columns([1, 1])
    click_registrar = col_btn_registrar.button(t("btn_registrar"), type="primary", key="reg_btn_registrar")
    click_limpiar = col_btn_limpiar.button(t("btn_limpiar"), key="reg_btn_limpiar")

    if click_limpiar:
        st.session_state["reg_form_version"] += 1
        st.rerun()

    if click_registrar:
        faltantes = [
            nombre
            for nombre, valor in {
                "TicketNumber": ticket_number,
                "Analista Quality": analista_quality,
                "Técnico": tecnico,
                "Idioma": idioma,
                "Región": region,
            }.items()
            if not valor
        ]

        if faltantes:
            st.error(t("err_encabezado", faltantes=", ".join(faltantes)))
        elif not respuestas:
            st.error(t("warn_sin_preguntas_activas"))
        else:
            nuevo_idq, err_idq = siguiente_idq()
            if err_idq:
                st.error(t("db_connection_error", error=err_idq))
            else:
                ahora = datetime.now()
                # `ticket_analysis.fecha_analisis` es texto en el formato
                # 'DD/MM/YYYY HH:MM' — se escribe así para que quede
                # comparable/ordenable con config.sql_fecha_analisis().
                # `general_comments.fecha` no se toca acá: sigue como datetime.
                fecha_analisis_texto = ahora.strftime(FECHA_ANALISIS_FORMATO_PY)

                # Todo el registro (N criterios + comentario general) va en UNA
                # transacción: si algo falla, no queda una evaluación gravada a
                # medias, que el Historial consolidaría con nota errada.
                nuevo_numero = re.sub(r"\D", "", nuevo_idq)

                SQL_INSERT_CRITERIO = f"""
                    INSERT INTO {T_ANALISE}
                        (id, id_number, id_manager, id_analista, id_analista_quality, question_id,
                         ticketnumber, analista_quality, nombre_del_tecnico, manager,
                         idioma, region, pergunta, pilar, nota, comentario,
                         fecha_analisis, status_feedback)
                    VALUES
                        (:id, :id_number, :id_manager, :id_analista, :id_analista_quality, :question_id,
                         :ticketnumber, :analista_quality, :nombre_del_tecnico, :manager,
                         :idioma, :region, :pergunta, :pilar, :nota, :comentario,
                         :fecha_analisis, :status_feedback)
                """

                operaciones = [
                    (
                        SQL_INSERT_CRITERIO,
                        {
                            "id": nuevo_idq,
                            "id_number": nuevo_numero,
                            "id_manager": id_manager,
                            "id_analista": id_analista,
                            "id_analista_quality": id_analista_quality,
                            "question_id": qid,
                            "ticketnumber": ticket_number,
                            "analista_quality": analista_quality,
                            "nombre_del_tecnico": tecnico,
                            "manager": manager_tecnico,
                            "idioma": idioma,
                            "region": region,
                            "pergunta": dato["label"],
                            "pilar": dato["pillar"],
                            "nota": dato["nota"],
                            "comentario": dato["comentario"],
                            "fecha_analisis": fecha_analisis_texto,
                            "status_feedback": STATUS_FEEDBACK_PENDIENTE,
                        },
                    )
                    for qid, dato in respuestas.items()
                ]

                if comentario_general.strip():
                    operaciones.append(
                        (
                            f"INSERT INTO {T_COMENTARIO} (id, comentario) VALUES (:id, :comentario)",
                            {"id": nuevo_idq, "comentario": comentario_general.strip()},
                        )
                    )

                # El encabezado se repite en todas las líneas, así que se loguea
                # una sola vez; cada criterio se identifica con "<rótulo>.nota" /
                # "<rótulo>.comentario" porque `pergunta` no es única por sí sola.
                operaciones += log_insert(
                    "ticket_analysis",
                    nuevo_idq,
                    {
                        "ticketnumber": ticket_number,
                        "analista_quality": analista_quality,
                        "nombre_del_tecnico": tecnico,
                        "manager": manager_tecnico,
                        "idioma": idioma,
                        "region": region,
                    },
                )
                valores_criterios = {}
                for dato in respuestas.values():
                    valores_criterios[f"{dato['label']}.nota"] = dato["nota"]
                    valores_criterios[f"{dato['label']}.comentario"] = dato["comentario"]
                operaciones += log_insert("ticket_analysis", nuevo_idq, valores_criterios)
                if comentario_general.strip():
                    operaciones += log_insert(
                        "general_comments", nuevo_idq, {"comentario": comentario_general.strip()}
                    )

                error = run_transaction_safe(operaciones)
                if error:
                    st.error(t("db_connection_error", error=error))
                else:
                    # El Historial cachea la consulta 5 min: sin esto, la nueva
                    # evaluación no aparecería hasta que expire el TTL.
                    st.cache_data.clear()
                    st.success(t("ok_registrado", idq=nuevo_idq))


# ---------------------------------------------------------------------------
# Editar evaluación existente
# ---------------------------------------------------------------------------
if es_admin:
    with tab_editar:
        st.subheader(t("edit_title"), anchor=False)
        st.caption(t("edit_caption"))

        st.markdown(f"**{t('consultar_subheader')}**")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        f_ticket = c1.text_input(t("field_ticket").replace(" *", ""), key="edit_f_ticket")
        f_idq = normalizar_idq(c2.text_input(t("field_idq"), key="edit_f_idq"))
        f_tecnico = c3.text_input(t("field_tecnico_req").replace(" *", ""), key="edit_f_tecnico")
        buscar = c4.button(t("btn_consultar"), use_container_width=True, key="edit_btn_buscar")

        if buscar:
            filtros = []
            params = {"limite": 500}
            if f_ticket:
                filtros.append("ticketnumber = :ticketnumber")
                params["ticketnumber"] = f_ticket
            if f_idq:
                filtros.append("id = :id")
                params["id"] = f_idq
            if f_tecnico:
                filtros.append("nombre_del_tecnico LIKE :nombre_del_tecnico")
                params["nombre_del_tecnico"] = f"%{f_tecnico}%"

            st.session_state["busca_directa_idq"] = bool(f_idq) and not f_ticket and not f_tecnico

            where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
            FECHA_EXPR = sql_fecha_analisis()
            resultado, err_busca = run_query_safe(
                f"""
                SELECT id, ticketnumber, nombre_del_tecnico, analista_quality, manager,
                       MAX({FECHA_EXPR}) AS ultima_actualizacion
                FROM {T_ANALISE}
                {where}
                GROUP BY id, ticketnumber, nombre_del_tecnico, analista_quality, manager
                ORDER BY ultima_actualizacion DESC
                LIMIT :limite
                """,
                params,
                columns=[
                    "id", "ticketnumber", "nombre_del_tecnico",
                    "analista_quality", "manager", "ultima_actualizacion",
                ],
            )
            mostrar_error_db(err_busca)
            st.session_state["resultado_busca"] = resultado

        resultado = st.session_state.get("resultado_busca")
        busca_directa_idq = st.session_state.get("busca_directa_idq", False)

        if resultado is not None:
            if busca_directa_idq:
                if resultado.empty:
                    st.warning(t("warn_sin_registros"))
                idq_seleccionado = str(resultado.iloc[0]["id"]) if not resultado.empty else ""
            else:
                st.dataframe(resultado, use_container_width=True, hide_index=True)

                idqs_disponibles = [""] + resultado["id"].astype(str).tolist()
                idq_seleccionado = st.selectbox(t("select_idq_edit"), idqs_disponibles, key="edit_idq_select")

            if idq_seleccionado:
                evaluacion, err_eval = run_query_safe(
                    f"""
                    SELECT question_id, ticketnumber, analista_quality, nombre_del_tecnico, manager, idioma, region,
                           pergunta, pilar, nota, comentario, status_feedback
                    FROM {T_ANALISE}
                    WHERE id = :id
                    """,
                    {"id": idq_seleccionado},
                    columns=[
                        "question_id", "ticketnumber", "analista_quality", "nombre_del_tecnico", "manager",
                        "idioma", "region", "pergunta", "pilar", "nota", "comentario",
                        "status_feedback",
                    ],
                )

                if err_eval:
                    mostrar_error_db(err_eval)
                elif evaluacion.empty:
                    st.warning(t("warn_sin_registros"))
                else:
                    encabezado = evaluacion.iloc[0]
                    st.divider()
                    st.markdown(f"**{t('editing_subheader', idq=idq_seleccionado)}**")

                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.text_input(t("field_ticket").replace(" *", ""), value=str(encabezado["ticketnumber"] or ""), disabled=True, key="edit_h_ticket")
                    c2.text_input(t("field_analista_quality").replace(" *", ""), value=encabezado["analista_quality"] or "", disabled=True, key="edit_h_analista")
                    c3.text_input(t("field_tecnico_req").replace(" *", ""), value=encabezado["nombre_del_tecnico"] or "", disabled=True, key="edit_h_tecnico")
                    c4.text_input(t("field_idioma").replace(" *", ""), value=encabezado["idioma"] or "", disabled=True, key="edit_h_idioma")
                    c5.text_input(t("field_region").replace(" *", ""), value=encabezado["region"] or "", disabled=True, key="edit_h_region")

                    # Preguntas a renderizar = ativas hoje UNION as que já têm
                    # resposta nesta avaliação (mesmo que tenham sido
                    # desativadas depois) — não some resposta histórica.
                    active_questions_df, err_active = run_query_safe(
                        f"SELECT {SQL_QUESTIONS_COLUMNS} WHERE q.active = 1",
                        columns=["id", "pillar", "weight", "label", "description"],
                    )
                    existing_ids = sorted({
                        int(qid) for qid in evaluacion["question_id"].dropna().unique()
                    })
                    if existing_ids:
                        placeholders = ", ".join(f":qid{i}" for i in range(len(existing_ids)))
                        extra_questions_df, err_extra = run_query_safe(
                            f"SELECT {SQL_QUESTIONS_COLUMNS} WHERE q.id IN ({placeholders})",
                            {f"qid{i}": qid for i, qid in enumerate(existing_ids)},
                            columns=["id", "pillar", "weight", "label", "description"],
                        )
                    else:
                        extra_questions_df = active_questions_df.iloc[0:0]
                    mostrar_error_db(err_active or (err_extra if existing_ids else None))

                    render_questions_df = (
                        pd.concat([active_questions_df, extra_questions_df])
                        .drop_duplicates(subset="id")
                        .sort_values(["pillar", "id"])
                    )

                    # `drop_duplicates` evita que .loc devuelva un DataFrame (en
                    # vez de una fila) si el mismo criterio apareciera repetido.
                    evaluacion_por_question = evaluacion.dropna(subset=["question_id"]).astype(
                        {"question_id": int}
                    ).drop_duplicates(subset="question_id", keep="last").set_index("question_id")

                    respuestas = {}
                    for pillar, grupo in render_questions_df.groupby("pillar", sort=False):
                        peso = grupo.iloc[0]["weight"]
                        st.markdown(f"*{pillar}* (peso {peso})")
                        for _, fila in grupo.iterrows():
                            qid = int(fila["id"])
                            rotulo = fila["label"]
                            descripcion = fila["description"]
                            nota_actual = "N/A"
                            comentario_actual = ""
                            if qid in evaluacion_por_question.index:
                                fila_resp = evaluacion_por_question.loc[qid]
                                nota_actual = str(fila_resp["nota"])
                                comentario_actual = fila_resp["comentario"] or ""

                            col_nota, col_comentario = st.columns([1, 3])
                            nota = col_nota.radio(
                                rotulo,
                                NOTA_OPTIONS,
                                index=NOTA_OPTIONS.index(nota_actual) if nota_actual in NOTA_OPTIONS else 0,
                                horizontal=True,
                                key=f"edit_nota_{qid}",
                                help=descripcion,
                            )
                            comentario = col_comentario.text_input(
                                "Comentario",
                                value=comentario_actual,
                                key=f"edit_coment_{qid}",
                                label_visibility="collapsed",
                            )
                            respuestas[qid] = {
                                "pillar": pillar, "label": rotulo, "nota": nota, "comentario": comentario,
                            }

                    comentario_general_nuevo = st.text_area(t("comentario_general_hist_label"), key="edit_comentario_general")

                    if st.button(t("btn_actualizar"), type="primary", key="edit_btn_actualizar"):
                        ahora = datetime.now()
                        # Mismo formato de texto usado en el registro — ver comentario allá.
                        fecha_analisis_texto = ahora.strftime(FECHA_ANALISIS_FORMATO_PY)

                        SQL_UPDATE_CRITERIO = f"""
                            UPDATE {T_ANALISE}
                            SET nota = :nota, comentario = :comentario, fecha_analisis = :fecha_analisis
                            WHERE id = :id AND question_id = :question_id
                        """
                        # Uma pergunta ativa que ainda não tinha resposta nesta
                        # avaliação (foi cadastrada depois que o ticket foi
                        # registrado) não tem linha pra dar UPDATE — precisa
                        # INSERT em vez de UPDATE.
                        SQL_INSERT_CRITERIO_NUEVO = f"""
                            INSERT INTO {T_ANALISE}
                                (id, id_number, question_id, ticketnumber, analista_quality,
                                 nombre_del_tecnico, manager, idioma, region, pergunta, pilar,
                                 nota, comentario, fecha_analisis, status_feedback)
                            VALUES
                                (:id, :id_number, :question_id, :ticketnumber, :analista_quality,
                                 :nombre_del_tecnico, :manager, :idioma, :region, :pergunta, :pilar,
                                 :nota, :comentario, :fecha_analisis, :status_feedback)
                        """

                        operaciones = []
                        for qid, dato in respuestas.items():
                            if qid in evaluacion_por_question.index:
                                operaciones.append(
                                    (
                                        SQL_UPDATE_CRITERIO,
                                        {
                                            "nota": dato["nota"],
                                            "comentario": dato["comentario"],
                                            "fecha_analisis": fecha_analisis_texto,
                                            "id": idq_seleccionado,
                                            "question_id": qid,
                                        },
                                    )
                                )
                            else:
                                operaciones.append(
                                    (
                                        SQL_INSERT_CRITERIO_NUEVO,
                                        {
                                            "id": idq_seleccionado,
                                            "id_number": re.sub(r"\D", "", idq_seleccionado),
                                            "question_id": qid,
                                            "ticketnumber": encabezado["ticketnumber"],
                                            "analista_quality": encabezado["analista_quality"],
                                            "nombre_del_tecnico": encabezado["nombre_del_tecnico"],
                                            "manager": encabezado["manager"],
                                            "idioma": encabezado["idioma"],
                                            "region": encabezado["region"],
                                            "pergunta": dato["label"],
                                            "pilar": dato["pillar"],
                                            "nota": dato["nota"],
                                            "comentario": dato["comentario"],
                                            "fecha_analisis": fecha_analisis_texto,
                                            "status_feedback": encabezado["status_feedback"],
                                        },
                                    )
                                )

                        if comentario_general_nuevo.strip():
                            operaciones.append(
                                (
                                    f"INSERT INTO {T_COMENTARIO} (id, comentario) VALUES (:id, :comentario)",
                                    {"id": idq_seleccionado, "comentario": comentario_general_nuevo.strip()},
                                )
                            )
                            operaciones += log_insert(
                                "general_comments", idq_seleccionado, {"comentario": comentario_general_nuevo.strip()}
                            )

                        # Solo loguea nota/comentario de los criterios que realmente
                        # cambiaron (log_update descarta los que quedaron iguales).
                        anteriores_log, nuevos_log = {}, {}
                        for qid, dato in respuestas.items():
                            rotulo = dato["label"]
                            anterior_nota, anterior_comentario = "N/A", ""
                            if qid in evaluacion_por_question.index:
                                fila_anterior = evaluacion_por_question.loc[qid]
                                anterior_nota = str(fila_anterior["nota"])
                                anterior_comentario = fila_anterior["comentario"] or ""
                            anteriores_log[f"{rotulo}.nota"] = anterior_nota
                            anteriores_log[f"{rotulo}.comentario"] = anterior_comentario
                            nuevos_log[f"{rotulo}.nota"] = dato["nota"]
                            nuevos_log[f"{rotulo}.comentario"] = dato["comentario"]
                        operaciones += log_update("ticket_analysis", idq_seleccionado, anteriores_log, nuevos_log)

                        error = run_transaction_safe(operaciones)
                        if error:
                            st.error(t("db_connection_error", error=error))
                        else:
                            # El Historial cachea la consulta 5 min: sin esto, la
                            # edición no aparecería hasta que expire el TTL.
                            st.cache_data.clear()
                            st.success(t("ok_actualizado", idq=idq_seleccionado))


# ---------------------------------------------------------------------------
# Aplicar Feedback — fecha o ciclo de vida da avaliação: Registrar é o início
# (status Pending), aplicar o feedback ao técnico é o Applied (fim).
# ---------------------------------------------------------------------------
with tab_feedback:
    st.subheader(t("feedback_subheader"), anchor=False)
    st.info(t("feedback_info"))

    idq_feedback = st.text_input(t("field_idq"), key="idq_feedback")
    buscar_feedback = st.button(t("btn_consultar"), key="btn_buscar_feedback", disabled=not idq_feedback)

    if buscar_feedback:
        estados, err_existe = run_query_safe(
            f"""
            SELECT DISTINCT ticketnumber, nombre_del_tecnico, status_feedback
            FROM {T_ANALISE} WHERE id = :id
            """,
            {"id": idq_feedback},
            columns=["ticketnumber", "nombre_del_tecnico", "status_feedback"],
        )
        if err_existe:
            st.error(t("db_connection_error", error=err_existe))
            estados = None
        elif estados.empty:
            st.error(t("err_idq_no_encontrado", idq=idq_feedback))
            estados = None
        st.session_state["feedback_estado_busca"] = estados if estados is not None and not estados.empty else None
        st.session_state["feedback_idq_buscado"] = idq_feedback

    estados = st.session_state.get("feedback_estado_busca")
    idq_encontrado = st.session_state.get("feedback_idq_buscado")

    if estados is not None and idq_encontrado == idq_feedback and idq_feedback:
        fila = estados.iloc[0]
        status_atual = ", ".join(sorted(estados["status_feedback"].dropna().astype(str).unique()))

        c1, c2, c3 = st.columns(3)
        c1.text_input(t("field_ticket").replace(" *", ""), value=str(fila["ticketnumber"] or ""), disabled=True, key="fb_h_ticket")
        c2.text_input(t("field_tecnico_req").replace(" *", ""), value=fila["nombre_del_tecnico"] or "", disabled=True, key="fb_h_tecnico")
        c3.text_input(t("field_status_atual"), value=status_atual, disabled=True, key="fb_h_status")

        status_unicos = set(estados["status_feedback"].dropna().unique())
        ja_concluido = STATUS_FEEDBACK_CONCLUIDO in status_unicos
        ja_cancelado = bool(status_unicos) and status_unicos <= {STATUS_FEEDBACK_CANCELADO}

        if ja_concluido:
            st.success(t("feedback_ja_concluido"))
        elif ja_cancelado:
            st.warning(t("feedback_cancelado_aviso"))
        elif st.button(t("btn_aplicar_feedback"), type="primary", key="btn_confirma_feedback"):
            operaciones = [
                (
                    f"""
                    UPDATE {T_ANALISE}
                    SET status_feedback = :status_concluido
                    WHERE id = :id AND status_feedback = :status_pendiente
                    """,
                    {
                        "id": idq_feedback,
                        "status_concluido": STATUS_FEEDBACK_CONCLUIDO,
                        "status_pendiente": STATUS_FEEDBACK_PENDIENTE,
                    },
                )
            ]
            operaciones += log_update(
                "ticket_analysis",
                idq_feedback,
                {"status_feedback": status_atual},
                {"status_feedback": STATUS_FEEDBACK_CONCLUIDO},
            )

            error = run_transaction_safe(operaciones)
            if error:
                st.error(t("db_connection_error", error=error))
            else:
                st.cache_data.clear()
                st.session_state.pop("feedback_estado_busca", None)
                st.success(t("ok_feedback_aplicado", idq=idq_feedback))


# ---------------------------------------------------------------------------
# Cancelar evaluación (reversível — distinto de Eliminar, que é definitivo)
# ---------------------------------------------------------------------------
if es_admin:
    with tab_cancelar:
        st.subheader(t("cancelar_subheader"), anchor=False)
        st.info(t("cancelar_info"))

        idq_cancelar = st.text_input(t("field_idq"), key="idq_cancelar")
        motivacion = st.text_area(t("field_motivacion"), key="motivacion_cancelar")

        if st.button(t("btn_confirma"), type="primary", disabled=not idq_cancelar, key="btn_confirma_cancelar"):
            estados_previos, err_existe = run_query_safe(
                f"SELECT DISTINCT status_feedback FROM {T_ANALISE} WHERE id = :id",
                {"id": idq_cancelar},
                columns=["status_feedback"],
            )
            if err_existe:
                st.error(t("db_connection_error", error=err_existe))
            elif estados_previos.empty:
                st.error(t("err_idq_no_encontrado", idq=idq_cancelar))
            else:
                # Marca el status_feedback de todas las líneas del id — es la
                # evaluación que el Historial usa para identificar los cancelados.
                # El patrón del LIKE va como parámetro (y no literal en el SQL)
                # para que los '%' no pasen por la interpolación del driver.
                operaciones = [
                    (
                        f"""
                        UPDATE {T_ANALISE}
                        SET status_feedback = :status_cancelado
                        WHERE id = :id
                          AND COALESCE(status_feedback, '') NOT LIKE :patron_cancelado
                        """,
                        {
                            "id": idq_cancelar,
                            "status_cancelado": STATUS_FEEDBACK_CANCELADO,
                            "patron_cancelado": "%cancel%",
                        },
                    )
                ]

                if motivacion.strip():
                    operaciones.append(
                        (
                            f"INSERT INTO {T_COMENTARIO} (id, comentario) VALUES (:id, :comentario)",
                            {
                                "id": idq_cancelar,
                                "comentario": f"{STATUS_FEEDBACK_CANCELADO.upper()} - {motivacion.strip()}",
                            },
                        )
                    )
                    operaciones += log_insert(
                        "general_comments",
                        idq_cancelar,
                        {"comentario": f"{STATUS_FEEDBACK_CANCELADO.upper()} - {motivacion.strip()}"},
                    )

                estado_previo = ", ".join(sorted(estados_previos["status_feedback"].dropna().astype(str).unique()))
                operaciones += log_update(
                    "ticket_analysis",
                    idq_cancelar,
                    {"status_feedback": estado_previo},
                    {"status_feedback": STATUS_FEEDBACK_CANCELADO},
                )

                error = run_transaction_safe(operaciones)
                if error:
                    st.error(t("db_connection_error", error=error))
                else:
                    st.cache_data.clear()
                    st.success(t("ok_cancelado", idq=idq_cancelar))


# ---------------------------------------------------------------------------
# Eliminar evaluación (destructivo e permanente — distinto de Cancelar)
# ---------------------------------------------------------------------------
if es_admin:
    with tab_eliminar:
        st.subheader(t("eliminar_subheader"), anchor=False)
        st.warning(t("eliminar_warning"))

        idq_eliminar = st.text_input(t("field_idq"), key="idq_eliminar")
        confirmar_eliminar = st.checkbox(t("confirm_eliminar_checkbox"), key="confirma_eliminar")

        if st.button(
            t("btn_eliminar"), type="primary", disabled=not (idq_eliminar and confirmar_eliminar), key="btn_eliminar"
        ):
            filas_previas, err_existe = run_query_safe(
                f"""
                SELECT ticketnumber, analista_quality, nombre_del_tecnico, manager, idioma, region,
                       pergunta, nota, comentario
                FROM {T_ANALISE}
                WHERE id = :id
                """,
                {"id": idq_eliminar},
                columns=[
                    "ticketnumber", "analista_quality", "nombre_del_tecnico", "manager",
                    "idioma", "region", "pergunta", "nota", "comentario",
                ],
            )
            if err_existe:
                st.error(t("db_connection_error", error=err_existe))
            elif filas_previas.empty:
                st.error(t("err_idq_no_encontrado", idq=idq_eliminar))
            else:
                # Los dos DELETE en una transacción: nunca deben quedar comentarios
                # generales huérfanos de una evaluación ya borrada (ni al contrario).
                primera = filas_previas.iloc[0]
                operaciones = [
                    (
                        f"DELETE FROM {T_ANALISE} WHERE id = :id",
                        {"id": idq_eliminar},
                    ),
                    (
                        f"DELETE FROM {T_COMENTARIO} WHERE id = :id",
                        {"id": idq_eliminar},
                    ),
                ]
                operaciones += log_delete(
                    "ticket_analysis",
                    idq_eliminar,
                    {
                        "ticketnumber": primera["ticketnumber"],
                        "analista_quality": primera["analista_quality"],
                        "nombre_del_tecnico": primera["nombre_del_tecnico"],
                        "manager": primera["manager"],
                        "idioma": primera["idioma"],
                        "region": primera["region"],
                    },
                )
                valores_criterios = {
                    f"{fila['pergunta']}.nota": fila["nota"] for _, fila in filas_previas.iterrows()
                }
                valores_criterios.update(
                    {f"{fila['pergunta']}.comentario": fila["comentario"] for _, fila in filas_previas.iterrows()}
                )
                operaciones += log_delete("ticket_analysis", idq_eliminar, valores_criterios)

                error = run_transaction_safe(operaciones)
                if error:
                    st.error(t("db_connection_error", error=error))
                else:
                    st.cache_data.clear()
                    st.success(t("ok_eliminado", idq=idq_eliminar))
