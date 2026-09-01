"""Perguntas — cadastro de pilares (nome + peso) e dos critérios de avaliação
vinculados a eles, com ativação/desativação.

Os critérios ficam na tabela `questions` (ver db.py), com uma flag `active` e
uma FK `pillar_id` para `pillars`. A página "Análises" só oferece perguntas
ativas para uma avaliação **nova**; uma pergunta desativada continua
aparecendo, editável, em avaliações antigas que já a responderam (ver
views/analisis.py).

Convenção do app: nome do pilar em inglês, rótulo/descrição da pergunta em
português.

Página restrita a `role == 'admin'`.
"""

import streamlit as st

from core.auth import usuario_actual
from core.config import TABLES
from core.db import run_query_safe, run_transaction_safe, siguiente_id
from core.i18n import t
from core.log import log_insert, log_update
from core.ui import mostrar_error_db

if usuario_actual()["role"] != "admin":
    st.error(t("err_acceso_restringido"))
    st.stop()

st.title(t("questions_page_title"), anchor=False)
st.caption(t("questions_page_caption"))

T_PILLARS = TABLES["pillars"]
T_QUESTIONS = TABLES["questions"]

tab_pilares, tab_perguntas = st.tabs([t("pillars_tab_title"), t("questions_tab_title")])


