FROM python:3.10-slim

WORKDIR /app

# Устанавливаем необходимые пакеты, включая ffmpeg и зависимости для instaloader
RUN apt-get update && \
    apt-get install -y ffmpeg \
                       # Добавляем зависимости для instaloader
                       gcc \
                       libc-dev \
                       libffi-dev \
                       libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для временных файлов
RUN mkdir -p temp

# Запускаем приложение
CMD ["python", "app.py"]