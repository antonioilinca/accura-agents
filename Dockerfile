# Cockpit Accura Ouest — image conteneur pour Hugging Face Spaces (Docker)
# ou tout hébergeur de conteneurs. Fait tourner le dashboard des agents.
FROM python:3.12-slim

WORKDIR /app

# Dépendances cœur (sans faster-whisper : agent vocal bridé en ligne, voir docs).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'application.
COPY . .

# Hugging Face Spaces route le trafic HTTPS public vers le port 7860 par défaut.
# run.py lit $PORT et écoute alors sur 0.0.0.0:7860 (mode cloud).
ENV PORT=7860
EXPOSE 7860

CMD ["python", "-m", "agents.dashboard.run"]
