"""Popula um banco VAZIO com dados de demonstração (100% fictícios).

Gera 10 supervisores, 100 técnicos e 3 analistas de qualidade, mais 13 contas
viewer (uma por supervisor e por analista, senha padrão `quality_{ano}`) e entre
300 e 700 avaliações espalhadas de 2024-01-01 a 2026-08-31. Semente fixa:
sempre gera os mesmos dados. Uso (na raiz do projeto, depois de criar o admin):

    python scripts/create_admin.py --email voce@empresa.com
    python scripts/seed_demo_data.py

Só adiciona. Se já houver supervisores ou técnicos cadastrados, aborta sem
tocar em nada — nunca apaga dados existentes.
"""

import random
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core import auth, db  # noqa: E402
from core.config import (  # noqa: E402
    FECHA_ANALISIS_FORMATO_PY,
    IDIOMA_OPTIONS,
    REGION_OPTIONS,
    STATUS_FEEDBACK_CANCELADO,
    STATUS_FEEDBACK_CONCLUIDO,
    STATUS_FEEDBACK_PENDIENTE,
    TABLES,
    senha_padrao,
)

random.seed(42)

FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Gabriela", "Hugo",
    "Isabela", "João", "Karina", "Lucas", "Mariana", "Nicolás", "Olivia",
    "Pedro", "Renata", "Sergio", "Tatiana", "Vitor", "Camila", "Rodrigo",
    "Fernanda", "Marcelo", "Patricia", "Eduardo", "Luciana", "Rafael",
    "Beatriz", "Gustavo", "Daniela", "Thiago", "Paula", "André", "Sofia",
]
LAST_NAMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa", "Rodrigues",
    "Almeida", "Nascimento", "Lima", "Araújo", "Fernandes", "Carvalho",
    "Gomes", "Martins", "Rocha", "Ribeiro", "Alves", "Monteiro", "Cardoso",
    "Barbosa", "Freitas", "Pinto", "Moreira", "Correia", "Teixeira", "Dias",
    "Vieira", "Castro", "Campos",
]

DATA_INI = datetime(2024, 1, 1)
DATA_FIM = datetime(2026, 8, 31, 23, 59)
NOTA_PESOS = ["1"] * 7 + ["0"] * 2 + ["N/A"]  # 70% ok, 20% falha, 10% N/A


def gerar_nomes(qtd: int, usados: set[str]) -> list[str]:
    nomes = []
    while len(nomes) < qtd:
        nome = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if nome in usados:
            continue
        usados.add(nome)
        nomes.append(nome)
    return nomes


