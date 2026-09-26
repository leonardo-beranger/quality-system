"""Cria o primeiro usuário admin num banco novo.

Um banco recém-criado tem o catálogo de pilares/perguntas, mas nenhum usuário —
sem isso ninguém consegue logar. Uso (na raiz do projeto):

    python scripts/create_admin.py --email voce@empresa.com --name "Seu Nome"

Sem --password usa a senha padrão `quality_{ano_atual}` (a mesma de um usuário
novo em Cadastros), que é previsível: defina uma senha própria com --password ou troque-a em
Início depois de entrar. Não sobrescreve nada: se o e-mail já existe, aborta.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core import auth, db  # noqa: E402
from core.config import TABLES, senha_padrao  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria um usuário admin.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="admin")
    parser.add_argument("--password", default=None, help="padrão: quality_{ano_atual}")
    args = parser.parse_args()

    email = args.email.strip().lower()
    senha = args.password or senha_padrao()
    tabela = TABLES["quality_agent"]
    engine = db.get_engine()

    with engine.begin() as conn:
        existe = conn.execute(
            text(f"SELECT 1 FROM {tabela} WHERE lower(email) = :email"), {"email": email}
        ).first()
        if existe:
            print(f"Já existe um usuário com o e-mail {email}. Nada foi alterado.")
            return 1
        proximo_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {tabela}")).scalar()
        conn.execute(
            text(
                f"INSERT INTO {tabela} (id, name, email, status, role, password_hash) "
                "VALUES (:id, :name, :email, 'activate', 'admin', :hash)"
            ),
            {"id": proximo_id, "name": args.name, "email": email, "hash": auth.hash_password(senha)},
        )

    print(f"Admin criado: {email} (id {proximo_id}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
