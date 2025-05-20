FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    GODFINGER_HOME=/app/jediacademy/godfinger

WORKDIR ${GODFINGER_HOME}

RUN apt-get update && apt-get install -y \
    git \
    sqlite3 \
    bash \
    && rm -rf /var/lib/apt/lists/*

COPY . ${GODFINGER_HOME}

RUN chmod +x start/linux_macOS/prepare.sh start/linux_macOS/startDebugSilent.sh

CMD bash -c '\
  if [ ! -f /app/jediacademy/godfinger/.prepared ]; then \
    ./start/linux_macOS/prepare.sh && touch /app/jediacademy/godfinger/.prepared; \
  fi && \
  ./start/linux_macOS/startDebugSilent.sh'
