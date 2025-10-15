# Imagine de bază lightweight Python
FROM python:3.11-slim

# Setăm directorul de lucru
WORKDIR /app

# Copiem fișierele necesare
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY media_organizer.py .
COPY .env .

# Directorul de intrare va fi mapat la runtime
VOLUME ["/input", "/output_series", "/output_movies", "/config"]

# Variabile default (suprascrise din .env sau la docker run)
ENV INPUT_FOLDER=/input \
    OUTPUT_SERIES=/output_series \
    OUTPUT_MOVIES=/output_movies \
    LOG_FILE=/config/media_organizer.log \
    TMDB_API_KEY=CHANGEME

# Comanda de rulare
CMD ["python", "media_organizer.py"]