# ---------------------------------------------------------------------------
# Pilares — nome (inglês) + peso
# ---------------------------------------------------------------------------
with tab_pilares:
    st.subheader(t("pillars_tab_title"), anchor=False)
    st.caption(t("pillars_tab_caption"))

    pillars_df, err_pillars = run_query_safe(
        f"SELECT id, name, weight FROM {T_PILLARS} ORDER BY name",
        columns=["id", "name", "weight"],
    )

    col_form, col_list = st.columns([1, 1])

    with col_form:
        st.markdown(f"**{t('load_form_subheader')}**")

        nombres_pilares = [""] + pillars_df["name"].tolist()
        pilar_seleccionado = st.selectbox(t("select_to_load"), nombres_pilares, key="pillar_load")

        datos_pilar = {"id": None, "name": "", "weight": 1.0}
        if pilar_seleccionado:
            fila = pillars_df.loc[pillars_df["name"] == pilar_seleccionado].iloc[0]
            datos_pilar = {"id": int(fila["id"]), "name": fila["name"], "weight": float(fila["weight"])}

        with st.form("form_pillar", clear_on_submit=False):
            pillar_name = st.text_input(t("field_pillar_name"), value=datos_pilar["name"])
            pillar_weight = st.number_input(
                t("field_pillar_weight"), min_value=0.1, step=0.1, value=datos_pilar["weight"] or 1.0
            )

            c1, c2 = st.columns(2)
            registrar_pilar = c1.form_submit_button(t("btn_registrar"), use_container_width=True)
            actualizar_pilar = c2.form_submit_button(t("btn_actualizar"), use_container_width=True)

            if registrar_pilar:
                if not pillar_name:
                    st.error(t("err_informe_pillar_name"))
                elif pillar_name in pillars_df["name"].tolist():
                    st.error(t("err_pillar_duplicado", nombre=pillar_name))
                else:
                    nuevo_id, err_id = siguiente_id(T_PILLARS, "id")
                    if err_id:
                        st.error(t("db_connection_error", error=err_id))
                    else:
                        valores = {"id": nuevo_id, "name": pillar_name, "weight": pillar_weight}
                        operaciones = [
                            (
                                f"INSERT INTO {T_PILLARS} (id, name, weight) VALUES (:id, :name, :weight)",
                                valores,
                            )
                        ]
                        operaciones += log_insert("pillars", pillar_name, valores)
                        error = run_transaction_safe(operaciones)
                        if error:
                            st.error(error)
                        else:
                            st.success(t("ok_pillar_registrado", nombre=pillar_name))
                            st.rerun()

            if actualizar_pilar:
                if not pilar_seleccionado:
                    st.error(t("err_cargue_pillar"))
                else:
                    operaciones = [
                        (
                            f"UPDATE {T_PILLARS} SET name = :name, weight = :weight WHERE id = :id",
                            {"id": datos_pilar["id"], "name": pillar_name, "weight": pillar_weight},
                        )
                    ]
                    operaciones += log_update(
                        "pillars",
                        pilar_seleccionado,
                        {"name": datos_pilar["name"], "weight": str(datos_pilar["weight"])},
                        {"name": pillar_name, "weight": str(pillar_weight)},
                    )
                    error = run_transaction_safe(operaciones)
                    if error:
                        st.error(error)
                    else:
                        st.success(t("ok_pillar_actualizado", nombre=pillar_name))
                        st.rerun()

    with col_list:
        st.markdown(f"**{t('current_list_subheader')}**")
        if err_pillars:
            mostrar_error_db(err_pillars)
        st.dataframe(pillars_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Perguntas — vinculadas a um pilar
# ---------------------------------------------------------------------------
with tab_perguntas:
    st.subheader(t("questions_tab_title"), anchor=False)
    st.caption(t("questions_tab_caption"))

    pillars_df, err_pillars = run_query_safe(
        f"SELECT id, name, weight FROM {T_PILLARS} ORDER BY name",
        columns=["id", "name", "weight"],
    )
    questions_df, err_questions = run_query_safe(
        f"""
        SELECT q.id, p.name AS pillar, p.weight AS weight, q.label, q.description, q.active
        FROM {T_QUESTIONS} q
        JOIN {T_PILLARS} p ON p.id = q.pillar_id
        ORDER BY p.name, q.id
        """,
        columns=["id", "pillar", "weight", "label", "description", "active"],
    )

    if pillars_df.empty:
        st.warning(t("warn_sin_pilares"))
    else:
        col_form, col_list = st.columns([1, 1])

        with col_form:
            st.markdown(f"**{t('load_form_subheader')}**")

            rotulos_existentes = [""] + questions_df["label"].tolist()
            seleccionado = st.selectbox(t("select_to_load"), rotulos_existentes, key="q_load")

            pilares_options = pillars_df["name"].tolist()
            datos_cargados = {"id": None, "pillar": pilares_options[0], "label": "", "description": "", "active": True}
            if seleccionado:
                fila = questions_df.loc[questions_df["label"] == seleccionado].iloc[0]
                datos_cargados = {
                    "id": int(fila["id"]),
                    "pillar": fila["pillar"],
                    "label": fila["label"],
                    "description": fila["description"] or "",
                    "active": bool(fila["active"]),
                }

            with st.form("form_question", clear_on_submit=False):
                pillar = st.selectbox(
                    t("field_pillar"),
                    pilares_options,
                    index=pilares_options.index(datos_cargados["pillar"]) if datos_cargados["pillar"] in pilares_options else 0,
                )
                peso_pillar = pillars_df.loc[pillars_df["name"] == pillar, "weight"].iloc[0]
                st.caption(t("field_weight_caption", peso=peso_pillar))
                label = st.text_input(t("field_question_label"), value=datos_cargados["label"])
                description = st.text_area(t("field_question_description"), value=datos_cargados["description"])
                active = st.checkbox(t("field_question_active"), value=datos_cargados["active"])

                c1, c2 = st.columns(2)
                registrar = c1.form_submit_button(t("btn_registrar"), use_container_width=True)
                actualizar = c2.form_submit_button(t("btn_actualizar"), use_container_width=True)

                pillar_id = int(pillars_df.loc[pillars_df["name"] == pillar, "id"].iloc[0])

                if registrar:
                    if not label:
                        st.error(t("err_informe_question_label"))
                    else:
                        nuevo_id, err_id = siguiente_id(T_QUESTIONS, "id")
                        if err_id:
                            st.error(t("db_connection_error", error=err_id))
                        else:
                            valores = {
                                "id": nuevo_id,
                                "pillar_id": pillar_id,
                                "label": label,
                                "description": description,
                                "active": int(active),
                            }
                            operaciones = [
                                (
                                    f"INSERT INTO {T_QUESTIONS} (id, pillar_id, label, description, active) "
                                    "VALUES (:id, :pillar_id, :label, :description, :active)",
                                    valores,
                                )
                            ]
                            operaciones += log_insert("questions", label, valores)
                            error = run_transaction_safe(operaciones)
                            if error:
                                st.error(error)
                            else:
                                st.success(t("ok_question_registrada", nombre=label))
                                st.rerun()

                if actualizar:
                    if not seleccionado:
                        st.error(t("err_cargue_question"))
                    else:
                        operaciones = [
                            (
                                f"UPDATE {T_QUESTIONS} SET pillar_id = :pillar_id, label = :label, "
                                "description = :description, active = :active WHERE id = :id",
                                {
                                    "id": datos_cargados["id"],
                                    "pillar_id": pillar_id,
                                    "label": label,
                                    "description": description,
                                    "active": int(active),
                                },
                            )
                        ]
                        operaciones += log_update(
                            "questions",
                            label,
                            {
                                "pillar": datos_cargados["pillar"],
                                "label": datos_cargados["label"],
                                "description": datos_cargados["description"],
                                "active": str(datos_cargados["active"]),
                            },
                            {"pillar": pillar, "label": label, "description": description, "active": str(active)},
                        )
                        error = run_transaction_safe(operaciones)
                        if error:
                            st.error(error)
                        else:
                            st.success(t("ok_question_actualizada", nombre=label))
                            st.rerun()

        with col_list:
            st.markdown(f"**{t('current_list_subheader')}**")
            if err_questions:
                mostrar_error_db(err_questions)
            st.dataframe(questions_df, use_container_width=True, hide_index=True)
