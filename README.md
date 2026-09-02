# Quality System

Migração dos formulários VBA de `monitoreo_calidad_v2.xlsm` para um app Streamlit
multipage, com um banco **SQLite local** (arquivo `.db` na própria máquina —
sem servidor externo). Textos em Espanhol por padrão, com seletor de idioma
(Spanish/Portuguese/English) na barra lateral. Tema padrão: dark, com a
paleta de marca (`.streamlit/config.toml`).

Login por `role`: `admin` vê todas as páginas (Cadastros, Perguntas, Análises
completo, Eliminar); `viewer` (inclui supervisores) vê Início, Dashboard,
Análises (apenas Registrar) e Histórico de Análises. Ordem fixa do menu:
Início → Dashboard → Cadastros → Perguntas → Análises → Histórico (as duas do
meio somem pro viewer).

## Como rodar

```bash
pip install -r requirements.txt
streamlit run Inicio.py
```

Não precisa configurar nada: na primeira execução, `db.py` cria o arquivo
`quality_system.db` (na raiz do projeto) e todas as tabelas automaticamente.
Para usar outro caminho, veja "Banco de dados" abaixo.

## Estrutura

```
quality_system/
├── Inicio.py                        # Entrypoint: st.set_page_config + seletor de idioma + st.navigation
├── db_config.json                   # Caminho do arquivo .db, opcional (não versionar — está no .gitignore)
├── db_config.json.example           # Template (copie para db_config.json)
├── requirements.txt
├── assets/
│   ├── logo.png                     # Logo fixado no rodapé da sidebar
│   └── favicon.png                  # Ícone da aba do navegador (page_icon)
├── .streamlit/
│   └── config.toml                  # Tema dark + paleta de marca
├── core/                            # Infra do app — nada aqui conhece páginas específicas
│   ├── db.py                        # Conexão genérica com o SQLite local (SQLAlchemy) + criação do schema
│   ├── config.py                    # Nomes de tabelas + catálogo padrão de critérios/pilares (seed)
│   ├── auth.py                      # Login, sessão (cookie), hash de senha
│   ├── i18n.py                      # Textos ES/PT/EN + seletor de idioma (sidebar)
│   ├── log.py                       # Auditoria (activity_log) — 1 linha por coluna alterada
│   └── ui.py                        # Helpers visuais compartilhados (tema, logo, erro de conexão)
└── views/
    ├── inicio.py                    # Conteúdo da página inicial
    ├── dashboard.py                 # Indicadores de qualidade — admin e viewer
    ├── registros.py                 # Quality Agent + Manager + Analistas (3 abas) — admin
    ├── questions.py                 # Cadastro de pilares/perguntas (2 abas) — admin
    ├── analisis.py                  # Registrar + Editar + Aplicar Feedback + Cancelar + Eliminar Análise (5 abas)
    └── historial_analisis.py        # Histórico consolidado, filtros e exportação CSV/Excel
```

Páginas importam a infra como `from core.db import ...`, `from core.auth import ...` etc. —
`core/` é um pacote Python normal (tem `__init__.py`), não precisa instalar nada
à parte para isso funcionar.

As páginas `Registros` e `Analisis` usam `st.tabs()` para agrupar os formulários
relacionados em uma única página com abas horizontais — mesmo padrão usado em
`Claude_helper/export_BI_reports/app.py` (Workspaces / Reports / Exportar / Excluir).

### Por que `st.navigation` em vez de `pages/`

A navegação usa `st.navigation`/`st.Page` (Inicio.py), não a convenção de pasta
`pages/`. Motivo: com a pasta `pages/`, cada clique no menu lateral navega para
uma URL diferente e o navegador faz um carregamento de documento completo —
isso cria uma **sessão nova** do Streamlit a cada página, e qualquer escolha
guardada em `st.session_state` (como o idioma) se perde ao trocar de página.
Com `st.navigation`, a troca de página acontece dentro da mesma sessão
contínua, então o idioma (e qualquer outro estado) vale para todas as páginas.

## Banco de dados — SQLite local

