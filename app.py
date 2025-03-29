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
import telegram
from telegram import Bot
from telegram.ext import ApplicationBuilder

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

# Создаем директории
os.makedirs('temp', exist_ok=True)

# Поддерживаемые социальные сети и их паттерны URL
SUPPORTED_PLATFORMS = {
    'instagram': r'https?://(www\.)?(instagram\.com|instagr\.am)/(?:p|reel)/[^/]+',
    'tiktok': r'https?://(www\.)?(tiktok\.com)/(@[^/]+)/video/\d+',
    'twitter': r'https?://(www\.)?(twitter\.com|x\.com)/[^/]+/status/\d+',
    'youtube': r'https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[^&\s]+',
    'facebook': r'https?://(www\.)?(facebook\.com|fb\.watch)/[^/]+(/videos/|/watch/\?v=)\d+',
}

# Инициализируем бота (асинхронная версия для вебхуков)
bot = Bot(token=BOT_TOKEN)

# Инициализируем синхронное приложение для отправки сообщений
application = ApplicationBuilder().token(BOT_TOKEN).build()


def send_start_message(chat_id):
    """Отправляет приветственное сообщение"""
    try:
        logger.info(f"Отправка приветственного сообщения пользователю {chat_id}")
        # Используем bot вместо application.bot
        bot.send_message(
            chat_id=chat_id,
            text="👋 Привет! Я бот для скачивания видео из соцсетей.\n\n"
                 "Просто отправь мне ссылку на пост из Instagram, TikTok, Twitter, YouTube или Facebook, "
                 "и я извлеку видео для тебя.\n\n"
                 "Для получения справки используй команду /инфо"
        )
        logger.info(f"Приветственное сообщение успешно отправлено пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке приветственного сообщения: {e}")


def send_info_message(chat_id):
    """Отправляет справочное сообщение"""
    try:
        logger.info(f"Отправка справочного сообщения пользователю {chat_id}")
        bot.send_message(
            chat_id=chat_id,
            text="📋 <b>Инструкция по использованию бота</b>\n\n"
                 "1. Скопируйте ссылку на пост с видео из поддерживаемой соцсети\n"
                 "2. Отправьте эту ссылку мне в сообщении\n"
                 "3. Дождитесь, пока я скачаю и отправлю вам видео\n\n"
                 "<b>Поддерживаемые платформы:</b>\n"
                 "• Instagram (посты и Reels)\n"
                 "• TikTok\n"
                 "• Twitter/X\n"
                 "• YouTube\n"
                 "• Facebook\n\n"
                 "<b>Команды бота:</b>\n"
                 "/старт - запустить бота\n"
                 "/инфо - показать эту справку",
            parse_mode="HTML"
        )
        logger.info(f"Справочное сообщение успешно отправлено пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке справочного сообщения: {e}")


def extract_url(text):
    """Извлекает URL из текста сообщения"""
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, text)
    if urls:
        return urls[0]
    return None


def is_supported_url(url):
    """Проверяет, поддерживается ли URL"""
    for platform, pattern in SUPPORTED_PLATFORMS.items():
        if re.match(pattern, url):
            return True
    return False


def get_platform(url):
    """Определяет платформу по URL"""
    domain = urlparse(url).netloc
    if 'instagram' in domain or 'instagr.am' in domain:
        return 'instagram'
    elif 'tiktok' in domain:
        return 'tiktok'
    elif 'twitter' in domain or 'x.com' in domain:
        return 'twitter'
    elif 'youtube' in domain or 'youtu.be' in domain:
        return 'youtube'
    elif 'facebook' in domain or 'fb.watch' in domain:
        return 'facebook'
    return 'unknown'


def cleanup_temp_files():
    """Удаляет старые временные файлы"""
    try:
        for file in os.listdir('temp'):
            file_path = os.path.join('temp', file)
            if os.path.isfile(file_path) and (time.time() - os.path.getmtime(file_path)) > 3600:  # Старше 1 часа
                os.remove(file_path)
                logger.info(f"Удален старый временный файл: {file_path}")
    except Exception as e:
        logger.error(f"Ошибка при очистке временных файлов: {e}")


