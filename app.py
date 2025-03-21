import os
import re
import time
import asyncio
import logging
import threading
import subprocess
from flask import Flask, request
from urllib.parse import urlparse
import yt_dlp
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не указан токен бота (BOT_TOKEN)")

# Создаем Flask-приложение для обработки вебхуков
app = Flask(__name__)

# Инициализируем бота
application = ApplicationBuilder().token(BOT_TOKEN).build()

def extract_url(text):
    """Извлекает URL из текста сообщения"""
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else None

def download_video(url):
    """Скачивает видео с помощью yt-dlp"""
    ydl_opts = {
        'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
        'outtmpl': 'temp/%(title)s_%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Ошибка при скачивании видео: {e}")
        return None

def compress_video(video_path):
    """Сжимает видео для Telegram"""
    compressed_path = f"{os.path.splitext(video_path)[0]}_compressed.mp4"
    cmd = f"ffmpeg -i \"{video_path}\" -c:v libx264 -crf 28 -preset fast -c:a aac -b:a 96k \"{compressed_path}\""
    subprocess.call(cmd, shell=True)
    return compressed_path if os.path.exists(compressed_path) else None

async def start(update: Update, context):
    """Отправляет приветственное сообщение"""
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео из соцсетей.\n\n"
        "Просто отправь мне ссылку на пост из Instagram, TikTok, Twitter, YouTube или Facebook, "
        "и я извлеку видео для тебя.\n\n"
        "Для получения справки используй команду /инфо"
    )

async def info(update: Update, context):
    """Отправляет справочное сообщение"""
    await update.message.reply_text(
        "📋 Инструкция по использованию бота. Просто отправьте ссылку на видео."
    )

async def handle_message(update: Update, context):
    """Обрабатывает сообщения с ссылками"""
    text = update.message.text
    url = extract_url(text)
    if url:
        await update.message.reply_text(f"⏳ Обрабатываю ссылку: {url}")
        video_path = download_video(url)
        if video_path:
            compressed_video = compress_video(video_path)
            with open(compressed_video or video_path, 'rb') as video:
                await update.message.reply_video(video=video, caption="🎬 Ваше видео готово!")
        else:
            await update.message.reply_text("❌ Не удалось скачать видео.")
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте ссылку на видео.")

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Обрабатывает входящие обновления от Telegram"""
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        asyncio.run(application.process_update(update))
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook: {e}")
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

    # Настройка обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск бота
    application.run_polling()