A conexão é **genérica** (`db.py`): nenhuma página conhece o caminho do
arquivo `.db` diretamente — todas usam apenas `run_query()`/`run_statement()`
(ou as versões `_safe`). Por padrão, o banco fica em `quality_system.db`, na
raiz do projeto, criado automaticamente (schema + índices) na primeira
conexão do processo.

Para usar outro caminho (ex.: fora do OneDrive, ou num disco dedicado), copie
`db_config.json.example` para `db_config.json` na raiz do projeto e preencha:

```json
{
  "sqlite": {
    "path": "quality_system.db"
  }
}
```

Um caminho relativo é resolvido a partir da raiz do projeto; um caminho
absoluto é usado como está. `db_config.json` está no `.gitignore` (não é
versionado). Se o arquivo não existir, o caminho cai para a variável de
ambiente `QUALITY_DB_PATH` e, por fim, para o padrão `quality_system.db`.

`db.py` também procura `db_config.json` em `%USERPROFILE%\.streamlit\` como
segundo caminho — útil para manter o arquivo `.db` fora do OneDrive (evita
sincronizar um arquivo binário que muda a cada gravação).

Todas as páginas usam `run_query_safe()` / `run_statement_safe()` (em vez das
versões que levantam exceção): o layout do formulário é sempre desenhado
primeiro; a tentativa de conexão acontece a seguir, e se falhar aparece apenas
um aviso amarelo — a página nunca fica em branco/travada esperando o banco.

O botão **Recargar configuración** (página Inicio) descarta o engine
cacheado, necessário para aplicar mudanças em `db_config.json` sem reiniciar
o servidor.

## Idioma

`i18n.py` centraliza todos os textos em Spanish/Portuguese/English. O seletor
(`render_language_selector()`) é chamado **uma única vez**, no entrypoint
`Inicio.py`, antes de `st.navigation(...).run()`. Cada página em `views/`
importa apenas `t("chave")` para exibir o texto no idioma escolhido. A escolha
fica em `st.session_state["idioma"]` e, graças ao `st.navigation`, vale para
todas as páginas da sessão.

## Login e papéis (admin / viewer)

`quality_agent.role` guarda `'admin'` ou `'viewer'`. Um usuário novo (aba
Quality Agent, em Cadastros) recebe automaticamente a senha padrão
`quality_{ano_atual}` (ex.: `quality_2026`, ver `config.senha_padrao()`) — não
há fluxo de "esqueci minha senha"; o admin precisa avisar essa senha ao
usuário para o primeiro acesso.

`viewer` vê Início, Dashboard, Análises (apenas a aba Registrar) e Histórico
de Análises — cada página/aba admin (`registros.py`, `questions.py`, e as
abas Editar/Aplicar Feedback/Cancelar/Eliminar de `analisis.py`) também se protege sozinha
(`if usuario_actual()["role"] != "admin": st.stop()`), então acessar a URL
direto não contorna a restrição. `dashboard.py` e `historial_analisis.py` são
só leitura e não têm esse guard — abertos pra `admin` e `viewer`.

Supervisores (cadastrados como `managers`, tabela de referência sem login)
também recebem uma conta `quality_agent` própria com `role = 'viewer'`, pra
poderem entrar e ver o Dashboard/Histórico — são dois cadastros distintos
(um em `managers`, outro em `quality_agent`) que só coincidem no nome/e-mail.

A sessão sobrevive a um F5 via uma cookie assinada (HMAC) gravada com um
`<script>` síncrono dentro de um iframe (`components.html`) que, depois de
gravar/apagar a cookie, dispara `window.top.location.reload()` — usar
`CookieManager.set()/.delete()` (biblioteca `extra_streamlit_components`)
diretamente mostrou não confirmar a escrita a tempo do rerun do Streamlit.

## Tabelas do banco local

Os nomes de tabela usados estão centralizados em `config.py` (`TABLES`), todos
em inglês — o schema (criado automaticamente por `db.py` na primeira conexão)
segue exatamente esses nomes. Ajuste `TABLES` se quiser renomear alguma
tabela.

- `quality_agent (id, name, email, status, password_hash, role, last_login)`
- `managers (id_manager, manager, email, status)`
- `analysts (id_analista, name, id_manager, manager, email, status, region, updated_on)`
- `pillars (id, name, weight)` — catálogo de pilares, gerenciado pela página
  **Perguntas → Pilares** (admin). Nome em **inglês** por convenção; o peso é
  usado para ponderar a nota final.
- `questions (id, pillar_id, label, description, active)` — catálogo de
  critérios de avaliação, gerenciado pela página **Perguntas → Perguntas**
  (admin). `pillar_id` é FK para `pillars.id`. Rótulo/descrição em
  **português**. Só perguntas `active = 1` entram numa avaliação **nova**;
  uma pergunta desativada continua editável em avaliações que já a
  responderam (ver "Editar Análise" abaixo). Ambas as tabelas são populadas
  uma vez, na primeira conexão, a partir de `config.CRITERIOS` (5 pilares
  padrão) — depois disso o banco é a fonte da verdade, não `config.py`.
- `ticket_analysis (...)` — 1 linha por critério avaliado (formato longo). As colunas
  estão declaradas em `config.ANALISE_COLUMNS`, que é a **fonte da verdade** do schema
  para todas as páginas:
  `id, id_number, id_manager, id_analista, id_analista_quality, question_id,
  fecha_analisis, analista_quality, ticketnumber, idioma, region, manager,
  nombre_del_tecnico, pilar, pergunta, nota, comentario, status_feedback`

  `id` é o código completo da avaliação, mostrado como **"IDQ"** na interface
  (ex.: `'IDQ12737'`); `id_number` é só a parte numérica. `question_id` é a FK
  para `questions.id`; `pilar`/`pergunta` ficam congelados no momento do
  registro (não mudam retroativamente se o rótulo da pergunta for editado
  depois).

  **`fecha_analisis` é `TEXT`, não um tipo datetime real** — formato
  `'DD/MM/YYYY HH24:MI'` (ex.: `'21/01/2025 09:09'`). Um `.max()`/`ORDER BY`
  direto nela é uma comparação **alfabética**, não cronológica (ex.:
  `'05/03/2025'` viria "menor" que `'21/01/2025'` porque compara caractere a
  caractere pelo dia primeiro). Toda leitura/ordenação usa
  `config.sql_fecha_analisis()` (que reordena a coluna para
  `'YYYY-MM-DD HH:MM'`, onde a comparação de texto já é cronológica) e toda
  escrita usa `ahora.strftime(config.FECHA_ANALISIS_FORMATO_PY)` — nunca
  compare, ordene ou grave essa coluna diretamente.
- `general_comments (id, comentario, fecha)`
- `activity_log (id, tabla, registro_id, accion, columna, valor_anterior, valor_nuevo, usuario, fecha)` — auditoria, 1 linha por coluna alterada (ver `log.py`)

### Editar Análise e perguntas desativadas

Ao editar uma avaliação existente, o formulário mostra a **união** de:
perguntas ativas hoje, e perguntas que essa avaliação específica já respondeu
(mesmo desativadas depois). Uma pergunta ativa nova, que a avaliação nunca
respondeu, aparece em branco e vira um **INSERT** ao salvar (em vez de
**UPDATE**, já que não existe linha prévia pra esse `question_id`) — ver
`views/analisis.py`.

### Ciclo de vida de `status_feedback`

`ticket_analysis.status_feedback` acompanha o processo de uma avaliação, do
registro até o feedback chegar ao técnico:

1. **Registrar** cria a avaliação como `Pendiente` — início do processo.
2. **Aplicar Feedback** (aba em Análises, só admin) marca `Concluído` quando o
   feedback já foi repassado ao técnico — fim do processo. Só oferece o botão
   se o IDQ ainda estiver `Pendiente`; se já `Concluído` ou `Cancelado`, avisa
   e não deixa reaplicar.
3. **Cancelar** (aba em Análises, só admin) marca `Cancelado` — reversível,
   mantém o histórico, fora do ciclo normal.
4. **Eliminar** (aba em Análises, só admin) apaga definitivamente as linhas do
   IDQ em `ticket_analysis`/`general_comments`. Não há undo — distinto de
   Cancelar, que só muda o status.

O Dashboard usa esse status real: **Feedbacks Aplicados** = % de avaliações
não canceladas com `status_feedback = 'Concluído'`.

A página de **Historial de Analisis** é uma ferramenta de exportação: mostra e
exporta `ticket_analysis` **linha a linha**, com exatamente as colunas de
`config.ANALISE_COLUMNS` — 1 linha por critério avaliado, sem agregar por
evaluación.

## Limite de período no Historial (volume)

`ticket_analysis` tem volume muito alto, então a página de Historial impõe dois
tetos, ambos em `config.py`:

- `MAX_MESES_PERIODO = 2` — o filtro de datas (usado tanto na tela quanto na
  exportação CSV/Excel) aceita no máximo 2 meses. Um período maior é recortado
  automaticamente, com aviso na tela.
- `MAX_FILAS_CONSULTA` — teto de linhas por consulta (`LIMIT` no SQL), rede de
  segurança para o caso de 2 meses ainda retornarem volume excessivo.

Os filtros de texto (técnico, manager, analista, ticket, IDQ) são aplicados **no
SQL** (`LIKE`), não em pandas: o banco devolve só o necessário. O resultado é
cacheado por 5 min (`st.cache_data`); gravações (registrar/editar/eliminar/
cancelar) limpam esse cache para o Historial refletir a mudança na hora.

## Diagnóstico de erro de conexão

A página **Inicio** testa a conexão com o banco local e traduz o erro em uma
causa provável (`db.diagnose_error`): arquivo inacessível, banco bloqueado por
outro processo, arquivo somente leitura, tabela/coluna inexistente. O botão
**Recargar configuración** descarta o engine cacheado, necessário para
aplicar mudanças em `db_config.json` sem reiniciar o servidor.

## Docker

A app roda em container com Python 3.12 slim. O banco SQLite fica num volume
Docker nomeado (`quality-data`), montado em `/app/data` — o arquivo `.db`
sobrevive a rebuilds e recriações do container, mas não precisa de nenhuma
credencial nem serviço externo.

### Subir

```bash
cp .env.example .env   # opcional: só define QUALITY_PORT
docker compose up -d --build
```

Comandos úteis:

```bash
docker compose logs -f      # acompanhar logs
docker compose restart      # reiniciar
docker compose down         # parar e remover o container
```

### Acesso a partir de outros computadores

A porta é publicada em `0.0.0.0`, então a app responde no IP da máquina na rede
local — outros computadores acessam por `http://<IP-do-host>:8502`.