def email_de(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return sem_acento.lower().replace(" ", ".") + "@empresa.com"


def status_para(fecha: datetime) -> str:
    """Avaliações antigas já tiveram o feedback tratado; as recentes ficam pendentes."""
    idade_dias = (DATA_FIM - fecha).days
    if idade_dias < 30:
        return STATUS_FEEDBACK_PENDIENTE if random.random() < 0.85 else STATUS_FEEDBACK_CANCELADO
    sorteio = random.random()
    if sorteio < 0.70:
        return STATUS_FEEDBACK_CONCLUIDO
    if sorteio < 0.90:
        return STATUS_FEEDBACK_PENDIENTE
    return STATUS_FEEDBACK_CANCELADO


def main() -> int:
    engine = db.get_engine()
    T_AGENT = TABLES["quality_agent"]
    T_MANAGERS = TABLES["managers"]
    T_ANALYSTS = TABLES["analysts"]
    T_ANALISE = TABLES["ticket_analysis"]

    with engine.begin() as conn:
        ocupados = conn.execute(
            text(f"SELECT (SELECT COUNT(*) FROM {T_MANAGERS}) + (SELECT COUNT(*) FROM {T_ANALYSTS})")
        ).scalar()
        if ocupados:
            print("Já existem supervisores/técnicos cadastrados. Abortado, nada foi alterado.")
            return 1

        usados: set[str] = set()
        managers = [
            {"id_manager": i, "manager": nome, "email": email_de(nome), "status": "activate"}
            for i, nome in enumerate(gerar_nomes(10, usados), start=1)
        ]
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tecnicos = []
        for i, nome in enumerate(gerar_nomes(100, usados), start=1):
            mgr = random.choice(managers)
            tecnicos.append({
                "id_analista": i, "name": nome, "id_manager": mgr["id_manager"],
                "manager": mgr["manager"], "email": email_de(nome), "status": "activate",
                "region": random.choice(REGION_OPTIONS), "updated_on": agora,
            })

        conn.execute(
            text(f"INSERT INTO {T_MANAGERS} (id_manager, manager, email, status) VALUES (:id_manager, :manager, :email, :status)"),
            managers,
        )
        conn.execute(
            text(
                f"INSERT INTO {T_ANALYSTS} (id_analista, name, id_manager, manager, email, status, region, updated_on) "
                "VALUES (:id_analista, :name, :id_manager, :manager, :email, :status, :region, :updated_on)"
            ),
            tecnicos,
        )

        # Contas viewer: 1 por supervisor + 3 analistas de qualidade (avaliadores).
        proximo_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {T_AGENT}")).scalar()
        hash_padrao = auth.hash_password(senha_padrao())
        avaliadores = gerar_nomes(3, usados)
        contas = [{"name": m["manager"], "email": m["email"]} for m in managers]
        contas += [{"name": nome, "email": email_de(nome)} for nome in avaliadores]
        for offset, conta in enumerate(contas):
            conn.execute(
                text(
                    f"INSERT INTO {T_AGENT} (id, name, email, status, role, password_hash) "
                    "VALUES (:id, :name, :email, 'activate', 'viewer', :hash)"
                ),
                {"id": proximo_id + offset, **conta, "hash": hash_padrao},
            )
        avaliadores_rows = [
            {"id": proximo_id + len(managers) + i, "name": nome} for i, nome in enumerate(avaliadores)
        ]

        questions = conn.execute(
            text(
                f"SELECT q.id, p.name AS pillar, q.label FROM {TABLES['questions']} q "
                f"JOIN {TABLES['pillars']} p ON p.id = q.pillar_id WHERE q.active = 1"
            )
        ).mappings().all()

        n_avaliacoes = random.randint(300, 700)
        intervalo = int((DATA_FIM - DATA_INI).total_seconds())
        linhas = []
        for n in range(n_avaliacoes):
            tecnico = random.choice(tecnicos)
            qa = random.choice(avaliadores_rows)
            numero = 10_001 + n
            fecha = DATA_INI + timedelta(seconds=random.randint(0, intervalo))
            ticket = f"TK{random.randint(100000, 999999)}"
            idioma = random.choice(IDIOMA_OPTIONS)
            status = status_para(fecha)
            for q in questions:
                linhas.append({
                    "id": f"IDQ{numero}", "id_number": str(numero),
                    "id_manager": tecnico["id_manager"], "id_analista": tecnico["id_analista"],
                    "id_analista_quality": qa["id"], "question_id": q["id"],
                    "fecha_analisis": fecha.strftime(FECHA_ANALISIS_FORMATO_PY),
                    "analista_quality": qa["name"], "ticketnumber": ticket, "idioma": idioma,
                    "region": tecnico["region"], "manager": tecnico["manager"],
                    "nombre_del_tecnico": tecnico["name"], "pilar": q["pillar"],
                    "pergunta": q["label"], "nota": random.choice(NOTA_PESOS),
                    "comentario": "", "status_feedback": status,
                })

        conn.execute(
            text(
                f"INSERT INTO {T_ANALISE} "
                "(id, id_number, id_manager, id_analista, id_analista_quality, question_id, "
                "fecha_analisis, analista_quality, ticketnumber, idioma, region, manager, "
                "nombre_del_tecnico, pilar, pergunta, nota, comentario, status_feedback) VALUES "
                "(:id, :id_number, :id_manager, :id_analista, :id_analista_quality, :question_id, "
                ":fecha_analisis, :analista_quality, :ticketnumber, :idioma, :region, :manager, "
                ":nombre_del_tecnico, :pilar, :pergunta, :nota, :comentario, :status_feedback)"
            ),
            linhas,
        )

    print(
        f"Supervisores: {len(managers)} | Técnicos: {len(tecnicos)} | Contas viewer: {len(contas)} | "
        f"Avaliações: {n_avaliacoes} ({len(linhas)} linhas)"
    )
    print(f"Senha padrão das contas viewer: {senha_padrao()} (troque em produção).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
