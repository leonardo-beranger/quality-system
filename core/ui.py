"""Pequeños helpers de presentación compartidos por las páginas.

Existe para que el reporte de errores del DW sea idéntico en todas las páginas:
el aviso genérico ("no fue posible conectar…") más la causa probable deducida de
la firma del error del driver (`db.diagnose_error`).
"""

import base64
from pathlib import Path

import streamlit as st

from .db import diagnose_error
from .i18n import t

# core/ui.py -> a pasta assets/ fica na raiz do projeto, um nível acima daqui.
_ASSETS = Path(__file__).parent.parent / "assets"

LOGO_PATH = _ASSETS / "logo.png"

# Mesmo favicon do portfólio (leonardo-beranger/portfolio): fundo #060126,
# "L" em off-white + "/" em teal, fonte monospace bold — replicado aqui
# porque `st.set_page_config(page_icon=...)` não aceita a `data:image/svg+xml`
# original (PIL, usado por baixo dos panos, não lê SVG).
FAVICON_PATH = _ASSETS / "favicon.png"

# Cor "cinza" da paleta de marca — texto secundário, legendas, captions.
# Não configurável via .streamlit/config.toml (que só define primaryColor/
# backgroundColor/secondaryBackgroundColor/textColor), então é aplicada via CSS.
_COR_CINZA = "#7C8A94"


def render_brand_theme() -> None:
    """Aplica a tipografia da marca (Outfit nos títulos, Inter no corpo) e a
    cor secundária "cinza" nas legendas/captions — chamado uma única vez, no
    entrypoint, antes de qualquer conteúdo.
    """
    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
        <style>
        html, body, [class*="css"] {{
            font-family: "Inter", sans-serif;
        }}
        h1, h2, h3, [data-testid="stMetricValue"] {{
            font-family: "Outfit", sans-serif;
            font-weight: 700;
        }}
        [data-testid="stCaptionContainer"], [data-testid="stCaption"] {{
            color: {_COR_CINZA} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_logo() -> None:
    """Fija una imagen al pie de la barra lateral (debajo del menú y del selector de idioma).

    El truco es puramente CSS: se vuelve la columna de la sidebar un flex
    container y se agrega un spacer con `flex: 1` justo antes de la imagen —
    el spacer absorbe todo el espacio vertical sobrante, empujando la imagen
    al fondo sin importar cuánto contenido haya arriba.
    """
    if not LOGO_PATH.exists():
        return

    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    st.sidebar.markdown(
        f"""
        <style>
        [data-testid="stSidebarContent"] {{
            display: flex;
            flex-direction: column;
            height: 100%;
        }}
        .sidebar-logo-spacer {{
            flex: 1 1 auto;
        }}
        .sidebar-logo {{
            padding: 1rem 0 0.5rem;
            text-align: center;
        }}
        .sidebar-logo img {{
            max-width: 70%;
        }}
        </style>
        <div class="sidebar-logo-spacer"></div>
        <div class="sidebar-logo"><img src="data:image/png;base64,{encoded}"></div>
        """,
        unsafe_allow_html=True,
    )


def mostrar_error_db(error: str | None) -> bool:
    """Muestra el aviso de error del DW y su causa probable. Devuelve True si había error.

    Se usa `st.warning` (y no `st.error`) porque las páginas siguen siendo
    utilizables sin banco: el formulario se renderiza igual, solo los listados y
    el guardado quedan indisponibles.
    """
    if not error:
        return False

    st.warning(t("db_connection_error", error=error))
    hint = diagnose_error(error)
    if hint:
        st.info(f"**{t('hint_label')}:** {t(hint)}")
    return True
