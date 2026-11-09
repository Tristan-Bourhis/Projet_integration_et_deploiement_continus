FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps . && useradd --uid 10001 --create-home pipeline
USER pipeline
ENTRYPOINT ["transaction-pipeline"]
CMD ["process", "--source", "s3"]
