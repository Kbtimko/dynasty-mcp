FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["dynasty-mcp"]