Falta apenas liberar a porta no Firewall do Windows (uma vez, em PowerShell
**como administrador**), restringindo a origem à rede local:

```powershell
New-NetFirewallRule -DisplayName "Quality Streamlit 8502" -Direction Inbound -Protocol TCP -LocalPort 8502 -Action Allow -Profile Any -RemoteAddress LocalSubnet
```

Para remover depois:

```powershell
Remove-NetFirewallRule -DisplayName "Quality Streamlit 8502"
```

O IP muda quando a máquina troca de rede — confira com `ipconfig`. Para um
endereço estável, publicar em um servidor fixo é melhor que depender desta
máquina.

Pontos de atenção ao expor na rede:

- O tráfego é **HTTP puro**: senha de login e dados trafegam sem criptografia na
  rede local. Para uso fora de uma rede confiável, colocar um reverse proxy com
  TLS (nginx/Caddy) na frente.
- A chave que assina o cookie de sessão é gerada por processo (`auth.py`): ao
  reiniciar o container todos precisam logar de novo, e a app **não** deve ser
  escalada para mais de uma réplica sem sticky sessions.
- Enquanto o container estiver de pé, qualquer um na mesma rede alcança a tela
  de login. O controle de acesso é o login da própria app.

### Detalhes da imagem

- Roda como usuário sem privilégios (`appuser`, uid 10001).
- `HEALTHCHECK` no endpoint `/_stcore/health` do Streamlit (`docker ps` mostra
  `healthy` quando a app responde).
- `requirements.txt` é copiado antes do código, então alterar um `.py` não
  reinstala as dependências no rebuild.
