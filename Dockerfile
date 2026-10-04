FROM python:3.13-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends stockfish ca-certificates \
    && mkdir -p /app/notices/stockfish \
    && cp /usr/share/doc/stockfish/copyright /app/notices/stockfish/COPYRIGHT \
    && dpkg-query -W stockfish > /app/notices/stockfish/VERSION \
    && sed -i 's/Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && cd /app/notices/stockfish && apt-get source --download-only stockfish \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY chess_coach chess_coach
COPY LICENSE NOTICE /app/notices/
RUN useradd --create-home coach && mkdir -p /data && chown coach:coach /data
USER coach
ENV STOCKFISH_PATH=/usr/games/stockfish DATABASE=/data/chess-coach.sqlite3 PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec gunicorn 'chess_coach.beta:create_app()' --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 300 --graceful-timeout 15 --access-logfile /dev/null"]
