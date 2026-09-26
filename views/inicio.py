"""
Monitoreo de Calidad — página de inicio.

Equivalente al "Menu" de la planilha monitoreo_calidad_v2.xlsm, ahora como app
Streamlit multipágina (st.navigation). Cada ítem del menú original se convirtió
en una página dentro de `views/`.

Esta página también es el punto de diagnóstico de la conexión con el DW: prueba
la conexión y traduce el error del driver en una causa probable.
"""

import streamlit as st

from core.account import MIN_PASSWORD_LEN, alterar_senha_propria, usa_senha_padrao
from core.auth import usuario_actual
from core.db import diagnose_error, reset_engine, test_connection
from core.i18n import t

st.title(t("home_title"), anchor=False)
st.caption(t("home_caption"))

st.markdown(t("home_intro"))

st.divider()

st.subheader(t("home_db_subheader"), anchor=False)
st.caption(t("home_db_caption"))

c1, c2 = st.columns([1, 1])

if c1.button(t("test_connection_button"), type="primary"):
    ok, message = test_connection()
    if ok:
        st.success(t("test_connection_ok"))
    else:
        st.error(t("test_connection_fail", error=message))
        hint = diagnose_error(message)
        if hint:
            st.warning(f"**{t('hint_label')}:** {t(hint)}")

# El engine se cachea con st.cache_resource, así que editar db_config.json no
# tiene efecto hasta limpiar ese caché — sin este botón habría que reiniciar
# el servidor Streamlit para probar una configuración nueva.
if c2.button(t("reset_engine_button")):
    reset_engine()
    st.cache_data.clear()
    st.info(t("reset_engine_ok"))

# Troca de senha: qualquer usuário logado muda a própria senha aqui (não existe
# fluxo de "esqueci minha senha" — o admin redefine pelo cadastro, se preciso).
usuario = usuario_actual()
if usuario:
    st.divider()
    st.subheader(t("pwd_subheader"), anchor=False)
    st.caption(t("pwd_caption", min=MIN_PASSWORD_LEN))
    if usa_senha_padrao(usuario["id"]):
        st.warning(t("pwd_aviso_padrao"))

    with st.form("form_troca_senha", clear_on_submit=True):
        atual = st.text_input(t("pwd_field_atual"), type="password")
        nova = st.text_input(t("pwd_field_nueva"), type="password")
        confirmacao = st.text_input(t("pwd_field_confirma"), type="password")
        trocar = st.form_submit_button(t("pwd_btn"), type="primary")

    if trocar:
        erro = alterar_senha_propria(usuario["id"], atual, nova, confirmacao)
        if erro:
            st.error(t(erro))
        else:
            st.success(t("pwd_ok"))
