"""
Configuração central do projeto: nomes de tabelas do banco e catálogo de critérios.

Ajuste os nomes em TABLES se quiser renomear alguma tabela do schema local.
Isso evita ter que caçar strings de SQL espalhadas pelas páginas.
"""

from datetime import date

APP_TITLE = "Quality Metrics"

# Nomes das tabelas do banco SQLite local (schema criado por db.py).
TABLES = {
    "quality_agent": "quality_agent",
    "managers": "managers",
    "analysts": "analysts",
    "ticket_analysis": "ticket_analysis",   # transacional, 1 linha por critério (formato longo)
    "general_comments": "general_comments",
    "pillars": "pillars",                   # catálogo de pilares (nome em inglês + peso)
    "questions": "questions",               # catálogo de critérios (perguntas em português), com flag `active`
    "activity_log": "activity_log",         # auditoria: 1 linha por coluna alterada
}

# Colunas reais da tabela transacional `ticket_analysis` (formato longo: 1 linha
# por pergunta/critério). Esta é a fonte da verdade do schema para todo o projeto
# — todas as páginas usam exatamente estes nomes no SQL.
#
#   id ................ código completo da avaliação (o "IDQ" exibido na
#                       interface, ex.: 'IDQ12737')
#   id_number ......... apenas a parte numérica desse código (ex.: '12737'),
#                       sem o prefixo
#   id_manager/id_analista/id_analista_quality .. FKs das dimensões, a app escreve.
#   question_id ....... FK para `questions.id` (o critério avaliado nessa linha)
#   pergunta .......... rótulo do critério avaliado, congelado no momento do registro
#                       (não muda retroativamente se o rótulo da pergunta for editado depois)
#   nombre_del_tecnico  técnico avaliado
#   ticketnumber ...... número do ticket
#   fecha_analisis .... data/hora do registro. ATENÇÃO: é texto, não timestamp —
#                       formato 'DD/MM/YYYY HH24:MI' (ex.: '21/01/2025 09:09'). Use
#                       sempre `sql_fecha_analisis()` para filtrar/ordenar por
#                       ela em SQL, e `FECHA_ANALISIS_FORMATO_PY` para escrevê-la.
#   status_feedback ... situação do feedback; 'Cancelado' marca avaliação cancelada
#
# O peso NÃO é uma coluna da tabela: vem de `questions.weight` e a nota final
# é ponderada na aplicação.
ANALISE_COLUMNS = [
    "id", "id_number", "id_manager", "id_analista",
    "id_analista_quality", "question_id", "fecha_analisis",
    "analista_quality", "ticketnumber", "idioma", "region", "manager",
    "nombre_del_tecnico", "pilar", "pergunta", "nota",
    "comentario", "status_feedback",
]

# `fecha_analisis` é armazenada como texto, não datetime — comparar/ordenar
# direto nela dá comparação lexicográfica silenciosamente errada (ex.:
# '05/03/2025' viria "menor" que '21/01/2025', porque compara caractere a
# caractere pelo dia primeiro). Formato observado: 'DD/MM/YYYY HH:MM'.
FECHA_ANALISIS_FORMATO_PY = "%d/%m/%Y %H:%M"

# Formato que `sql_fecha_analisis()` produz ('YYYY-MM-DD HH:MM') — usado para
# formatar os parâmetros de data/hora ao montar o WHERE em torno dela.
FECHA_ANALISIS_FORMATO_SQL_PY = "%Y-%m-%d %H:%M"


def sql_fecha_analisis(coluna: str = "fecha_analisis") -> str:
    """Expressão SQL que reordena `fecha_analisis` ('DD/MM/YYYY HH:MM') para
    'YYYY-MM-DD HH:MM' — nesse formato a comparação/ordenação de texto já é
    cronológica, sem precisar converter para um tipo datetime real.

    Use esta expressão em todo WHERE/ORDER BY/MAX() sobre `fecha_analisis` —
    nunca compare a coluna crua com uma data, e nunca a ordene como texto no
    formato original. Os parâmetros comparados contra esta expressão devem
    estar formatados com `FECHA_ANALISIS_FORMATO_SQL_PY`.
    """
    return (
        f"(substr({coluna}, 7, 4) || '-' || substr({coluna}, 4, 2) || '-' || "
        f"substr({coluna}, 1, 2) || ' ' || substr({coluna}, 12, 5))"
    )


