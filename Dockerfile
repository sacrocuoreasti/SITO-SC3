FROM python:3.11-slim

WORKDIR /app

# Installa dipendenze di sistema minime
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cartelle persistenti
RUN mkdir -p database uploads
RUN python scripts/check_release.py

ENV PORT=5001
EXPOSE 5001

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