def download_video(url, platform):
    """Скачивает видео с использованием yt-dlp"""
    try:
        # Преобразование URL для Instagram через прокси-сервис (если нужно)
        if platform == 'instagram' and os.environ.get("USE_INSTAGRAM_PROXY", "0") == "1":
            # Используем прокси для Instagram
            url = f"https://www.ddinstagram.com/{url.split('instagram.com/')[1]}"
            logger.info(f"Используем прокси для Instagram: {url}")

        # Опции для yt-dlp с оптимизацией размера/качества
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            'outtmpl': 'temp/%(title)s_%(id)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 60,  # Увеличенный таймаут
            # Добавляем хедеры для имитации браузера
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
        }

        # Скачиваем видео
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)

            # Проверяем, что файл существует
            if os.path.exists(video_path):
                # Если файл не mp4, конвертируем его с помощью ffmpeg
                if not video_path.endswith('.mp4'):
                    new_path = f"{os.path.splitext(video_path)[0]}.mp4"
                    cmd = f"ffmpeg -i \"{video_path}\" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k \"{new_path}\""
                    subprocess.call(cmd, shell=True)

                    if os.path.exists(new_path):
                        if os.path.exists(video_path):
                            os.remove(video_path)
                        video_path = new_path

            return video_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании видео: {e}")
        raise


def compress_video(video_path):
    """Сжимает видео для Telegram"""
    compressed_path = f"{os.path.splitext(video_path)[0]}_compressed.mp4"

    # Сжимаем видео для Telegram
    cmd = f"ffmpeg -i \"{video_path}\" -c:v libx264 -crf 28 -preset faster -vf scale=-2:480 -r 24 -c:a aac -b:a 96k \"{compressed_path}\""
    subprocess.call(cmd, shell=True)

    # Проверяем результат сжатия
    if os.path.exists(compressed_path) and os.path.getsize(compressed_path) <= 50 * 1024 * 1024:
        return compressed_path

    # Если видео всё еще слишком большое, пробуем ещё сильнее сжать
    more_compressed_path = f"{os.path.splitext(video_path)[0]}_more_compressed.mp4"
    cmd = f"ffmpeg -i \"{video_path}\" -c:v libx264 -crf 32 -preset faster -vf scale=-2:360 -r 20 -c:a aac -b:a 64k \"{more_compressed_path}\""
    subprocess.call(cmd, shell=True)

    if os.path.exists(more_compressed_path) and os.path.getsize(more_compressed_path) <= 50 * 1024 * 1024:
        # Удаляем первую сжатую версию
        if os.path.exists(compressed_path):
            os.remove(compressed_path)
        return more_compressed_path

    # Если не удалось сжать до нужного размера
    return None


def cleanup_video_files(video_path):
    """Удаляет все связанные с видео временные файлы"""
    temp_files = [
        video_path,
        f"{os.path.splitext(video_path)[0]}_compressed.mp4",
        f"{os.path.splitext(video_path)[0]}_more_compressed.mp4"
    ]

    for file in temp_files:
        if os.path.exists(file):
            os.remove(file)


