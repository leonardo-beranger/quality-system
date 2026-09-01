"""Conexão com o banco local SQLite da aplicação.

O caminho do arquivo `.db` NÃO fica hardcoded aqui. Preencha opcionalmente em
`db_config.json` (copie de `db_config.json.example`), na raiz deste projeto:

    {
      "sqlite": {
        "path": "quality_system.db"
      }
    }

Se `db_config.json` não existir, o caminho cai para a variável de ambiente
`QUALITY_DB_PATH` e, por fim, para o padrão `quality_system.db` na raiz do
projeto. Um caminho relativo é resolvido a partir da raiz do projeto (onde
este arquivo está).

Todo o resto do projeto importa apenas `get_engine()` / `run_query()` /
`run_statement()` deste módulo — nenhuma outra página conhece o caminho do
arquivo `.db`. Na primeira conexão, `get_engine()` também garante que as
tabelas (ver `SCHEMA`) e o catálogo de critérios (`perguntas`) existam.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import CRITERIOS, TABLES, iter_criterios

# core/db.py -> a raiz do projeto (onde fica quality_system.db e db_config.json)
# é um nível acima daqui, já que db.py mora dentro do pacote core/.
_PROJECT_ROOT = Path(__file__).parent.parent

# O driver sqlite3 do stdlib deixou de adaptar `datetime`/`date` para texto por
# padrão (aviso de depreciação desde o Python 3.12) — os módulos da app passam
# esses tipos como parâmetro (`datetime.now()` em auth.py/registros.py/
# analisis.py), então os adaptadores são registrados explicitamente aqui,
# uma única vez, em vez de depender do comportamento default do driver.
sqlite3.register_adapter(datetime, lambda v: v.isoformat(sep=" "))
sqlite3.register_adapter(date, lambda v: v.isoformat())

_CONFIG_CANDIDATES = [
    _PROJECT_ROOT / "db_config.json",
    Path.home() / ".streamlit" / "db_config.json",
]


def _load_json_config() -> dict:
    """Lê o primeiro `db_config.json` encontrado. Retorna {} se não existir/for inválido."""
    for path in _CONFIG_CANDIDATES:
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f).get("sqlite", {})
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def _get_db_path() -> Path:
    """Resolve o caminho do arquivo `.db` a partir de db_config.json ou variável de ambiente."""
    cfg = _load_json_config()
    caminho = cfg.get("path") or os.getenv("QUALITY_DB_PATH", "quality_system.db")
    path = Path(caminho)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path


def describe_connection() -> dict:
    """Parâmetros de conexão em uso — para diagnóstico na tela."""
    path = _get_db_path()
    return {"arquivo": str(path), "existe": path.exists()}


# ---------------------------------------------------------------------------
# Schema — criado/atualizado automaticamente na primeira conexão do processo.
# ---------------------------------------------------------------------------
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLES['quality_agent']} (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'activate',
    password_hash TEXT,
    role TEXT DEFAULT 'viewer',
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS {TABLES['managers']} (
    id_manager INTEGER PRIMARY KEY,
    manager TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'activate'
);

CREATE TABLE IF NOT EXISTS {TABLES['analysts']} (
    id_analista INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    id_manager INTEGER,
    manager TEXT,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'activate',
    region TEXT,
    updated_on TEXT
);

CREATE TABLE IF NOT EXISTS {TABLES['pillars']} (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    weight REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS {TABLES['questions']} (
    id INTEGER PRIMARY KEY,
    pillar_id INTEGER NOT NULL REFERENCES {TABLES['pillars']}(id),
    label TEXT NOT NULL,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS {TABLES['ticket_analysis']} (
    id TEXT,
    id_number TEXT,
    id_manager INTEGER,
    id_analista INTEGER,
    id_analista_quality INTEGER,
    question_id INTEGER,
    fecha_analisis TEXT,
    analista_quality TEXT,
    ticketnumber TEXT,
    idioma TEXT,
    region TEXT,
    manager TEXT,
    nombre_del_tecnico TEXT,
    pilar TEXT,
    pergunta TEXT,
    nota TEXT,
    comentario TEXT,
    status_feedback TEXT
);
CREATE INDEX IF NOT EXISTS idx_ticket_analysis_id ON {TABLES['ticket_analysis']} (id);

CREATE TABLE IF NOT EXISTS {TABLES['general_comments']} (
    id TEXT,
    comentario TEXT,
    fecha TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {TABLES['activity_log']} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla TEXT NOT NULL,
    registro_id TEXT NOT NULL,
    accion TEXT NOT NULL,
    columna TEXT NOT NULL,
    valor_anterior TEXT,
    valor_nuevo TEXT,
    usuario TEXT,
    fecha TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _seed_pillars_and_questions(conn) -> None:
    """Popula `pillars`/`questions` a partir de CRITERIOS (config.py), se vazias.

    Depois do seed inicial as tabelas são a fonte da verdade (a página
    "Perguntas" cadastra/edita pilares e perguntas direto no banco) —
    CRITERIOS só serve pra dar um ponto de partida num banco novo.
    """
    if not conn.execute(text(f"SELECT COUNT(*) FROM {TABLES['pillars']}")).scalar():
        for pillar_id, grupo in enumerate(CRITERIOS, start=1):
            conn.execute(
                text(f"INSERT INTO {TABLES['pillars']} (id, name, weight) VALUES (:id, :name, :weight)"),
                {"id": pillar_id, "name": grupo["pilar"], "weight": grupo["peso"]},
            )

    if not conn.execute(text(f"SELECT COUNT(*) FROM {TABLES['questions']}")).scalar():
        pillar_id_por_nome = {grupo["pilar"]: i for i, grupo in enumerate(CRITERIOS, start=1)}
        for question_id, (_codigo, rotulo, descricao, pilar, _peso) in enumerate(iter_criterios(), start=1):
            conn.execute(
                text(
                    f"INSERT INTO {TABLES['questions']} (id, pillar_id, label, description, active) "
                    "VALUES (:id, :pillar_id, :label, :description, 1)"
                ),
                {"id": question_id, "pillar_id": pillar_id_por_nome[pilar], "label": rotulo, "description": descricao},
            )


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """Cria (uma única vez por sessão de servidor) o engine SQLAlchemy do SQLite local."""
    path = _get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{path}",
        # Streamlit atende requisições em threads diferentes; sem isso o
        # sqlite3 recusa reusar a conexão fora da thread onde foi criada.
        connect_args={"check_same_thread": False},
    )

    with engine.begin() as conn:
        # WAL permite leituras concorrentes enquanto uma escrita está em
        # andamento — relevante porque várias páginas/sessões do Streamlit
        # podem consultar ao mesmo tempo que alguém registra uma avaliação.
        conn.execute(text("PRAGMA journal_mode = WAL"))
        conn.execute(text("PRAGMA foreign_keys = ON"))
        for statement in SCHEMA.strip().split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        _seed_pillars_and_questions(conn)

    return engine


def reset_engine() -> None:
    """Descarta o engine em cache — use após editar `db_config.json`.

    O engine é cacheado com `st.cache_resource`, então mudar o caminho do
    arquivo `.db` no JSON não tem efeito até o cache ser limpo (ou o servidor
    reiniciado).
    """
    get_engine.clear()


@contextmanager
def get_connection():
    """Context manager para uma conexão transacional (usado em INSERT/UPDATE/DELETE)."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Executa um SELECT e retorna um DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def run_statement(sql: str, params: dict | None = None) -> None:
    """Executa um INSERT/UPDATE/DELETE dentro de uma transação."""
    with get_connection() as conn:
        conn.execute(text(sql), params or {})


