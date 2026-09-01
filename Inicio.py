"""
Punto de entrada de la app — declara la navegación (st.navigation) y registra
el idioma en la barra lateral una única vez por ejecución.

Usar st.navigation en vez de la carpeta `pages/` es lo que permite que el
cambio de idioma (y cualquier otro st.session_state) se mantenga al navegar
entre páginas: con `pages/`, cada clic en el menú lateral hace una navegación
de documento completa (nueva sesión); con st.navigation, todo corre dentro de
una única sesión continua.
"""

import streamlit as st

from core.auth import logout, render_login, usuario_actual
from core.config import APP_TITLE
from core.i18n import render_language_selector, t
from core.ui import FAVICON_PATH, render_brand_theme, render_sidebar_logo

st.set_page_config(page_title=APP_TITLE, page_icon=str(FAVICON_PATH), layout="wide")
render_brand_theme()
render_language_selector()

# El gate de login corta la ejecución acá: sin sesión válida, ni la navegación
# ni ninguna página se renderizan — solo el formulario de login y el selector
# de idioma (ya renderizado en la sidebar).
if not render_login():
    render_sidebar_logo()
    st.stop()

usuario = usuario_actual()
st.sidebar.divider()
st.sidebar.markdown(t("logged_in_as", nombre=usuario["name"]))
if st.sidebar.button(t("logout_button"), use_container_width=True):
    logout()

# El logo se fija al final de la sidebar (spacer con flex:1 antes de él) —
# por eso se llama después de todo el contenido propio de la sidebar, para
# que quede debajo del selector de idioma y del bloque de usuario/logout.
render_sidebar_logo()

es_admin = usuario["role"] == "admin"

# Ordem fixa: Início, Dashboard, Cadastros, Perguntas, Análises, Histórico.
# Dashboard e Histórico são só leitura — visíveis pra admin e viewer. Cadastros
# e Perguntas são administrativos. Cancelar/Eliminar são abas dentro da
# própria página Análises (admin-only, filtrado lá dentro), e Análises só
# mostra a aba Registrar pra viewer (também filtrado dentro da página).
pages = [
    st.Page("views/inicio.py", title=t("nav_inicio"), default=True),
    st.Page("views/dashboard.py", title=t("dashboard_page_title")),
]
if es_admin:
    pages.append(st.Page("views/registros.py", title=t("registros_page_title")))
    pages.append(st.Page("views/questions.py", title=t("questions_page_title")))
pages.append(st.Page("views/analisis.py", title=t("analisis_page_title")))
pages.append(st.Page("views/historial_analisis.py", title=t("hist_title")))

pg = st.navigation(pages)
pg.run()