# Valores de `status_feedback` usados pela aplicação — sempre em inglês,
# independente do idioma da interface (mesma convenção já usada pro nome dos
# pilares): ciclo de vida de uma avaliação — Registrar cria como PENDING
# (início); aplicar o feedback ao técnico marca como APPLIED (fim do
# processo); Cancelar marca como CANCELLED (reversível, fora do ciclo normal).
STATUS_FEEDBACK_PENDIENTE = "Pending"
STATUS_FEEDBACK_CONCLUIDO = "Applied"
STATUS_FEEDBACK_CANCELADO = "Cancelled"

# Limite máximo do filtro de período no Historial (consulta em tela e exportação).
# A tabela `ticket_analysis` tem volume muito alto: sem esse teto, uma consulta
# aberta seria lenta/pesada e a exportação ficaria impraticável.
MAX_MESES_PERIODO = 2

# Teto de linhas trazidas por consulta no Historial — rede de segurança para o
# caso de um período de 2 meses ainda retornar volume excessivo.
MAX_FILAS_CONSULTA = 200_000

STATUS_OPTIONS = ["activate", "deactivated"]

ROLE_OPTIONS = ["admin", "viewer"]

IDIOMA_OPTIONS = ["Español", "Português", "English"]

REGION_OPTIONS = ["Hispano", "Brasil"]


def senha_padrao(ano: int | None = None) -> str:
    """Senha padrão atribuída a um `quality_agent` novo: 'quality_{ano_atual}'.

    O admin precisa comunicar essa senha ao novo usuário — não há fluxo de
    "esqueci minha senha" nesta app, então o login é sempre feito com bcrypt
    sobre o hash gravado no cadastro.
    """
    return f"quality_{ano or date.today().year}"


# Critérios padrão de avaliação, agrupados por pilar (nome em inglês, peso do
# pilar) — usados apenas para popular as tabelas `pillars`/`questions` na
# primeira execução (banco vazio). Depois do seed inicial, a fonte da verdade
# passa a ser o banco: a página "Perguntas" permite cadastrar/editar pilares
# (nome, peso) e perguntas (ativar/desativar, vincular a um pilar) sem tocar
# neste arquivo. Nome do pilar em inglês, rótulo/descrição da pergunta em
# português — é o padrão adotado no app.
CRITERIOS = [
    {
        "pilar": "Communication",
        "peso": 2,
        "criterios": [
            ("estado", "Estado", "Mudança para 'EN CURSO' em até 15 min após ser assignado."),
            ("validacion", "Validação", "Validação da resolução com o cliente (tentativas de contato registradas)."),
            ("fup", "FUP", "Follow-up periódico com o cliente, registrado no ticket."),
            ("validacion_n1", "Validação N1", "Contato para validar N1 e descartar falha de energia."),
        ],
    },
    {
        "pilar": "Standard",
        "peso": 1.5,
        "criterios": [
            ("templates_sn", "Templates SN", "Uso dos templates padrão do ServiceNow."),
            ("tsdanc", "TSDANC", "Registro do TSDANC a cada atualização da tratativa."),
        ],
    },
    {
        "pilar": "Diagnosis",
        "peso": 2,
        "criterios": [
            ("diagnostico_preciso", "Diagnóstico preciso", "Diagnóstico coerente com a reclamação do cliente."),
            ("diagnostico_enviado", "Diagnóstico enviado", "Diagnóstico enviado ao cliente em até 60 min."),
            ("direccion_correcta", "Direção correta", "Ação correta tomada em até 60 min (N2, Vendor Task, campo etc.)."),
        ],
    },
    {
        "pilar": "Technical",
        "peso": 3,
        "criterios": [
            ("analisis_completo", "Análise Completa", "Análise técnica completa e coerente, com testes documentados."),
            ("clasificacion_coherente", "Classificação Coerente", "Classificação do incidente coerente com os sintomas."),
            ("evidencia_documentada", "Evidência Documentada", "Evidências técnicas mínimas registradas no ticket."),
        ],
    },
    {
        "pilar": "Solution",
        "peso": 1.5,
        "criterios": [
            ("causa_documentada", "Causa Documentada", "Causa, subcausa e evidências finais documentadas corretamente."),
            ("cierre_adecuado", "Fechamento Adequado", "Campos de resolução e RFO completos."),
            ("particularidad_registrada", "Particularidade Registrada", "Particularidades de validação registradas no ticket."),
        ],
    },
]


def iter_criterios():
    """Itera (codigo, rotulo, descricao, pilar, peso) para todos os critérios do seed."""
    for grupo in CRITERIOS:
        for codigo, rotulo, descricao in grupo["criterios"]:
            yield codigo, rotulo, descricao, grupo["pilar"], grupo["peso"]


NOTA_OPTIONS = ["N/A", "0", "1"]
