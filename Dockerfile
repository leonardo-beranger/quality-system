# Imagem da app Streamlit "Quality Metrics".
#
# O banco é um arquivo SQLite local (ver db.py). O caminho é resolvido por
# db_config.json ou pela variável de ambiente QUALITY_DB_PATH — o
# docker-compose aponta para /app/data/quality_system.db, montado como volume
# para persistir entre reinícios do container.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Streamlit em container: sem browser local, sem prompt de e-mail e
    # escutando em todas as interfaces (senão o publish de porta não alcança).
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# requirements primeiro: essa camada só é reconstruída quando as dependências
# mudam, não a cada alteração de código.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuário sem privilégios. /app/data existe e é gravável — é lá que o SQLite
# grava o arquivo .db (ver QUALITY_DB_PATH no docker-compose.yml).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

# Endpoint de saúde oficial do Streamlit. Usa urllib (a imagem slim não traz curl).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "Inicio.py"]
