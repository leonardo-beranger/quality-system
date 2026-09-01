"""Registros — Quality Agent, Manager y Analistas en una sola página con pestañas.

Equivalente a los formularios "Quality Agent", "Controle Manager" y "Controle
Analistas" de la planilha original, agrupados en pestañas (mismo patrón de
`st.tabs` usado en export_BI_reports/app.py).

Página restrita a `role == 'admin'` — cadastro de usuários/managers/técnicos
não é uma tarefa de viewer.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from core.auth import hash_password, usuario_actual
from core.config import REGION_OPTIONS, ROLE_OPTIONS, STATUS_OPTIONS, TABLES, senha_padrao
from core.db import run_query_safe, run_statement_safe, run_transaction_safe, siguiente_id
from core.i18n import t
from core.log import log_insert, log_update
from core.ui import mostrar_error_db

if usuario_actual()["role"] != "admin":
    st.error(t("err_acceso_restringido"))
    st.stop()

st.title(t("registros_page_title"), anchor=False)
st.caption(t("registros_page_caption"))

tab_quality_agent, tab_manager, tab_analistas = st.tabs(
    [t("qa_title"), t("mgr_title"), t("an_title")]
)


# ---------------------------------------------------------------------------
# Quality Agent
# ---------------------------------------------------------------------------
with tab_quality_agent:
    st.subheader(t("qa_title"), anchor=False)
    st.caption(t("qa_caption"))

    TABLE = TABLES["quality_agent"]
    agents_df, db_error = run_query_safe(
        f"SELECT name as analista, email, status, role FROM {TABLE} ORDER BY analista",
        columns=["analista", "email", "status", "role"],
    )

    col_form, col_list = st.columns([1, 1])

    with col_form:
        st.markdown(f"**{t('load_form_subheader')}**")

        nombres = [""] + agents_df["analista"].tolist()
        seleccionado = st.selectbox(t("select_to_load"), nombres, key="qa_load")

        datos_cargados = {"analista": "", "email": "", "status": STATUS_OPTIONS[0], "role": ROLE_OPTIONS[-1]}
        if seleccionado:
            fila = agents_df.loc[agents_df["analista"] == seleccionado].iloc[0]
            datos_cargados = {
                "analista": fila["analista"],
                "email": fila["email"],
                "status": fila["status"],
                "role": fila["role"] or ROLE_OPTIONS[-1],
            }

        with st.form("form_quality_agent", clear_on_submit=False):
            analista = st.text_input(t("field_analista"), value=datos_cargados["analista"])
            email = st.text_input(t("field_email"), value=datos_cargados["email"])
            status = st.selectbox(
                t("field_status"),
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(datos_cargados["status"]) if datos_cargados["status"] in STATUS_OPTIONS else 0,
            )
            role = st.selectbox(
                t("field_role"),
                ROLE_OPTIONS,
                index=ROLE_OPTIONS.index(datos_cargados["role"]) if datos_cargados["role"] in ROLE_OPTIONS else 0,
            )

            if not seleccionado:
                st.caption(t("qa_senha_padrao_caption", senha=senha_padrao()))

            c1, c2 = st.columns(2)
            registrar = c1.form_submit_button(t("btn_registrar"), use_container_width=True)
            actualizar = c2.form_submit_button(t("btn_actualizar"), use_container_width=True)

            if registrar:
                if not analista:
                    st.error(t("err_informe_analista"))
                else:
                    # `id` no es autoincremental en el banco: hay que calcular el
                    # próximo valor a mano, o la fila queda con id NULL.
                    nuevo_id, err_id = siguiente_id(TABLE, "id")
                    if err_id:
                        st.error(t("db_connection_error", error=err_id))
                    else:
                        # Todo usuario nuevo entra con la senha padrão do ano
                        # atual (`quality_2026`, etc.) — não há tela de "esqueci
                        # minha senha", então o admin precisa avisar essa senha
                        # ao usuário para o primeiro acesso.
                        password_hash = hash_password(senha_padrao())
                        operaciones = [
                            (
                                f"INSERT INTO {TABLE} (id, name, email, status, role, password_hash) "
                                "VALUES (:id, :analista, :email, :status, :role, :password_hash)",
                                {
                                    "id": nuevo_id,
                                    "analista": analista,
                                    "email": email,
                                    "status": status,
                                    "role": role,
                                    "password_hash": password_hash,
                                },
                            )
                        ]
                        operaciones += log_insert(
                            "quality_agent",
                            analista,
                            {"id": nuevo_id, "name": analista, "email": email, "status": status, "role": role},
                        )
                        error = run_transaction_safe(operaciones)
                        if error:
                            st.error(error)
                        else:
                            st.success(t("ok_analista_registrado_senha", nombre=analista, senha=senha_padrao()))
                            st.rerun()

            if actualizar:
                if not seleccionado:
                    st.error(t("err_cargue_analista"))
                else:
                    operaciones = [
                        (
                            f"UPDATE {TABLE} SET email = :email, status = :status, role = :role WHERE name = :analista",
                            {"analista": seleccionado, "email": email, "status": status, "role": role},
                        )
                    ]
                    operaciones += log_update(
                        "quality_agent",
                        seleccionado,
                        {"email": datos_cargados["email"], "status": datos_cargados["status"], "role": datos_cargados["role"]},
                        {"email": email, "status": status, "role": role},
                    )
                    error = run_transaction_safe(operaciones)
                    if error:
                        st.error(error)
                    else:
                        st.success(t("ok_analista_actualizado", nombre=seleccionado))
                        st.rerun()

    with col_list:
        st.markdown(f"**{t('current_list_subheader')}**")
        if db_error:
            mostrar_error_db(db_error)
        st.dataframe(agents_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
with tab_manager:
    st.subheader(t("mgr_title"), anchor=False)
    st.caption(t("mgr_caption"))

    TABLE = TABLES["managers"]
    managers_df, db_error = run_query_safe(
        f"SELECT manager, email, status FROM {TABLE} ORDER BY manager",
        columns=["manager", "email", "status"],
    )

    col_form, col_list = st.columns([1, 1])

    with col_form:
        st.markdown(f"**{t('load_form_subheader')}**")

        nombres = [""] + managers_df["manager"].tolist()
        seleccionado = st.selectbox(t("select_to_load"), nombres, key="mgr_load")

        datos_cargados = {"manager": "", "email": "", "status": STATUS_OPTIONS[0]}
        if seleccionado:
            fila = managers_df.loc[managers_df["manager"] == seleccionado].iloc[0]
            datos_cargados = {"manager": fila["manager"], "email": fila["email"], "status": fila["status"]}

        with st.form("form_manager", clear_on_submit=False):
            manager = st.text_input(t("field_manager"), value=datos_cargados["manager"])
            email = st.text_input(t("field_email"), value=datos_cargados["email"])
            status = st.selectbox(
                t("field_status"),
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(datos_cargados["status"]) if datos_cargados["status"] in STATUS_OPTIONS else 0,
            )

            c1, c2 = st.columns(2)
            registrar = c1.form_submit_button(t("btn_registrar"), use_container_width=True)
            actualizar = c2.form_submit_button(t("btn_actualizar"), use_container_width=True)

            if registrar:
                if not manager:
                    st.error(t("err_informe_manager"))
                else:
                    # `id_manager` no es autoincremental en el banco: hay que
                    # calcular el próximo valor a mano.
                    nuevo_id, err_id = siguiente_id(TABLE, "id_manager")
                    if err_id:
                        st.error(t("db_connection_error", error=err_id))
                    else:
                        operaciones = [
                            (
                                f"INSERT INTO {TABLE} (id_manager, manager, email, status) "
                                "VALUES (:id_manager, :manager, :email, :status)",
                                {"id_manager": nuevo_id, "manager": manager, "email": email, "status": status},
                            )
                        ]
                        operaciones += log_insert(
                            "managers",
                            manager,
                            {"id_manager": nuevo_id, "manager": manager, "email": email, "status": status},
                        )
                        error = run_transaction_safe(operaciones)
                        if error:
                            st.error(error)
                        else:
                            st.success(t("ok_manager_registrado", nombre=manager))
                            st.rerun()

            if actualizar:
                if not seleccionado:
                    st.error(t("err_cargue_manager"))
                else:
                    operaciones = [
                        (
                            f"UPDATE {TABLE} SET email = :email, status = :status WHERE manager = :manager",
                            {"manager": seleccionado, "email": email, "status": status},
                        )
                    ]
                    operaciones += log_update(
                        "managers",
                        seleccionado,
                        {"email": datos_cargados["email"], "status": datos_cargados["status"]},
                        {"email": email, "status": status},
                    )
                    error = run_transaction_safe(operaciones)
                    if error:
                        st.error(error)
                    else:
                        st.success(t("ok_manager_actualizado", nombre=seleccionado))
                        st.rerun()

    with col_list:
        st.markdown(f"**{t('current_list_subheader')}**")
        if db_error:
            mostrar_error_db(db_error)
        st.dataframe(managers_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Analistas (técnicos)
# ---------------------------------------------------------------------------
with tab_analistas:
    st.subheader(t("an_title"), anchor=False)
    st.caption(t("an_caption"))

    TABLE = TABLES["analysts"]
    TABLE_ANALISE = TABLES["ticket_analysis"]
    STATUS_ANALISTA_OPTIONS = STATUS_OPTIONS + ["undefined"]

    analistas_df, db_error = run_query_safe(
        f"SELECT name as analista, manager, email, status, region, updated_on FROM {TABLE} ORDER BY analista",
        columns=["analista", "manager", "email", "status", "region", "updated_on"],
    )
    managers_df_an, managers_error = run_query_safe(
        f"SELECT id_manager, manager FROM {TABLES['managers']} ORDER BY manager",
        columns=["id_manager", "manager"],
    )
    managers_list = managers_df_an["manager"].tolist()

    col_form, col_list = st.columns([1, 1])

    with col_form:
        st.markdown(f"**{t('load_form_subheader')}**")

        nombres = [""] + analistas_df["analista"].tolist()
        seleccionado = st.selectbox(t("field_tecnico"), nombres, key="an_load")

        datos_cargados = {
            "analista": "", "manager": "", "email": "", "status": STATUS_ANALISTA_OPTIONS[0], "region": "",
        }
        manager_anterior = None
        if seleccionado:
            fila = analistas_df.loc[analistas_df["analista"] == seleccionado].iloc[0]
            datos_cargados = {
                "analista": fila["analista"],
                "manager": fila["manager"],
                "email": fila["email"],
                "status": fila["status"],
                "region": fila["region"] or "",
            }
            manager_anterior = fila["manager"]

        with st.form("form_analista", clear_on_submit=False):
            analista = st.text_input(t("field_analista"), value=datos_cargados["analista"])
            manager = st.selectbox(
                t("field_manager"),
                [""] + managers_list,
                index=([""] + managers_list).index(datos_cargados["manager"])
                if datos_cargados["manager"] in managers_list
                else 0,
            )
            email = st.text_input(t("field_email"), value=datos_cargados["email"])
            status = st.selectbox(
                t("field_status"),
                STATUS_ANALISTA_OPTIONS,
                index=STATUS_ANALISTA_OPTIONS.index(datos_cargados["status"])
                if datos_cargados["status"] in STATUS_ANALISTA_OPTIONS
                else 0,
            )
            region = st.selectbox(
                t("field_region").replace(" *", ""),
                [""] + REGION_OPTIONS,
                index=([""] + REGION_OPTIONS).index(datos_cargados["region"])
                if datos_cargados["region"] in REGION_OPTIONS
                else 0,
            )

            c1, c2 = st.columns(2)
            registrar = c1.form_submit_button(t("btn_registrar"), use_container_width=True)
            actualizar = c2.form_submit_button(t("btn_actualizar"), use_container_width=True)

            # `id_manager` es la FK hacia managers — se resuelve acá a partir
            # del nombre elegido, ya que el formulario solo selecciona por
            # nombre. La columna es texto: el valor crudo de pandas viene como
            # np.float64 (por los NaN de filas sin manager), y el driver no
            # sabe adaptar ese tipo — se convierte a str explícito.
            fila_manager = managers_df_an.loc[managers_df_an["manager"] == manager]
            id_manager_valor = fila_manager.iloc[0]["id_manager"] if not fila_manager.empty else None
            if id_manager_valor is None or pd.isna(id_manager_valor):
                id_manager = None
            elif isinstance(id_manager_valor, float):
                id_manager = str(int(id_manager_valor))
            else:
                id_manager = str(id_manager_valor)

            if registrar:
                if not analista:
                    st.error(t("err_informe_tecnico"))
                else:
                    # `id_analista` no es autoincremental en el banco: hay que
                    # calcular el próximo valor a mano.
                    nuevo_id, err_id = siguiente_id(TABLE, "id_analista")
                    if err_id:
                        st.error(t("db_connection_error", error=err_id))
                    else:
                        valores = {
                            "id_analista": nuevo_id,
                            "name": analista,
                            "id_manager": id_manager,
                            "manager": manager,
                            "email": email,
                            "status": status,
                            "region": region,
                        }
                        operaciones = [
                            (
                                f"INSERT INTO {TABLE} (id_analista, name, id_manager, manager, email, status, region, updated_on) "
                                "VALUES (:id_analista, :analista, :id_manager, :manager, :email, :status, :region, :updated_on)",
                                {**valores, "analista": analista, "updated_on": datetime.now()},
                            )
                        ]
                        operaciones += log_insert("analysts", analista, valores)
                        error = run_transaction_safe(operaciones)
                        if error:
                            st.error(error)
                        else:
                            st.success(t("ok_tecnico_registrado", nombre=analista))
                            st.rerun()

            if actualizar:
                if not seleccionado:
                    st.error(t("err_cargue_tecnico"))
                else:
                    operaciones = [
                        (
                            f"UPDATE {TABLE} SET id_manager = :id_manager, manager = :manager, email = :email, "
                            "status = :status, region = :region, updated_on = :updated_on WHERE name = :analista",
                            {
                                "analista": seleccionado,
                                "id_manager": id_manager,
                                "manager": manager,
                                "email": email,
                                "status": status,
                                "region": region,
                                "updated_on": datetime.now(),
                            },
                        )
                    ]
                    operaciones += log_update(
                        "analysts",
                        seleccionado,
                        {
                            "manager": datos_cargados["manager"],
                            "email": datos_cargados["email"],
                            "status": datos_cargados["status"],
                            "region": datos_cargados["region"],
                        },
                        {"manager": manager, "email": email, "status": status, "region": region},
                    )
                    error = run_transaction_safe(operaciones)
                    if error:
                        st.error(error)
                    else:
                        if manager_anterior is not None and manager != manager_anterior:
                            cascade_error = run_statement_safe(
                                f"UPDATE {TABLE_ANALISE} SET manager = :manager "
                                "WHERE nombre_del_tecnico = :nombre_del_tecnico",
                                {"manager": manager, "nombre_del_tecnico": seleccionado},
                            )
                            if cascade_error:
                                st.error(cascade_error)
                            else:
                                st.info(t("cascada_info", nombre=seleccionado))

                        st.success(t("ok_tecnico_actualizado", nombre=seleccionado))
                        st.rerun()

    with col_list:
        st.markdown(f"**{t('current_list_subheader')}**")
        if db_error:
            mostrar_error_db(db_error)
        st.dataframe(analistas_df, use_container_width=True, hide_index=True)