def test_connection() -> tuple[bool, str]:
    """Testa a conexão com o banco local. Usado na home page para diagnóstico rápido."""
    try:
        run_query("SELECT 1")
        return True, "Conexão com o banco local estabelecida com sucesso."
    except Exception as exc:  # noqa: BLE001 - queremos mostrar qualquer erro ao usuário
        return False, str(exc)


# Assinaturas de erro -> chave de tradução com a causa provável. A ordem importa:
# a primeira que casar é usada.
_ERROR_HINTS = [
    (("unable to open database file",), "hint_sqlite_arquivo"),
    (("database is locked",), "hint_sqlite_locked"),
    (("readonly database", "attempt to write a readonly database"), "hint_sqlite_readonly"),
    (("no such table",), "hint_tabla_inexistente"),
    (("no such column",), "hint_columna_inexistente"),
]


def diagnose_error(error: str | None) -> str | None:
    """Classifica a mensagem de erro do driver e devolve a chave i18n da causa provável.

    O texto cru do sqlite3/SQLAlchemy diz *o que* falhou mas não *o que fazer* —
    esta função traduz as assinaturas mais comuns em uma orientação acionável.
    Devolve None se não reconhecer.
    """
    if not error:
        return None

    texto = error.lower()
    for assinaturas, chave in _ERROR_HINTS:
        if any(assinatura.lower() in texto for assinatura in assinaturas):
            return chave
    return None


