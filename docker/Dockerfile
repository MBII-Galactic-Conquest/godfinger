FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    GODFINGER_HOME=/app/jediacademy/gamedata/godfinger

WORKDIR ${GODFINGER_HOME}

RUN apt-get update && apt-get install -y \
    git \
    sqlite3 \
    docker.io \
    bash \
    && rm -rf /var/lib/apt/lists/*

COPY . ${GODFINGER_HOME}

RUN chmod +x quickstart_linux_macOS.sh start/linux_macOS/prepare.sh

CMD bash -c '\
  if [ ! -f .prepared ]; then \
    ./start/linux_macOS/prepare.sh && touch .prepared; \
  fi && \
  ./quickstart_linux_macOS.sh'