def download_and_send_video(url, platform, chat_id, status_message_id):
    """Скачивает и отправляет видео"""
    try:
        # Очищаем старые временные файлы
        cleanup_temp_files()

        # Скачиваем видео
        video_path = download_video(url, platform)

        # Проверяем размер файла
        file_size = os.path.getsize(video_path)
        max_telegram_size = 50 * 1024 * 1024  # 50 МБ в байтах

        if file_size > max_telegram_size:
            # Если файл слишком большой, пробуем сжать сильнее
            application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text="⏳ Видео слишком большое, применяю дополнительное сжатие..."
            )

            compressed_path = compress_video(video_path)
            if compressed_path:
                video_path = compressed_path
            else:
                application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text="❌ Видео слишком большое для отправки в Telegram даже после сжатия (>50MB)"
                )
                # Удаляем временные файлы
                cleanup_video_files(video_path)
                return

        # Отправляем видео в чат
        with open(video_path, 'rb') as video_file:
            application.bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption=f"🎬 Видео из {platform.capitalize()}\n🔗 {url}",
                supports_streaming=True
            )

        # Удаляем статусное сообщение
        application.bot.delete_message(chat_id=chat_id, message_id=status_message_id)

        # Удаляем временные файлы
        cleanup_video_files(video_path)

    except Exception as e:
        # В случае ошибки информируем пользователя
        error_message = str(e)
        short_error = error_message[:100] + "..." if len(error_message) > 100 else error_message

        error_text = "❌ Произошла ошибка при скачивании видео"

        if "Unsupported URL" in error_message:
            error_text = "❌ Не удалось скачать видео: ссылка не поддерживается или контент недоступен."
        elif "Private video" in error_message or "This video is private" in error_message:
            error_text = "❌ Это приватное видео, доступ к нему ограничен."
        elif "Login required" in error_message or "sign in" in error_message.lower():
            error_text = "❌ Для доступа к этому контенту требуется авторизация."

        try:
            application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text=f"{error_text}: {short_error}"
            )
        except Exception:
            # Если не удалось отредактировать сообщение, отправляем новое
            bot.send_message(chat_id=chat_id, text=f"{error_text}: {short_error}")

        logger.error(f"Ошибка при обработке URL {url}: {e}")


# Асинхронная функция для установки вебхука
async def set_webhook_async(webhook_url):
    """Асинхронно устанавливает вебхук"""
    try:
        logger.info(f"Удаляем текущий вебхук...")
        await bot.delete_webhook()

        logger.info(f"Устанавливаем новый вебхук на {webhook_url}")
        webhook_info = await bot.set_webhook(url=webhook_url)

        logger.info(f"Вебхук успешно установлен: {webhook_info}")
        return f'Webhook настроен на {webhook_url}. Результат: {webhook_info}'
    except Exception as e:
        logger.error(f"Ошибка в асинхронной функции настройки вебхука: {e}")
        raise  # Пробрасываем ошибку выше для обработки