def run_query_safe(sql: str, params: dict | None = None, columns: list[str] | None = None):
    """Como run_query, mas nunca levanta exceção.

    As páginas usam esta versão para carregar dados de apoio (dropdowns, listas):
    o formulário deve sempre renderizar primeiro, mesmo que o banco esteja
    indisponível — a tentativa de conexão só acontece depois, e um erro aqui vira
    apenas um aviso na tela em vez de derrubar a página inteira.

    Retorna (DataFrame, mensagem_de_erro | None). Em caso de falha, o DataFrame
    vem vazio, com as colunas informadas em `columns` (se houver).
    """
    try:
        return run_query(sql, params), None
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer erro de conexão
        return pd.DataFrame(columns=columns or []), str(exc)


def siguiente_id(tabla: str, columna: str) -> tuple[int | None, str | None]:
    """Calcula MAX(columna) + 1 para tablas cuya PK no es autoincremental por escritura manual.

    Varias tablas de catálogo (quality_agent.id, managers.id_manager,
    analysts.id_analista, questions.id) exigen que la app calcule y escriba
    la PK a mano — sin esto, un INSERT que no la incluya guarda la fila con
    id NULL.

    Devuelve (siguiente_id, error). Si la tabla está vacía, devuelve 1.
    """
    df, error = run_query_safe(f"SELECT MAX({columna}) AS ultimo FROM {tabla}", columns=["ultimo"])
    if error:
        return None, error

    ultimo = df.iloc[0]["ultimo"] if not df.empty else None
    if ultimo is None or pd.isna(ultimo):
        return 1, None
    return int(ultimo) + 1, None


def run_statement_safe(sql: str, params: dict | None = None) -> str | None:
    """Como run_statement, mas retorna a mensagem de erro em vez de levantar exceção."""
    try:
        run_statement(sql, params)
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def run_transaction_safe(operaciones: list[tuple[str, dict]]) -> str | None:
    """Executa várias sentenças em UMA única transação — tudo ou nada.

    Usado no registro/edição de uma avaliação, que grava 15 linhas (uma por
    critério) mais o comentário geral e o alerta. Com um `run_statement_safe`
    por linha, cada sentença teria seu próprio commit e uma falha no meio
    deixaria a avaliação gravada pela metade — impossível de consolidar
    corretamente no Historial. Aqui, qualquer erro desfaz o conjunto inteiro.

    Retorna a mensagem de erro, ou None em caso de sucesso.
    """
    try:
        with get_connection() as conn:
            for sql, params in operaciones:
                conn.execute(text(sql), params or {})
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)
