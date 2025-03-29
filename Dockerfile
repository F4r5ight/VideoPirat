FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg \
                       gcc \
                       libc-dev \
                       libffi-dev \
                       libssl-dev \
                       wget \
                       curl \
                       ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir --upgrade yt-dlp instaloader

RUN mkdir -p temp && chmod 777 temp

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV YTDLP_EXTRACTOR_RETRIES=3

ENV HTTP_TIMEOUT=120
ENV SOCKET_TIMEOUT=120

CMD ["python", "app.py"]