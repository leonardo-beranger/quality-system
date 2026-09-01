"""Soporte de idioma (Español / Português / English) para todo el proyecto.

Cada página llama a `render_language_selector()` una vez (en la barra lateral)
y usa `t("clave")` para obtener el texto en el idioma actualmente seleccionado.
El idioma se guarda en `st.session_state["idioma"]` y se mantiene al navegar
entre páginas, porque el session_state es compartido en toda la app Streamlit.
"""

import streamlit as st

LANGUAGES = {"es": "Spanish", "pt": "Portuguese", "en": "English"}
DEFAULT_LANGUAGE = "pt"

TRANSLATIONS = {
    # Login
    "login_title": {"es": "Iniciar sesión", "pt": "Entrar", "en": "Sign in"},
    "login_caption": {
        "es": "Ingrese con su correo y contraseña para acceder al Feedback Quality Monitor.",
        "pt": "Entre com seu e-mail e senha para acessar o Feedback Quality Monitor.",
        "en": "Sign in with your email and password to access the Feedback Quality Monitor.",
    },
    "login_field_email": {"es": "Correo electrónico", "pt": "E-mail", "en": "Email"},
    "login_field_password": {"es": "Contraseña", "pt": "Senha", "en": "Password"},
    "login_btn_entrar": {"es": "Entrar", "pt": "Entrar", "en": "Sign in"},
    "login_error_campos_vacios": {
        "es": "Informe correo y contraseña.",
        "pt": "Informe e-mail e senha.",
        "en": "Enter your email and password.",
    },
    "login_error_credenciales": {
        "es": "Correo o contraseña incorrectos.",
        "pt": "E-mail ou senha incorretos.",
        "en": "Incorrect email or password.",
    },
    "login_error_sin_password": {
        "es": "Este usuario todavía no tiene contraseña definida. Solicite a un administrador que la configure.",
        "pt": "Este usuário ainda não tem senha definida. Peça a um administrador para configurá-la.",
        "en": "This user doesn't have a password set yet. Ask an admin to set one.",
    },
    "logout_button": {"es": "Cerrar sesión", "pt": "Sair", "en": "Log out"},
    "logged_in_as": {
        "es": "Conectado como **{nombre}**",
        "pt": "Conectado como **{nombre}**",
        "en": "Signed in as **{nombre}**",
    },

    # Barra lateral / genérico
    "language_label": {"es": "Idioma", "pt": "Idioma", "en": "Language"},
    "err_acceso_restringido": {
        "es": "Página restringida a administradores.",
        "pt": "Página restrita a administradores.",
        "en": "This page is restricted to admins.",
    },
    "db_connection_error": {
        "es": "No fue posible conectar a la base de datos. El formulario se muestra igual, pero los "
        "listados y el guardado no funcionarán hasta que la conexión esté disponible.\n\nDetalle: {error}",
        "pt": "Não foi possível conectar ao banco de dados. O formulário é exibido normalmente, mas as "
        "listas e o salvamento não funcionarão até que a conexão esteja disponível.\n\nDetalhe: {error}",
        "en": "Could not connect to the database. The form still renders, but lists and saving won't "
        "work until the connection is available.\n\nDetail: {error}",
    },
    "test_connection_button": {"es": "Probar conexión", "pt": "Testar conexão", "en": "Test connection"},
    "test_connection_ok": {
        "es": "Conexión con el banco local establecida correctamente.",
        "pt": "Conexão com o banco local estabelecida com sucesso.",
        "en": "Connection to the local database established successfully.",
    },
    "test_connection_fail": {
        "es": "Falla en la conexión: {error}",
        "pt": "Falha na conexão: {error}",
        "en": "Connection failed: {error}",
    },
    "reset_engine_button": {"es": "Recargar configuración", "pt": "Recarregar configuração", "en": "Reload configuration"},
    "reset_engine_ok": {
        "es": "Configuración recargada desde db_config.json. Pruebe la conexión de nuevo.",
        "pt": "Configuração recarregada de db_config.json. Teste a conexão novamente.",
        "en": "Configuration reloaded from db_config.json. Test the connection again.",
    },

    # Diagnóstico de errores de conexión / esquema (db.diagnose_error)
    "hint_label": {"es": "Causa probable", "pt": "Causa provável", "en": "Likely cause"},
    "hint_sqlite_arquivo": {
        "es": "No fue posible **abrir el archivo** del banco SQLite. Revise si la carpeta indicada en "
        "`db_config.json` (o `QUALITY_DB_PATH`) existe y si el proceso tiene permiso de escritura ahí.",
        "pt": "Não foi possível **abrir o arquivo** do banco SQLite. Verifique se a pasta indicada em "
        "`db_config.json` (ou `QUALITY_DB_PATH`) existe e se o processo tem permissão de escrita nela.",
        "en": "Could not **open the SQLite file**. Check that the folder set in `db_config.json` (or "
        "`QUALITY_DB_PATH`) exists and that the process can write to it.",
    },
    "hint_sqlite_locked": {
        "es": "El banco está **bloqueado por otro proceso** (otra instancia de la app, o el archivo "
        "abierto en otra herramienta). Cierre el otro acceso e intente de nuevo.",
        "pt": "O banco está **bloqueado por outro processo** (outra instância da app, ou o arquivo "
        "aberto em outra ferramenta). Feche o outro acesso e tente de novo.",
        "en": "The database is **locked by another process** (another app instance, or the file open "
        "in another tool). Close the other access and try again.",
    },
    "hint_sqlite_readonly": {
        "es": "El archivo del banco es **de solo lectura** para este proceso. Revise los permisos del "
        "archivo/carpeta configurados en `db_config.json`.",
        "pt": "O arquivo do banco está **somente leitura** para este processo. Revise as permissões "
        "do arquivo/pasta configurados em `db_config.json`.",
        "en": "The database file is **read-only** for this process. Check the file/folder permissions "
        "configured in `db_config.json`.",
    },
    "hint_tabla_inexistente": {
        "es": "La conexión funcionó, pero la **tabla no existe**. Borre el archivo `.db` para que se "
        "recree desde cero, o revise los nombres en `TABLES` (config.py).",
        "pt": "A conexão funcionou, mas a **tabela não existe**. Apague o arquivo `.db` para que seja "
        "recriado do zero, ou revise os nomes em `TABLES` (config.py).",
        "en": "The connection worked, but the **table doesn't exist**. Delete the `.db` file so it gets "
        "recreated from scratch, or check the names in `TABLES` (config.py).",
    },
    "hint_columna_inexistente": {
        "es": "La tabla existe pero **una columna no**. Compare los nombres reales con "
        "`ANALISE_COLUMNS` en config.py, o borre el archivo `.db` para recrearlo desde cero.",
        "pt": "A tabela existe mas **uma coluna não**. Compare os nomes reais com "
        "`ANALISE_COLUMNS` em config.py, ou apague o arquivo `.db` para recriá-lo do zero.",
        "en": "The table exists but **a column doesn't**. Compare the real column names with "
        "`ANALISE_COLUMNS` in config.py, or delete the `.db` file to recreate it from scratch.",
    },

    # Inicio
    "home_title": {"es": "Feedback Quality Monitor", "pt": "Feedback Quality Monitor", "en": "Feedback Quality Monitor"},
    "home_caption": {
        "es": "Migración de los formularios VBA de monitoreo_calidad_v2.xlsm a Streamlit",
        "pt": "Migração dos formulários VBA de monitoreo_calidad_v2.xlsm para Streamlit",
        "en": "Migration of the monitoreo_calidad_v2.xlsm VBA forms to Streamlit",
    },
    "home_intro": {
        "es": """
Use el menú de la izquierda para navegar entre las páginas:

**Registros** *(solo admin)*
- Quality Agent, Manager, Analistas — mantiene las listas de analistas de calidad,
  managers y técnicos.
- Perguntas — activa/desactiva los criterios de evaluación y agrega nuevos.

**Proceso de evaluación**
- Registrar Análisis — registra una nueva evaluación de ticket (criterios activos,
  agrupados en pilares) y genera el código IDQ.
- Editar Análisis *(solo admin)* — carga una evaluación existente por IDQ/ticket y
  permite editar las notas y comentarios.
- Cancelar Análisis *(solo admin)* — marca una evaluación como cancelada, sin borrarla.
- Eliminar *(solo admin)* — eliminación definitiva de una evaluación.

**Consulta**
- Dashboard — nivel de calidad, volumen de feedbacks y rankings.
- Historial de Análisis — vista consolidada de todas las evaluaciones, con filtros
  y exportación (CSV/Excel).
        """,
        "pt": """
Use o menu à esquerda para navegar entre as páginas:

**Cadastros** *(somente admin)*
- Quality Agent, Manager, Analistas — mantém as listas de analistas de qualidade,
  managers e técnicos.
- Perguntas — ativa/desativa os critérios de avaliação e cadastra novos.

**Processo de avaliação**
- Registrar Análise — registra uma nova avaliação de ticket (critérios ativos,
  agrupados em pilares) e gera o código IDQ.
- Editar Análise *(somente admin)* — carrega uma avaliação existente pelo IDQ/ticket
  e permite editar as notas e comentários.
- Cancelar Análise *(somente admin)* — marca uma avaliação como cancelada, sem apagá-la.
- Eliminar *(somente admin)* — remoção definitiva de uma avaliação.

**Consulta**
- Dashboard — nível de qualidade, volume de feedbacks e rankings.
- Histórico de Análises — visão consolidada de todas as avaliações, com filtros
  e exportação (CSV/Excel).
        """,
        "en": """
Use the menu on the left to move between pages:

**Records** *(admin only)*
- Quality Agent, Manager, Analysts — maintains the lists of quality analysts,
  managers and technicians.
- Questions — activates/deactivates evaluation criteria and adds new ones.

**Evaluation process**
- Register Analysis — registers a new ticket evaluation (active criteria,
  grouped by pillar) and generates the IDQ code.
- Edit Analysis *(admin only)* — loads an existing evaluation by IDQ/ticket and
  lets you edit the scores/comments.
- Cancel Analysis *(admin only)* — flags an evaluation as cancelled, without deleting it.
- Delete *(admin only)* — permanently deletes an evaluation.

**Reporting**
- Dashboard — quality level, feedback volume and rankings.
- Analysis History — consolidated view of every evaluation, with filters and
  export (CSV/Excel).
        """,
    },
    "home_db_subheader": {
        "es": "Conexión con el banco de datos (SQLite local)",
        "pt": "Conexão com o banco de dados (SQLite local)",
        "en": "Database connection (local SQLite)",
    },
    "home_db_caption": {
        "es": "El banco es un archivo local, creado automáticamente. Para usar otro "
        "camino, configure `db_config.json` (vea `db_config.json.example`) o la "
        "variable de entorno QUALITY_DB_PATH.",
        "pt": "O banco é um arquivo local, criado automaticamente. Para usar outro "
        "caminho, configure `db_config.json` (veja `db_config.json.example`) ou a "
        "variável de ambiente QUALITY_DB_PATH.",
        "en": "The database is a local file, created automatically. To use a "
        "different path, set `db_config.json` (see `db_config.json.example`) or "
        "the QUALITY_DB_PATH environment variable.",
    },

    # Navegación (st.navigation)
    "nav_inicio": {"es": "Inicio", "pt": "Início", "en": "Home"},

    # Página agrupada "Registros" (Quality Agent + Manager + Analistas)
    "registros_page_title": {"es": "Registros", "pt": "Cadastros", "en": "Records"},
    "registros_page_caption": {
        "es": "Registro y mantenimiento de analistas de calidad, managers y técnicos.",
        "pt": "Cadastro e manutenção de analistas de qualidade, managers e técnicos.",
        "en": "Registration and upkeep of quality analysts, managers and technicians.",
    },

    # Página agrupada "Analisis" (Registrar + Editar + Cancelar + Eliminar)
    "analisis_page_title": {"es": "Analisis", "pt": "Análises", "en": "Analysis"},
    "analisis_page_caption": {
        "es": "Registrar una nueva evaluación de ticket o editar/consultar/cancelar/eliminar una evaluación existente.",
        "pt": "Registrar uma nova avaliação de ticket ou editar/consultar/cancelar/eliminar uma avaliação existente.",
        "en": "Register a new ticket evaluation, or edit/look up/cancel/delete an existing one.",
    },

    # Quality Agent
    "qa_title": {"es": "Quality Agent", "pt": "Quality Agent", "en": "Quality Agent"},
    "qa_caption": {
        "es": "Registro y mantenimiento de la lista de analistas de calidad.",
        "pt": "Cadastro e manutenção da lista de analistas de qualidade.",
        "en": "Registration and upkeep of the quality analysts list.",
    },
    "load_form_subheader": {"es": "Cargar / Registro", "pt": "Load / Cadastro", "en": "Load / Register"},
    "select_to_load": {"es": "Seleccione para cargar", "pt": "Selecione para carregar", "en": "Select to load"},
    "field_analista": {"es": "Analista", "pt": "Analista", "en": "Analyst"},
    "field_email": {"es": "Correo electrónico", "pt": "E-mail", "en": "Email"},
    "field_status": {"es": "Estado", "pt": "Status", "en": "Status"},
    "field_role": {"es": "Rol", "pt": "Papel", "en": "Role"},
    "btn_registrar": {"es": "Registrar (nuevo)", "pt": "Registrar (novo)", "en": "Register (new)"},
    "btn_actualizar": {"es": "Actualizar", "pt": "Actualizar", "en": "Update"},
    "err_informe_analista": {
        "es": "Informe el nombre del analista.",
        "pt": "Informe o nome do analista.",
        "en": "Enter the analyst's name.",
    },
    "qa_senha_padrao_caption": {
        "es": "Un usuario nuevo recibe la contraseña estándar **{senha}** — avísele para el primer acceso.",
        "pt": "Um usuário novo recebe a senha padrão **{senha}** — avise-o para o primeiro acesso.",
        "en": "A new user gets the default password **{senha}** — let them know for their first sign-in.",
    },
    "ok_analista_registrado_senha": {
        "es": "Analista '{nombre}' registrado. Contraseña inicial: **{senha}**",
        "pt": "Analista '{nombre}' registrado. Senha inicial: **{senha}**",
        "en": "Analyst '{nombre}' registered. Initial password: **{senha}**",
    },
    "err_cargue_analista": {
        "es": "Cargue un analista existente antes de actualizar.",
        "pt": "Carregue um analista existente antes de atualizar.",
        "en": "Load an existing analyst before updating.",
    },
    "ok_analista_actualizado": {
        "es": "Analista '{nombre}' actualizado.",
        "pt": "Analista '{nombre}' atualizado.",
        "en": "Analyst '{nombre}' updated.",
    },
    "current_list_subheader": {"es": "Lista actual", "pt": "Lista atual", "en": "Current list"},

    # Manager
    "mgr_title": {"es": "Manager", "pt": "Manager", "en": "Manager"},
    "mgr_caption": {
        "es": "Registro y mantenimiento de la lista de managers.",
        "pt": "Cadastro e manutenção da lista de managers.",
        "en": "Registration and upkeep of the managers list.",
    },
    "field_manager": {"es": "Manager", "pt": "Manager", "en": "Manager"},
    "err_informe_manager": {
        "es": "Informe el nombre del manager.",
        "pt": "Informe o nome do manager.",
        "en": "Enter the manager's name.",
    },
    "ok_manager_registrado": {
        "es": "Manager '{nombre}' registrado.",
        "pt": "Manager '{nombre}' registrado.",
        "en": "Manager '{nombre}' registered.",
    },
    "err_cargue_manager": {
        "es": "Cargue un manager existente antes de actualizar.",
        "pt": "Carregue um manager existente antes de atualizar.",
        "en": "Load an existing manager before updating.",
    },
    "ok_manager_actualizado": {
        "es": "Manager '{nombre}' actualizado.",
        "pt": "Manager '{nombre}' atualizado.",
        "en": "Manager '{nombre}' updated.",
    },

    # Analistas
    "an_title": {"es": "Analistas (técnicos)", "pt": "Analistas (técnicos)", "en": "Analysts (technicians)"},
    "an_caption": {
        "es": "Registro y mantenimiento de la lista de técnicos evaluados.",
        "pt": "Cadastro e manutenção da lista de técnicos avaliados.",
        "en": "Registration and upkeep of the evaluated technicians list.",
    },
    "field_tecnico": {"es": "Analista/Técnico", "pt": "Analista/Técnico", "en": "Analyst/Technician"},
    "err_informe_tecnico": {
        "es": "Informe el nombre del técnico.",
        "pt": "Informe o nome do técnico.",
        "en": "Enter the technician's name.",
    },
    "ok_tecnico_registrado": {
        "es": "Técnico '{nombre}' registrado.",
        "pt": "Técnico '{nombre}' registrado.",
        "en": "Technician '{nombre}' registered.",
    },
    "err_cargue_tecnico": {
        "es": "Cargue un técnico existente antes de actualizar.",
        "pt": "Carregue um técnico existente antes de atualizar.",
        "en": "Load an existing technician before updating.",
    },
    "ok_tecnico_actualizado": {
        "es": "Técnico '{nombre}' actualizado.",
        "pt": "Técnico '{nombre}' atualizado.",
        "en": "Technician '{nombre}' updated.",
    },
    "cascada_info": {
        "es": "Manager actualizado en cascada en las evaluaciones ya registradas de '{nombre}'.",
        "pt": "Manager atualizado em cascata nas avaliações já registradas de '{nombre}'.",
        "en": "Manager cascaded to the evaluations already registered for '{nombre}'.",
    },

    # Registrar Análisis
    "reg_title": {"es": "Registrar Análisis de Ticket", "pt": "Registrar Análise de Ticket", "en": "Register Ticket Analysis"},
    "reg_caption": {
        "es": "Equivalente al formulario 'Hacer análisis' — registro de una nueva evaluación (genera un nuevo IDQ).",
        "pt": "Equivalente ao formulário 'Hacer análisis' — registro de uma nova avaliação (gera um novo IDQ).",
        "en": "Equivalent to the 'Hacer análisis' form — registers a new evaluation (generates a new IDQ).",
    },
    "header_subheader": {"es": "Encabezado", "pt": "Cabeçalho", "en": "Header"},
    "field_ticket": {"es": "TicketNumber *", "pt": "TicketNumber *", "en": "TicketNumber *"},
    "field_analista_quality": {"es": "Analista Quality *", "pt": "Analista Quality *", "en": "Quality Analyst *"},
    "field_tecnico_req": {"es": "Técnico *", "pt": "Técnico *", "en": "Technician *"},
    "field_idioma": {"es": "Idioma *", "pt": "Idioma *", "en": "Language *"},
    "field_region": {"es": "Región *", "pt": "Región *", "en": "Region *"},
    "manager_tecnico_caption": {
        "es": "Manager del técnico: **{manager}**",
        "pt": "Manager do técnico: **{manager}**",
        "en": "Technician's manager: **{manager}**",
    },
    "criterios_subheader": {
        "es": "Criterios de evaluación",
        "pt": "Critérios de avaliação",
        "en": "Evaluation criteria",
    },
    "warn_sin_preguntas_activas": {
        "es": "No hay preguntas activas configuradas — pida a un admin que active al menos una en \"Perguntas\".",
        "pt": "Não há perguntas ativas configuradas — peça a um admin para ativar pelo menos uma em \"Perguntas\".",
        "en": "There are no active questions configured — ask an admin to activate at least one in \"Perguntas\".",
    },
    "comentario_placeholder": {"es": "Comentario — {rotulo}", "pt": "Comentário — {rotulo}", "en": "Comment — {rotulo}"},
    "comentario_general_label": {"es": "Comentario General", "pt": "Comentario General", "en": "General Comment"},
    "err_encabezado": {
        "es": "Complete el encabezado obligatorio: {faltantes}",
        "pt": "Preencha o cabeçalho obrigatório: {faltantes}",
        "en": "Fill in the required header: {faltantes}",
    },
    "ok_registrado": {
        "es": "Evaluación registrada con éxito — código generado: **{idq}**",
        "pt": "Avaliação registrada com sucesso — código gerado: **{idq}**",
        "en": "Evaluation registered successfully — generated code: **{idq}**",
    },
    "btn_limpiar": {"es": "Limpiar", "pt": "Limpar", "en": "Clear"},

    # Editar Análisis
    "edit_title": {"es": "Editar Análisis", "pt": "Editar Análise", "en": "Edit Analysis"},
    "edit_caption": {
        "es": "Consulte una evaluación existente por IDQ, TicketNumber o Técnico y edite las notas/comentarios.",
        "pt": "Consulte uma avaliação existente por IDQ, TicketNumber ou Técnico e edite as notas/comentários.",
        "en": "Look up an existing evaluation by IDQ, TicketNumber or Technician and edit its scores/comments.",
    },
    "consultar_subheader": {"es": "Consultar Análisis", "pt": "Consultar Análise", "en": "Look Up Analysis"},
    "field_idq": {"es": "IDQ", "pt": "IDQ", "en": "IDQ"},
    "btn_consultar": {"es": "Consultar", "pt": "Consultar", "en": "Search"},
    "select_idq_edit": {
        "es": "Seleccione el IDQ para cargar y editar",
        "pt": "Selecione o IDQ para carregar e editar",
        "en": "Select the IDQ to load and edit",
    },
    "warn_sin_registros": {
        "es": "No se encontraron registros para ese IDQ.",
        "pt": "Nenhum registro encontrado para esse IDQ.",
        "en": "No records found for that IDQ.",
    },
    "editing_subheader": {"es": "Editando {idq}", "pt": "Editando {idq}", "en": "Editing {idq}"},
    "comentario_general_hist_label": {
        "es": "Comentario General (se agregará al historial)",
        "pt": "Comentario General (será adicionado ao histórico)",
        "en": "General Comment (will be added to the history)",
    },
    "ok_actualizado": {
        "es": "Evaluación {idq} actualizada con éxito.",
        "pt": "Avaliação {idq} atualizada com sucesso.",
        "en": "Evaluation {idq} updated successfully.",
    },

    # Cancelar Análisis (aba dentro de "Análises")
    "cancel_title": {"es": "Cancelar Análisis", "pt": "Cancelar Análise", "en": "Cancel Analysis"},
    "cancelar_subheader": {
        "es": "Cancelar — reversible, mantiene el historial",
        "pt": "Cancelar — reversível, mantém o histórico",
        "en": "Cancel — reversible, keeps history",
    },
    "cancelar_info": {
        "es": "No borra nada: marca `status_feedback = 'Cancelado'` en las líneas de ese IDQ "
        "(es lo que lee el filtro \"Solo cancelados\" del Historial) y guarda el motivo en "
        "`general_comments`.",
        "pt": "Não apaga nada: marca `status_feedback = 'Cancelado'` nas linhas daquele IDQ "
        "(é o que o filtro \"Somente cancelados\" do Histórico lê) e grava o motivo em "
        "`general_comments`.",
        "en": "Deletes nothing: flags `status_feedback = 'Cancelado'` on that IDQ's rows (which is "
        "what the History's \"Only cancelled\" filter reads) and saves the reason in "
        "`general_comments`.",
    },
    "field_motivacion": {"es": "Motivación", "pt": "Motivación", "en": "Reason"},
    "btn_confirma": {"es": "Confirma", "pt": "Confirma", "en": "Confirm"},
    "err_idq_no_encontrado": {
        "es": "No se encontró ningún registro para el IDQ '{idq}'.",
        "pt": "Nenhum registro encontrado para o IDQ '{idq}'.",
        "en": "No record found for IDQ '{idq}'.",
    },
    "ok_cancelado": {
        "es": "IDQ '{idq}' marcado como cancelado.",
        "pt": "IDQ '{idq}' marcado como cancelado.",
        "en": "IDQ '{idq}' flagged as cancelled.",
    },

    # Eliminar
    "del_title": {"es": "Eliminar Análisis", "pt": "Eliminar Análise", "en": "Delete Analysis"},
    "eliminar_subheader": {
        "es": "Eliminar — acción destructiva y permanente",
        "pt": "Eliminar — ação destrutiva e permanente",
        "en": "Delete — destructive, permanent action",
    },
    "eliminar_warning": {
        "es": "Borra definitivamente todas las líneas del IDQ informado en `ticket_analysis` y "
        "`general_comments`. No se puede deshacer. Use solo para registros incorrectos o duplicados.",
        "pt": "Apaga definitivamente todas as linhas do IDQ informado em `ticket_analysis` e "
        "`general_comments`. Não pode ser desfeito. Use apenas para lançamentos incorretos ou duplicados.",
        "en": "Permanently deletes every row for the given IDQ in `ticket_analysis` and "
        "`general_comments`. Cannot be undone. Only use it for incorrect or duplicate entries.",
    },
    "confirm_eliminar_checkbox": {
        "es": "Confirmo que deseo eliminar permanentemente este IDQ",
        "pt": "Confirmo que desejo excluir permanentemente este IDQ",
        "en": "I confirm I want to permanently delete this IDQ",
    },
    "btn_eliminar": {"es": "Eliminar", "pt": "Eliminar", "en": "Delete"},
    "ok_eliminado": {
        "es": "IDQ '{idq}' eliminado permanentemente.",
        "pt": "IDQ '{idq}' excluído permanentemente.",
        "en": "IDQ '{idq}' permanently deleted.",
    },

    # Perguntas (catálogo de pilares + critérios)
    "questions_page_title": {"es": "Perguntas", "pt": "Perguntas", "en": "Questions"},
    "questions_page_caption": {
        "es": "Cadastro de pilares (nombre + peso) y de los criterios de evaluación vinculados a ellos.",
        "pt": "Cadastro de pilares (nome + peso) e dos critérios de avaliação vinculados a eles.",
        "en": "Registration of pillars (name + weight) and the evaluation criteria linked to them.",
    },
    "pillars_tab_title": {"es": "Pilares", "pt": "Pilares", "en": "Pillars"},
    "pillars_tab_caption": {
        "es": "Nombre (en inglés) y peso de cada pilar — usado para ponderar la nota final.",
        "pt": "Nome (em inglês) e peso de cada pilar — usado para ponderar a nota final.",
        "en": "Name (in English) and weight of each pillar — used to weight the final score.",
    },
    "questions_tab_title": {"es": "Preguntas", "pt": "Perguntas", "en": "Questions"},
    "questions_tab_caption": {
        "es": "Cada pregunta pertenece a un pilar y hereda su peso. Pregunta/descripción en portugués.",
        "pt": "Cada pergunta pertence a um pilar e herda o peso dele. Pergunta/descrição em português.",
        "en": "Each question belongs to a pillar and inherits its weight. Question/description in Portuguese.",
    },
    "field_pillar_name": {"es": "Nombre del pilar (inglés)", "pt": "Nome do pilar (inglês)", "en": "Pillar name (English)"},
    "field_pillar_weight": {"es": "Peso", "pt": "Peso", "en": "Weight"},
    "err_informe_pillar_name": {
        "es": "Informe el nombre del pilar.",
        "pt": "Informe o nome do pilar.",
        "en": "Enter the pillar's name.",
    },
    "err_pillar_duplicado": {
        "es": "Ya existe un pilar llamado '{nombre}'.",
        "pt": "Já existe um pilar chamado '{nombre}'.",
        "en": "A pillar named '{nombre}' already exists.",
    },
    "err_cargue_pillar": {
        "es": "Cargue un pilar existente antes de actualizar.",
        "pt": "Carregue um pilar existente antes de atualizar.",
        "en": "Load an existing pillar before updating.",
    },
    "ok_pillar_registrado": {
        "es": "Pilar '{nombre}' registrado.",
        "pt": "Pilar '{nombre}' registrado.",
        "en": "Pillar '{nombre}' registered.",
    },
    "ok_pillar_actualizado": {
        "es": "Pilar '{nombre}' actualizado.",
        "pt": "Pilar '{nombre}' atualizado.",
        "en": "Pillar '{nombre}' updated.",
    },
    "warn_sin_pilares": {
        "es": "No hay pilares registrados — cree uno en la pestaña \"Pilares\" antes de agregar preguntas.",
        "pt": "Não há pilares cadastrados — crie um na aba \"Pilares\" antes de adicionar perguntas.",
        "en": "No pillars registered yet — create one in the \"Pillars\" tab before adding questions.",
    },
    "field_pillar": {"es": "Pilar", "pt": "Pilar", "en": "Pillar"},
    "field_weight_caption": {"es": "Peso del pilar: **{peso}**", "pt": "Peso do pilar: **{peso}**", "en": "Pillar weight: **{peso}**"},
    "field_question_label": {"es": "Pregunta", "pt": "Pergunta", "en": "Question"},
    "field_question_description": {"es": "Descripción", "pt": "Descrição", "en": "Description"},
    "field_question_active": {"es": "Activa", "pt": "Ativa", "en": "Active"},
    "err_informe_question_label": {
        "es": "Informe el texto de la pregunta.",
        "pt": "Informe o texto da pergunta.",
        "en": "Enter the question's text.",
    },
    "err_cargue_question": {
        "es": "Cargue una pregunta existente antes de actualizar.",
        "pt": "Carregue uma pergunta existente antes de atualizar.",
        "en": "Load an existing question before updating.",
    },
    "ok_question_registrada": {
        "es": "Pregunta '{nombre}' registrada.",
        "pt": "Pergunta '{nombre}' registrada.",
        "en": "Question '{nombre}' registered.",
    },
    "ok_question_actualizada": {
        "es": "Pregunta '{nombre}' actualizada.",
        "pt": "Pergunta '{nombre}' atualizada.",
        "en": "Question '{nombre}' updated.",
    },

    # Dashboard (indicadores de qualidade)
    "dashboard_page_title": {"es": "Dashboard", "pt": "Dashboard", "en": "Dashboard"},
    "dashboard_page_caption": {
        "es": "Indicadores de calidad — nivel, volumen de feedbacks y rankings.",
        "pt": "Indicadores de qualidade — nível, volume de feedbacks e rankings.",
        "en": "Quality indicators — level, feedback volume and rankings.",
    },
    "dashboard_sin_datos": {
        "es": "Todavía no hay evaluaciones registradas para calcular los indicadores.",
        "pt": "Ainda não há avaliações registradas para calcular os indicadores.",
        "en": "No evaluations registered yet to calculate the indicators.",
    },
    "kpi_nivel_calidad": {"es": "Nivel Calidad", "pt": "Nível Qualidade", "en": "Quality Level"},
    "kpi_encaminhados": {"es": "Feedbacks Encaminados", "pt": "Feedbacks Encaminhados", "en": "Feedbacks Forwarded"},
    "kpi_aplicados": {"es": "Feedbacks Aplicados", "pt": "Feedbacks Aplicados", "en": "Feedbacks Applied"},
    "field_periodo_dashboard": {"es": "Período", "pt": "Período", "en": "Period"},
    "btn_limpar_filtros": {"es": "Limpiar filtros", "pt": "Limpar filtros", "en": "Clear filters"},
    "btn_limpar_filtros_help": {
        "es": "Limpia todos los filtros (vuelve al período/selección estándar)",
        "pt": "Limpa todos os filtros (volta ao período/seleção padrão)",
        "en": "Clear all filters (back to the default period/selection)",
    },
    "dashboard_filtro_clique_info": {
        "es": "Filtro por clic activo: {valores} — use \"Limpiar filtros\" para limpiar.",
        "pt": "Filtro por clique ativo: {valores} — use \"Limpar filtros\" para limpar.",
        "en": "Click-filter active: {valores} — use \"Clear filters\" to clear it.",
    },
    "donut_title": {"es": "Feedbacks", "pt": "Feedbacks", "en": "Feedbacks"},
    "status_title": {"es": "Status Feedback", "pt": "Status Feedback", "en": "Feedback Status"},
    "legend_aplicado": {"es": "Aplicado", "pt": "Aplicado", "en": "Applied"},
    "combo_title": {"es": "Feedbacks por mes", "pt": "Feedbacks por mês", "en": "Feedbacks by month"},
    "ranking_pilares_title": {"es": "Ranking - Pilares", "pt": "Ranking - Pilares", "en": "Ranking - Pillars"},
    "ranking_supervisores_title": {"es": "Ranking Supervisores", "pt": "Ranking Supervisores", "en": "Ranking Supervisors"},
    "ranking_analistas_title": {"es": "Ranking Analistas", "pt": "Ranking Analistas", "en": "Ranking Analysts"},
    "reincidencia_title": {"es": "Reincidencia", "pt": "Reincidência", "en": "Recurrence"},

    # Historial
    "hist_title": {"es": "Historial de Analisis", "pt": "Histórico de Análises", "en": "Analysis History"},
    "hist_caption": {
        "es": "Líneas de análisis (1 por criterio evaluado), con filtros y exportación.",
        "pt": "Linhas de análise (1 por critério avaliado), com filtros e exportação.",
        "en": "Analysis rows (1 per evaluated criterion), with filters and export.",
    },
    "filtros_subheader": {"es": "Filtros", "pt": "Filtros", "en": "Filters"},
    "field_periodo": {"es": "fecha_analisis", "pt": "fecha_analisis", "en": "fecha_analisis"},
    "field_manager_filtro": {"es": "Manager", "pt": "Manager", "en": "Manager"},
    "field_analista_filtro": {"es": "Analista Quality", "pt": "Analista Quality", "en": "Quality Analyst"},
    "field_status_filtro": {"es": "Estado", "pt": "Status", "en": "Status"},
    "opt_todos": {"es": "Todos", "pt": "Todos", "en": "All"},
    "opt_solo_activos": {"es": "Solo activos", "pt": "Somente ativos", "en": "Active only"},
    "opt_solo_cancelados": {"es": "Solo cancelados", "pt": "Somente cancelados", "en": "Cancelled only"},
    "resultado_subheader": {"es": "Resultado ({n} líneas)", "pt": "Resultado ({n} linhas)", "en": "Result ({n} rows)"},
    "exportacion_subheader": {"es": "Exportación", "pt": "Exportação", "en": "Export"},
    "btn_export_csv": {"es": "Exportar CSV", "pt": "Exportar CSV", "en": "Export CSV"},
    "btn_export_excel": {"es": "Exportar Excel", "pt": "Exportar Excel", "en": "Export Excel"},
    "periodo_limitado_aviso": {
        "es": "El volumen de datos es muy grande: el período se limitó automáticamente a "
        "{meses} meses ({desde} a {hasta}).",
        "pt": "O volume de dados é muito grande: o período foi limitado automaticamente a "
        "{meses} meses ({desde} a {hasta}).",
        "en": "The data volume is too large: the period was automatically limited to "
        "{meses} months ({desde} to {hasta}).",
    },
    "periodo_limite_caption": {
        "es": "El período de consulta y exportación está limitado a {meses} meses — la tabla de "
        "análisis tiene un volumen muy alto.",
        "pt": "O período de consulta e exportação está limitado a {meses} meses — a tabela de "
        "análises tem volume muito alto.",
        "en": "The query/export period is limited to {meses} months — the analysis table has a "
        "very high volume.",
    },
    "periodo_help": {
        "es": "Seleccione la fecha inicial y la final. El rango máximo es de {meses} meses; "
        "si elige un período mayor, se recorta automáticamente.",
        "pt": "Selecione a data inicial e a final. O intervalo máximo é de {meses} meses; "
        "se escolher um período maior, ele é recortado automaticamente.",
        "en": "Select the start and end date. The maximum range is {meses} months; a longer "
        "period is automatically trimmed.",
    },
    "periodo_incompleto_aviso": {
        "es": "Seleccione también la **fecha final** del período para ejecutar la consulta.",
        "pt": "Selecione também a **data final** do período para executar a consulta.",
        "en": "Also select the period's **end date** to run the query.",
    },
    "consultando_spinner": {"es": "Consultando el banco…", "pt": "Consultando o banco…", "en": "Querying the database…"},
    "resultado_truncado_aviso": {
        "es": "El resultado superó {filas} líneas y fue recortado: las evaluaciones del borde "
        "pueden quedar incompletas. Reduzca el período o use más filtros antes de exportar.",
        "pt": "O resultado passou de {filas} linhas e foi recortado: as avaliações da borda "
        "podem ficar incompletas. Reduza o período ou use mais filtros antes de exportar.",
        "en": "The result exceeded {filas} rows and was trimmed: evaluations at the edge may be "
        "incomplete. Narrow the period or use more filters before exporting.",
    },
    "exportacion_caption": {
        "es": "Período {desde} a {hasta} — {lineas} líneas (1 línea por criterio evaluado).",
        "pt": "Período {desde} a {hasta} — {lineas} linhas (1 linha por critério avaliado).",
        "en": "Period {desde} to {hasta} — {lineas} rows (1 row per evaluated criterion).",
    },
}


def render_language_selector() -> str:
    idioma_actual = st.session_state.get("idioma", DEFAULT_LANGUAGE)
    opciones = list(LANGUAGES.keys())
    idx = opciones.index(idioma_actual) if idioma_actual in opciones else 0
    return st.sidebar.radio(
        t("language_label"),
        opciones,
        index=idx,
        format_func=lambda code: LANGUAGES[code],
        key="idioma",
    )


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("idioma", DEFAULT_LANGUAGE)
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    texto = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    return texto.format(**kwargs) if kwargs else texto