# Обработчик вебхука Telegram
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Обрабатывает входящие обновления от Telegram"""
    try:
        update_data = request.get_json(force=True)
        logger.info(f"Получено обновление: {update_data}")

        # Проверяем наличие сообщения
        if 'message' not in update_data:
            return 'OK'

        chat_id = update_data['message']['chat']['id']

        # Проверяем наличие текста
        if 'text' not in update_data['message']:
            return 'OK'

        text = update_data['message']['text']
        logger.info(f"Получено сообщение от {chat_id}: {text}")

        # Обработка команд
        if text.startswith('/start') or text.startswith('/старт'):
            logger.info(f"Обработка команды /старт от {chat_id}")
            send_start_message(chat_id)
            return 'OK'

        if text.startswith('/help') or text.startswith('/инфо'):
            logger.info(f"Обработка команды /инфо от {chat_id}")
            send_info_message(chat_id)
            return 'OK'

        # Обработка URL
        url = extract_url(text)
        if url and is_supported_url(url):
            platform = get_platform(url)
            logger.info(f"Обнаружена ссылка на {platform} от {chat_id}: {url}")

            # Отправляем сообщение о начале обработки
            status_message = bot.send_message(
                chat_id=chat_id,
                text=f"⏳ Скачиваю видео из {platform.capitalize()}..."
            )

            # Запускаем обработку видео в отдельном потоке
            thread = threading.Thread(
                target=download_and_send_video,
                args=(url, platform, chat_id, status_message.message_id)
            )
            thread.daemon = True  # Поток будет завершен при завершении основного процесса
            thread.start()
        else:
            # Если сообщение не является командой и не содержит URL
            if not text.startswith('/'):
                logger.info(f"Отправка информационного сообщения пользователю {chat_id}")
                bot.send_message(
                    chat_id=chat_id,
                    text="Пожалуйста, отправьте ссылку на видео из поддерживаемой соцсети. Для получения справки используйте команду /инфо"
                )

    except Exception as e:
        logger.error(f"Ошибка при обработке webhook: {e}")

    return 'OK'


# Маршрут для проверки работоспособности сервера
@app.route('/')
def index():
    return 'Бот работает!'


# Маршрут для настройки вебхука
@app.route('/set_webhook')
def set_webhook_route():
    """Синхронный маршрут для асинхронной настройки вебхука"""
    # Получаем URL приложения от Railway
    # Railway использует разные переменные окружения в разных версиях
    app_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    webhook_base_url = None

    if app_domain:
        # Проверяем, включает ли домен протокол
        if not app_domain.startswith(('http://', 'https://')):
            webhook_base_url = f"https://{app_domain}"
        else:
            webhook_base_url = app_domain
    else:
        # Другие возможные переменные окружения
        static_url = os.environ.get('RAILWAY_STATIC_URL')
        if static_url:
            webhook_base_url = static_url
        else:
            # Резервный вариант
            webhook_base_url = os.environ.get('APP_URL', 'https://your-app-url.railway.app')

    # Удаляем возможные слеши в конце URL
    if webhook_base_url.endswith('/'):
        webhook_base_url = webhook_base_url[:-1]

    webhook_url = f"{webhook_base_url}/{BOT_TOKEN}"

    logger.info(f"Пытаемся установить вебхук на: {webhook_url}")

    try:
        # Запускаем асинхронную функцию в синхронном контексте
        result = asyncio.run(set_webhook_async(webhook_url))
        return result
    except Exception as e:
        logger.error(f"Ошибка при настройке вебхука: {e}")
        # Пробуем с альтернативным URL форматом
        alt_webhook_base_url = f"https://{os.environ.get('RAILWAY_SERVICE_NAME', 'videopirat')}.up.railway.app"
        alt_webhook_url = f"{alt_webhook_base_url}/{BOT_TOKEN}"
        logger.info(f"Пробуем альтернативный URL: {alt_webhook_url}")

        try:
            result = asyncio.run(set_webhook_async(alt_webhook_url))
            return result
        except Exception as e2:
            logger.error(f"Ошибка при настройке вебхука (альтернативный URL): {e2}")
            return f'Не удалось настроить webhook: Попробовали {webhook_url} и {alt_webhook_url}'


# Маршрут для удаления вебхука
@app.route('/remove_webhook')
def remove_webhook():
    """Удаляет вебхук"""
    try:
        asyncio.run(bot.delete_webhook())
        return 'Webhook удален'
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
        return f'Ошибка при удалении webhook: {e}'


if __name__ == '__main__':
    # Определяем порт из переменных окружения (для Railway)
    port = int(os.environ.get('PORT', 8080))

    # Получаем URL приложения - это должно быть отдельно от настройки вебхука
    try:
        app_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        webhook_base_url = None

        if app_domain:
            if not app_domain.startswith(('http://', 'https://')):
                webhook_base_url = f"https://{app_domain}"
            else:
                webhook_base_url = app_domain
        else:
            webhook_base_url = os.environ.get('RAILWAY_STATIC_URL')
            if not webhook_base_url:
                webhook_base_url = f"https://{os.environ.get('RAILWAY_SERVICE_NAME', 'videopirat')}.up.railway.app"

        # Удаляем возможные слеши в конце URL
        if webhook_base_url.endswith('/'):
            webhook_base_url = webhook_base_url[:-1]

        webhook_url = f"{webhook_base_url}/{BOT_TOKEN}"
        logger.info(f"Настраиваем вебхук на {webhook_url}")

        # Запускаем в отдельном потоке, чтобы не блокировать запуск сервера
        threading.Thread(
            target=lambda: asyncio.run(set_webhook_async(webhook_url)),
            daemon=True
        ).start()
    except Exception as e:
        logger.error(f"Ошибка при настройке вебхука при запуске: {e}")
        logger.info(
            "Продолжаем запуск сервера без настройки вебхука. Вы можете настроить вебхук вручную через /set_webhook")

    # Запускаем сервер
    app.run(host='0.0.0.0', port=port)