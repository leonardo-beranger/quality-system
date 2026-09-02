"""Dashboard — indicadores de qualidade, inspirado no layout do BI de referência.

Adaptação para o schema local: o BI original tinha uma fila de envio
(`analise_enviadas`) e um fluxo de impugnação (`Impugnaciones`, removido desta
app — ver views/analisis.py). Os indicadores usam o ciclo de vida real de
`ticket_analysis.status_feedback` (ver views/analisis.py): `Pendiente`
(início, criado ao Registrar) → `Concluído` (fim, aba "Aplicar Feedback") ou
`Cancelado` (reversível, aba "Cancelar Análise"):

- **Feedbacks Encaminhados** = total de avaliações (IDQ únicos) no período.
- **Feedbacks Aplicados** = % de avaliações **não canceladas** com
  `status_feedback = 'Concluído'` — ou seja, quantas do que realmente entrou
  no fluxo já tiveram o feedback aplicado ao técnico.
- **Nível Qualidade** = média das notas (1=100%, 0=0%, N/A excluída),
  ponderada pelo peso do pilar de cada pergunta (`pillars.weight`), em 0-10.

"Feedbacks Contestados" (impugnação) não existe mais nesta app.

## Filtros e clique-pra-filtrar

Os filtros do topo (Período/Manager/Técnico/Pilar) recortam `df` antes de
qualquer cálculo. Manager→Técnico é em cascata: trocar o Manager restringe as
opções de Técnico (a chave do widget do Técnico embute o Manager selecionado,
então o próprio Streamlit reseta o Técnico pra "Todos" quando isso acontece,
em vez de tentar validar um valor que não existe mais na lista).

Clicar numa barra/fatia (Status, Pilares, Supervisores, Analistas) também
filtra o resto da página — como no Power BI. Isso funciona lendo
`st.session_state[chave_do_gráfico]` **no topo do script**, antes de montar
qualquer gráfico: um clique dispara um rerun, e o Streamlit já grava a seleção
no session_state antes desse rerun começar a executar o script de novo, então
dá pra ler o clique cedo e aplicar como mais um filtro sobre `df`.

Todas as chaves de widget (filtros e gráficos clicáveis) embutem um contador
`dash_v` — o botão "limpar filtros" só incrementa esse contador e força
rerun, o que faz o Streamlit tratar cada widget como uma instância nova (sem
estado anterior), zerando filtros manuais E seleções de clique de uma vez.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.config import (
    FECHA_ANALISIS_FORMATO_PY,
    STATUS_FEEDBACK_CANCELADO,
    STATUS_FEEDBACK_CONCLUIDO,
    STATUS_FEEDBACK_PENDIENTE,
    TABLES,
)
from core.db import run_query_safe
from core.i18n import t
from core.ui import mostrar_error_db

st.title(t("dashboard_page_title"), anchor=False)
st.caption(t("dashboard_page_caption"))

T_ANALISE = TABLES["ticket_analysis"]
T_PILLARS = TABLES["pillars"]

# Paleta de marca (ver .streamlit/config.toml) — usada nos gráficos porque
# plotly não herda o tema do Streamlit automaticamente.
COR_TEAL = "#16A085"
COR_CIANO = "#22D3B4"
COR_CINZA = "#7C8A94"
COR_OFFWHITE = "#F5F3EE"
COR_GRAFITE = "#12212E"
COR_VERMELHO = "#E5484D"
COR_ROXO = "#8B5CF6"
COR_AZUL = "#3B82F6"

_LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=COR_OFFWHITE, family="Inter, sans-serif"),
    margin=dict(l=10, r=10, t=30, b=10),
)


@st.cache_data(ttl=300, show_spinner=False)
def carregar_dados():
    df, err = run_query_safe(
        f"""
        SELECT id, fecha_analisis, manager, nombre_del_tecnico, pilar, pergunta, nota, status_feedback
        FROM {T_ANALISE}
        """,
        columns=["id", "fecha_analisis", "manager", "nombre_del_tecnico", "pilar", "pergunta", "nota", "status_feedback"],
    )
    pillars_df, err_p = run_query_safe(
        f"SELECT name, weight FROM {T_PILLARS}", columns=["name", "weight"]
    )
    return df, pillars_df, (err or err_p)


df, pillars_df, err = carregar_dados()
mostrar_error_db(err)

if df.empty:
    st.info(t("dashboard_sin_datos"))
    st.stop()

df["fecha"] = pd.to_datetime(df["fecha_analisis"], format=FECHA_ANALISIS_FORMATO_PY, errors="coerce")
df = df.dropna(subset=["fecha"])

if "dash_v" not in st.session_state:
    st.session_state["dash_v"] = 0
v = st.session_state["dash_v"]

KEY_DONUT = f"chart_donut_{v}"
KEY_STATUS = f"chart_status_{v}"
KEY_PILARES = f"chart_pilares_{v}"
KEY_SUPERVISORES = f"chart_supervisores_{v}"
KEY_ANALISTAS = f"chart_analistas_{v}"


def _click_valor(key: str, campo: str) -> str | None:
    estado = st.session_state.get(key)
    if not estado:
        return None
    pontos = estado.get("selection", {}).get("points", [])
    if not pontos:
        return None
    return pontos[0].get(campo)


click_pilar = _click_valor(KEY_PILARES, "y")
click_manager = _click_valor(KEY_SUPERVISORES, "y")
click_tecnico = _click_valor(KEY_ANALISTAS, "y")
click_status = _click_valor(KEY_STATUS, "y") or _click_valor(KEY_DONUT, "label")

# ---------------------------------------------------------------------------
# Filtros (topo da página) — recortam `df` antes de qualquer cálculo, então
# todo o resto da página (KPIs, gráficos, rankings) já reflete o filtro.
# ---------------------------------------------------------------------------
data_min, data_max = df["fecha"].min().date(), df["fecha"].max().date()

fc1, fc2, fc3, fc4, fc5 = st.columns([3, 2, 2, 2, 2])
periodo = fc1.date_input(t("field_periodo_dashboard"), value=(data_min, data_max), min_value=data_min, max_value=data_max, key=f"dash_periodo_{v}")

df_periodo = df
if isinstance(periodo, tuple) and len(periodo) == 2:
    ini, fim = periodo
    df_periodo = df[(df["fecha"].dt.date >= ini) & (df["fecha"].dt.date <= fim)]

managers_opts = [t("opt_todos")] + sorted(df_periodo["manager"].dropna().unique().tolist())
manager_sel = fc2.selectbox(t("field_manager_filtro"), managers_opts, key=f"dash_manager_{v}")

# Cascata: opções de Técnico dependem do Manager escolhido. A chave do widget
# embute `manager_sel` de propósito — trocar o Manager troca a chave, então o
# Streamlit trata o Técnico como um widget novo (volta pra "Todos") em vez de
# tentar validar contra uma lista de opções que já mudou.
df_para_tecnicos = df_periodo if manager_sel == t("opt_todos") else df_periodo[df_periodo["manager"] == manager_sel]
tecnicos_opts = [t("opt_todos")] + sorted(df_para_tecnicos["nombre_del_tecnico"].dropna().unique().tolist())
tecnico_sel = fc3.selectbox(t("field_tecnico_req").replace(" *", ""), tecnicos_opts, key=f"dash_tecnico_{v}_{manager_sel}")

pilares_opts = [t("opt_todos")] + sorted(df_periodo["pilar"].dropna().unique().tolist())
pilar_sel = fc4.selectbox(t("field_pillar"), pilares_opts, key=f"dash_pilar_{v}")

with fc5:
    st.write("")  # alinha o botão com a base dos outros campos
    if st.button(t("btn_limpar_filtros"), help=t("btn_limpar_filtros_help"), use_container_width=True):
        st.session_state["dash_v"] += 1
        st.rerun()

df = df_periodo
if manager_sel != t("opt_todos"):
    df = df[df["manager"] == manager_sel]
if tecnico_sel != t("opt_todos"):
    df = df[df["nombre_del_tecnico"] == tecnico_sel]
if pilar_sel != t("opt_todos"):
    df = df[df["pilar"] == pilar_sel]

# Clique num gráfico funciona como mais um filtro, combinado (E) com os de cima.
if click_pilar:
    df = df[df["pilar"] == click_pilar]
if click_manager:
    df = df[df["manager"] == click_manager]
if click_tecnico:
    df = df[df["nombre_del_tecnico"] == click_tecnico]
if click_status:
    df = df[df["status_feedback"] == click_status]

cliques_ativos = [v_ for v_ in [click_pilar, click_manager, click_tecnico, click_status] if v_]
if cliques_ativos:
    st.caption(t("dashboard_filtro_clique_info", valores=", ".join(cliques_ativos)))

st.divider()

if df.empty:
    st.info(t("dashboard_sin_datos"))
    st.stop()

df["anio"] = df["fecha"].dt.year
df["mes"] = df["fecha"].dt.to_period("M").dt.to_timestamp()

peso_por_pilar = pillars_df.set_index("name")["weight"]
df["peso"] = df["pilar"].map(peso_por_pilar)
df["credito"] = df["nota"].map({"1": 1.0, "0": 0.0})  # 'N/A' -> NaN, excluída do cálculo
df["credito_ponderado"] = df["credito"] * df["peso"]


def nivel_calidad(sub: pd.DataFrame) -> float:
    """Nota 0-10 ponderada pelo peso do pilar — ver docstring do módulo."""
    valid = sub.dropna(subset=["credito", "peso"])
    peso_total = valid["peso"].sum()
    if valid.empty or peso_total == 0:
        return float("nan")
    return valid["credito_ponderado"].sum() / peso_total * 10


def fmt(valor: float, casas: int = 1, sufixo: str = "") -> str:
    if pd.isna(valor):
        return "—"
    return f"{valor:.{casas}f}{sufixo}".replace(".", ",")


def _rgba(hex_cor: str, alpha: float) -> str:
    """Plotly não aceita hex de 8 dígitos (#RRGGBBAA) — precisa de rgba()."""
    r, g, b = int(hex_cor[1:3], 16), int(hex_cor[3:5], 16), int(hex_cor[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _interp_hex(cor_ini: str, cor_fim: str, t_: float) -> str:
    r1, g1, b1 = int(cor_ini[1:3], 16), int(cor_ini[3:5], 16), int(cor_ini[5:7], 16)
    r2, g2, b2 = int(cor_fim[1:3], 16), int(cor_fim[3:5], 16), int(cor_fim[5:7], 16)
    r = round(r1 + (r2 - r1) * t_)
    g = round(g1 + (g2 - g1) * t_)
    b = round(b1 + (b2 - b1) * t_)
    return f"rgb({r},{g},{b})"


def gradiente(cor_ini: str, cor_fim: str, n: int) -> list[str]:
    """N cores interpoladas entre cor_ini e cor_fim — usado nos rankings pra
    dar variação/degradê sem sair da paleta da marca."""
    if n <= 1:
        return [cor_ini]
    return [_interp_hex(cor_ini, cor_fim, i / (n - 1)) for i in range(n)]


def sparkline(anos: list[int], valores: list[float], cor: str, casas: int = 1) -> go.Figure:
    """Mini gráfico anual do card KPI — com rótulo de valor em cada ponto e o
    ano no eixo x."""
    fig = go.Figure(
        go.Scatter(
            x=anos, y=valores, mode="lines+markers+text",
            line=dict(color=cor, width=2), marker=dict(color=cor, size=7),
            fill="tozeroy", fillcolor=_rgba(cor, 0.15),
            text=[fmt(v, casas) for v in valores], textposition="top center",
            textfont=dict(size=13, color=COR_OFFWHITE),
            cliponaxis=False,
        )
    )
    layout = {**_LAYOUT_BASE, "height": 120, "margin": dict(l=10, r=10, t=32, b=22), "showlegend": False}
    fig.update_layout(**layout)
    fig.update_xaxes(visible=True, tickvals=anos, tickformat="d", showgrid=False, zeroline=False, showline=False, color=COR_CINZA)
    fig.update_yaxes(visible=False, range=[0, max(valores) * 1.35 if valores and max(valores) else 1])
    return fig


# ---------------------------------------------------------------------------
# KPIs anuais (últimos até 3 anos com dados) — Nível Calidad / Encaminhados /
# Aplicados
# ---------------------------------------------------------------------------
anios = sorted(df["anio"].unique())
anios_kpi = anios[-3:] if len(anios) > 3 else anios

linhas_kpi = []
for anio in anios_kpi:
    sub = df[df["anio"] == anio]
    sub_id = sub.drop_duplicates("id")
    encaminhados = len(sub_id)
    # % sobre as avaliações não canceladas — cancelada não entra no funil de feedback.
    sub_id_ativos = sub_id[sub_id["status_feedback"] != STATUS_FEEDBACK_CANCELADO]
    aplicados_pct = (
        (sub_id_ativos["status_feedback"] == STATUS_FEEDBACK_CONCLUIDO).mean() * 100
        if not sub_id_ativos.empty else float("nan")
    )
    linhas_kpi.append(
        {"anio": anio, "nivel": nivel_calidad(sub), "encaminhados": encaminhados, "aplicados_pct": aplicados_pct}
    )
serie_anual = pd.DataFrame(linhas_kpi)


def delta_yoy(serie: pd.Series) -> float:
    if len(serie) < 2 or serie.iloc[-2] in (0, None) or pd.isna(serie.iloc[-2]):
        return float("nan")
    return (serie.iloc[-1] - serie.iloc[-2]) / serie.iloc[-2] * 100


def fmt_delta(valor: float) -> str | None:
    """Como fmt(), mas devolve None (sem badge de delta) quando não há ano
    anterior pra comparar — `st.metric` tenta interpretar o sinal do texto,
    então uma string tipo '—' quebraria essa lógica."""
    if pd.isna(valor):
        return None
    return fmt(valor, sufixo="%")


c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        t("kpi_nivel_calidad"),
        fmt(serie_anual["nivel"].iloc[-1]),
        delta=fmt_delta(delta_yoy(serie_anual["nivel"])),
    )
    st.plotly_chart(sparkline(serie_anual["anio"].tolist(), serie_anual["nivel"].tolist(), COR_TEAL), use_container_width=True, config={"displayModeBar": False})

with c2:
    st.metric(
        t("kpi_encaminhados"),
        fmt(serie_anual["encaminhados"].iloc[-1], casas=0),
        delta=fmt_delta(delta_yoy(serie_anual["encaminhados"])),
    )
    st.plotly_chart(sparkline(serie_anual["anio"].tolist(), serie_anual["encaminhados"].tolist(), COR_CIANO, casas=0), use_container_width=True, config={"displayModeBar": False})

with c3:
    st.metric(
        t("kpi_aplicados"),
        fmt(serie_anual["aplicados_pct"].iloc[-1], sufixo="%"),
        delta=fmt_delta(delta_yoy(serie_anual["aplicados_pct"])),
    )
    st.plotly_chart(sparkline(serie_anual["anio"].tolist(), serie_anual["aplicados_pct"].tolist(), COR_ROXO), use_container_width=True, config={"displayModeBar": False})

st.divider()

# ---------------------------------------------------------------------------
# Donut (status por avaliação) + lista de status — clicáveis (filtram o resto
# da página pelo status clicado).
# ---------------------------------------------------------------------------
col_donut, col_status = st.columns([1, 1])

df_id_geral = df.drop_duplicates("id")
contagem_status = df_id_geral["status_feedback"].fillna("—").value_counts()
cores_status = {STATUS_FEEDBACK_PENDIENTE: COR_AZUL, STATUS_FEEDBACK_CONCLUIDO: COR_TEAL, STATUS_FEEDBACK_CANCELADO: COR_CINZA}
cores_donut = [cores_status.get(s, COR_AZUL) for s in contagem_status.index]

with col_donut:
    st.subheader(t("donut_title"), anchor=False)
    fig = go.Figure(
        go.Pie(
            labels=contagem_status.index,
            values=contagem_status.values,
            hole=0.6,
            marker=dict(colors=cores_donut),
            textinfo="percent",
        )
    )
    fig.update_layout(**_LAYOUT_BASE, height=280, legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, on_select="rerun", key=KEY_DONUT)

with col_status:
    st.subheader(t("status_title"), anchor=False)
    fig = go.Figure(
        go.Bar(
            y=contagem_status.index,
            x=contagem_status.values,
            orientation="h",
            marker_color=[cores_status.get(s, COR_AZUL) for s in contagem_status.index],
            text=contagem_status.values,
            textposition="outside",
        )
    )
    fig.update_layout(**_LAYOUT_BASE, height=280)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(visible=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, on_select="rerun", key=KEY_STATUS)

st.divider()

# ---------------------------------------------------------------------------
# Combo mensal: Encaminhados/Aplicados (barras) + Calidad (linha)
# ---------------------------------------------------------------------------
st.subheader(t("combo_title"), anchor=False)

df_id_mes = df.groupby("id").agg(mes=("mes", "min"), status_feedback=("status_feedback", "first")).reset_index()
mensal = df_id_mes.groupby("mes").agg(
    encaminhados=("id", "count"),
    aplicados=("status_feedback", lambda s: (s == STATUS_FEEDBACK_CONCLUIDO).sum()),
).reset_index()
calidad_mes = df.groupby("mes").apply(nivel_calidad, include_groups=False).reset_index(name="calidad")
mensal = mensal.merge(calidad_mes, on="mes").sort_values("mes").tail(12)

fig = go.Figure()
fig.add_bar(x=mensal["mes"], y=mensal["encaminhados"], name=t("kpi_encaminhados"), marker_color=COR_AZUL)
fig.add_bar(x=mensal["mes"], y=mensal["aplicados"], name=t("legend_aplicado"), marker_color=COR_CIANO)
fig.add_trace(
    go.Scatter(
        x=mensal["mes"], y=mensal["calidad"], name=t("kpi_nivel_calidad"),
        mode="lines+markers+text", line=dict(color=COR_OFFWHITE, width=3),
        marker=dict(color=COR_OFFWHITE, size=7), yaxis="y2",
        text=[fmt(v, 0) for v in mensal["calidad"]], textposition="top center",
    )
)
fig.update_layout(
    **_LAYOUT_BASE,
    height=380,
    barmode="group",
    legend=dict(orientation="h", y=1.15),
    yaxis=dict(title=None, gridcolor="rgba(245,243,238,0.08)"),
    yaxis2=dict(overlaying="y", side="right", range=[0, 10], showgrid=False),
    xaxis=dict(tickformat="%b\n%Y"),
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.divider()


def ranking_bar(titulo: str, serie: pd.Series, altura: int, cor_ini: str, cor_fim: str, casas: int = 1, top: int | None = None, key: str | None = None):
    serie = serie.dropna().sort_values(ascending=False)
    if top:
        serie = serie.head(top)
    st.subheader(titulo, anchor=False)
    fig = go.Figure(
        go.Bar(
            y=serie.index,
            x=serie.values,
            orientation="h",
            marker_color=gradiente(cor_ini, cor_fim, len(serie)),
            text=[fmt(v, casas) for v in serie.values],
            textposition="outside",
        )
    )
    fig.update_layout(**_LAYOUT_BASE, height=altura)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(visible=False)
    kwargs = {"on_select": "rerun", "key": key} if key else {}
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, **kwargs)


# ---------------------------------------------------------------------------
# Rankings — Pilares / Supervisores / Reincidência / Analistas. Os três
# primeiros (exceto Reincidência) são clicáveis.
# ---------------------------------------------------------------------------
col_a, col_b = st.columns(2)
with col_a:
    ranking_bar(t("ranking_pilares_title"), df.groupby("pilar").apply(nivel_calidad, include_groups=False), altura=260, cor_ini=COR_CIANO, cor_fim=COR_AZUL, key=KEY_PILARES)
with col_b:
    ranking_bar(t("ranking_supervisores_title"), df.groupby("manager").apply(nivel_calidad, include_groups=False), altura=260, top=15, cor_ini=COR_TEAL, cor_fim=COR_ROXO, key=KEY_SUPERVISORES)

col_c, col_d = st.columns(2)
with col_c:
    falhas_por_pergunta = df[df["nota"] == "0"]["pergunta"].value_counts()
    ranking_bar(t("reincidencia_title"), falhas_por_pergunta, altura=300, casas=0, top=10, cor_ini=COR_VERMELHO, cor_fim=COR_GRAFITE)
with col_d:
    ranking_bar(t("ranking_analistas_title"), df.groupby("nombre_del_tecnico").apply(nivel_calidad, include_groups=False), altura=300, top=15, cor_ini=COR_CIANO, cor_fim=COR_TEAL, key=KEY_ANALISTAS)
