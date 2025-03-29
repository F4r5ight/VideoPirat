FROM python:3.10-slim

WORKDIR /app

# Устанавливаем необходимые пакеты, включая ffmpeg и зависимости для различных библиотек
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

# Копируем файлы проекта
COPY . .

# Обновляем pip
RUN pip install --no-cache-dir --upgrade pip

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем самые свежие версии важных пакетов
RUN pip install --no-cache-dir --upgrade yt-dlp instaloader

# Создаем директорию для временных файлов с правильными правами
RUN mkdir -p temp && chmod 777 temp

# Настройка переменных окружения для лучшей работы библиотек
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV YTDLP_EXTRACTOR_RETRIES=3

# Увеличиваем таймауты для улучшения стабильности
ENV HTTP_TIMEOUT=120
ENV SOCKET_TIMEOUT=120

# Запускаем приложение
CMD ["python", "app.py"]