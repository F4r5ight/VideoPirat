# VideoDownloader Telegram Bot

Бот для скачивания видео из популярных социальных сетей через Telegram.

## 🎯 Функциональные возможности

- Скачивание видео из нескольких платформ: Instagram, TikTok, Twitter/X, YouTube, Facebook и LinkedIn
- Автоматическое сжатие видео для соответствия ограничениям Telegram (до 50 МБ)
- Обработка видео различных форматов и конвертация их в MP4
- Простой интерфейс: просто отправьте ссылку, и бот сделает всё остальное

## 🌐 Поддерживаемые платформы

- **Instagram**: посты и Reels
- **TikTok**: видео
- **Twitter/X**: видео из твитов
- **YouTube**: видео
- **Facebook**: видео из постов
- **LinkedIn**: видео из постов

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- Telegram Bot API токен (получите его у [@BotFather](https://t.me/BotFather))

### Установка и запуск

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/videodownloader-bot.git
   cd videodownloader-bot
   ```

2. Создайте файл `.env` с вашим токеном бота:
   ```
   BOT_TOKEN=your_telegram_bot_token_here
   ```

3. Соберите и запустите Docker-контейнер:
   ```bash
   docker-compose up -d --build
   ```

4. Бот готов к использованию! Отправьте `/start` вашему боту в Telegram.

### Развертывание на Railway

Для быстрого развертывания нажмите кнопку ниже:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https%3A%2F%2Fgithub.com%2FF4r5ight%2FVideoPirat)

Не забудьте установить переменную окружения `BOT_TOKEN` в настройках Railway.

## 🔧 Использование

1. Запустите бот, отправив команду `/start`
2. Получите инструкции по использованию с помощью команды `/инфо`
3. Скопируйте ссылку на видео из поддерживаемой социальной сети
4. Отправьте ссылку боту
5. Дождитесь, пока бот скачает и отправит вам видео

## 📋 Команды бота

- `/start` или `/старт` - запустить бота и получить приветственное сообщение
- `/help` или `/инфо` - вывести информацию о поддерживаемых форматах и командах

## 🛠️ Технический стек

- Python 3.10
- Flask - для обработки вебхуков
- python-telegram-bot - для взаимодействия с Telegram API
- yt-dlp - для скачивания видео с большинства платформ
- instaloader - для скачивания видео с Instagram
- FFmpeg - для обработки и сжатия видео

## 📝 Особенности работы с разными платформами

### Instagram
Для скачивания видео с Instagram используется библиотека instaloader.

### LinkedIn
Для LinkedIn требуются специальные HTTP-заголовки, имитирующие реальный браузер. Скачивание видео с закрытых профилей может быть ограничено.

### YouTube, TikTok, Facebook, Twitter
Для этих платформ используется yt-dlp с оптимизированными настройками для каждой платформы.

## ⚙️ Конфигурация

Бот настраивается через переменные окружения:

- `BOT_TOKEN` - токен Telegram Bot API (обязательный)
- `PORT` - порт для запуска Flask-сервера (по умолчанию: 8080)

## 🔍 Решение проблем

### Бот не скачивает видео с LinkedIn
- Убедитесь, что видео общедоступно
- Попробуйте обновить yt-dlp до последней версии
- Проверьте, что URL соответствует формату публичного поста с видео

### Видео не отправляется из-за большого размера
- Бот автоматически пытается сжать видео до размера менее 50 МБ
- Для особенно длинных видео сжатие может быть недостаточным
- В этом случае лучше использовать прямую ссылку на YouTube или другие платформы

## 🔄 Обновление

Для обновления бота выполните:

```bash
git pull
docker-compose down
docker-compose up -d --build
```

## ❗️ Отказ от ответственности

Этот бот предназначен только для личного использования. Пожалуйста, уважайте авторские права и условия обслуживания платформ, видео с которых вы скачиваете.
