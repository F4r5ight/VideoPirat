import os
import re
import time as time_module
import random
import asyncio
import logging
import threading
import subprocess
from flask import Flask, request
from urllib.parse import urlparse
import yt_dlp
import requests
from telegram import Bot
from telegram.ext import ApplicationBuilder
import instaloader
import glob
import shutil

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не указан токен бота (BOT_TOKEN)")

app = Flask(__name__)

os.makedirs('temp', exist_ok=True)

SUPPORTED_PLATFORMS = {
    'instagram': r'https?://(www\.)?(instagram\.com|instagr\.am)/(?:p|reel)/[^/]+',
    'tiktok': r'https?://(www\.)?(tiktok\.com)/(@[^/]+)/video/\d+',
    'twitter': r'https?://(www\.)?(twitter\.com|x\.com)/[^/]+/status/\d+',
    'youtube': r'https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[^&\s]+',
    'facebook': r'https?://(www\.)?(facebook\.com|fb\.watch)/[^/]+(/videos/|/watch/\?v=)\d+',
    'linkedin': r'https?://(www\.)?(linkedin\.com)/posts/[^/]+(?:-[^/]+)*-(?:activity-|ugcPost-)\d+',
}

bot = Bot(token=BOT_TOKEN)

application = ApplicationBuilder().token(BOT_TOKEN).build()


def send_start_message(chat_id):
    try:
        logger.info(f"Отправка приветственного сообщения пользователю {chat_id}")

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "👋 Привет! Я бот для скачивания видео из соцсетей.\n\n"
                    "Просто отправь мне ссылку на пост из Instagram, TikTok, Twitter, YouTube, Facebook или LinkedIn, "
                    "и я извлеку видео для тебя.\n\n"
                    "Для получения справки используй команду /инфо"
        }
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            logger.info(f"Приветственное сообщение успешно отправлено пользователю {chat_id}")
        else:
            logger.error(f"Ошибка при отправке сообщения: {response.text}")

    except Exception as e:
        logger.error(f"Ошибка при отправке приветственного сообщения: {e}")


def send_info_message(chat_id):
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
                 "• Facebook\n"
                 "• LinkedIn\n\n"
                 "<b>Команды бота:</b>\n"
                 "/старт - запустить бота\n"
                 "/инфо - показать эту справку",
            parse_mode="HTML"
        )
        logger.info(f"Справочное сообщение успешно отправлено пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке справочного сообщения: {e}")


def extract_url(text):
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, text)
    if urls:
        return urls[0]
    return None


def is_supported_url(url):
    for platform, pattern in SUPPORTED_PLATFORMS.items():
        if re.match(pattern, url):
            return True
    return False


def get_platform(url):
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
    elif 'linkedin' in domain:
        return 'linkedin'
    return 'unknown'


def cleanup_temp_files():
    try:
        for file in os.listdir('temp'):
            file_path = os.path.join('temp', file)
            if os.path.isfile(file_path) and (time_module.time() - os.path.getmtime(file_path)) > 3600:  # Старше 1 часа
                os.remove(file_path)
                logger.info(f"Удален старый временный файл: {file_path}")
    except Exception as e:
        logger.error(f"Ошибка при очистке временных файлов: {e}")


def download_video(url, platform):
    try:
        if platform == 'instagram':


            user_agents = [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
                "Mozilla/5.0 (Android 12; Mobile; rv:98.0) Gecko/98.0 Firefox/98.0",
                "Instagram 219.0.0.12.117 Android"
            ]

            match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', url)
            if not match:
                raise ValueError("Не удалось извлечь ID поста из URL Instagram")

            shortcode = match.group(1)
            logger.info(f"Извлечен shortcode Instagram: {shortcode}")

            def try_instaloader():
                user_agent = random.choice(user_agents)

                L = instaloader.Instaloader(
                    download_videos=True,
                    download_video_thumbnails=False,
                    download_geotags=False,
                    download_comments=False,
                    save_metadata=False,
                    post_metadata_txt_pattern="",
                    dirname_pattern="temp",
                    user_agent=user_agent
                )

                instagram_username = os.environ.get("INSTAGRAM_USERNAME", "")
                instagram_password = os.environ.get("INSTAGRAM_PASSWORD", "")

                if instagram_username and instagram_password:
                    try:
                        logger.info(f"Попытка авторизации в Instagram под пользователем {instagram_username}")
                        L.login(instagram_username, instagram_password)
                        logger.info("Авторизация в Instagram успешна")
                    except Exception as e:
                        logger.warning(f"Не удалось авторизоваться в Instagram: {e}")

                temp_dir = f"temp/{shortcode}"
                os.makedirs(temp_dir, exist_ok=True)

                logger.info(f"Скачиваем пост Instagram с ID: {shortcode}")

                max_retries = 3
                retry_delay = 5
                success = False

                for attempt in range(max_retries):
                    try:
                        post = instaloader.Post.from_shortcode(L.context, shortcode)
                        L.download_post(post, target=temp_dir)
                        success = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
                            logger.info(f"Ожидание {retry_delay} секунд перед следующей попыткой...")
                            time_module.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            logger.error(f"Все попытки скачать через instaloader не удались: {e}")
                            return None

                if not success:
                    return None

                video_path = f"temp/{shortcode}.mp4"

                downloaded_files = glob.glob(f"{temp_dir}/*.mp4")

                if not downloaded_files:
                    downloaded_files = glob.glob(f"temp/*.mp4")
                    downloaded_files.sort(key=os.path.getmtime, reverse=True)

                if downloaded_files:
                    latest_file = downloaded_files[0]
                    logger.info(f"Найден видеофайл: {latest_file}")

                    if os.path.exists(video_path) and video_path != latest_file:
                        os.remove(video_path)

                    if latest_file == video_path:
                        logger.info(f"Видео Instagram уже в нужном месте: {video_path}")
                    else:
                        shutil.copy2(latest_file, video_path)
                        logger.info(f"Скопировано видео из {latest_file} в {video_path}")

                    if os.path.exists(temp_dir) and temp_dir != "temp":
                        shutil.rmtree(temp_dir)

                    logger.info(f"Видео Instagram успешно скачано через instaloader: {video_path}")
                    return video_path
                else:
                    logger.warning("Не удалось найти скачанное видео через instaloader")
                    return None

            video_path = try_instaloader()

            if not video_path:
                logger.info("Попытка скачать через yt-dlp в качестве запасного метода")
                try:
                    ydl_opts = {
                        'format': 'best[ext=mp4]/best',
                        'outtmpl': f'temp/{shortcode}.%(ext)s',
                        'quiet': True,
                        'no_warnings': True,
                        'cookiefile': 'instagram_cookies.txt',  # Путь к файлу с cookies
                        'http_headers': {
                            'User-Agent': random.choice(user_agents),
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept': '*/*',
                            'Referer': 'https://www.instagram.com/'
                        }
                    }

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    for ext in ['mp4', 'mkv', 'webm']:
                        video_path = f'temp/{shortcode}.{ext}'
                        if os.path.exists(video_path):
                            logger.info(f"Видео Instagram успешно скачано через yt-dlp: {video_path}")

                            if not video_path.endswith('.mp4'):
                                new_path = f"temp/{shortcode}.mp4"
                                cmd = f"ffmpeg -i \"{video_path}\" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k \"{new_path}\""
                                subprocess.call(cmd, shell=True)

                                if os.path.exists(new_path):
                                    if os.path.exists(video_path):
                                        os.remove(video_path)
                                    video_path = new_path

                            return video_path

                    raise ValueError("Не удалось найти скачанное видео через yt-dlp")

                except Exception as ytdl_err:
                    logger.error(f"Не удалось скачать через yt-dlp: {ytdl_err}")
                    raise ValueError(f"Не удалось скачать видео с Instagram ни одним из методов")

            return video_path

        else:
            logger.info(f"Используем yt-dlp для скачивания видео с {platform}")

            ydl_opts = {
                'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
                'outtmpl': 'temp/%(title)s_%(id)s.%(ext)s',
                'restrictfilenames': True,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 60,
            }

            if platform == 'linkedin':
                ydl_opts['http_headers'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Referer': 'https://www.linkedin.com/',
                    'sec-ch-ua': '"Chromium";v="96", "Google Chrome";v="96"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1'
                }
                ydl_opts['retries'] = 10
                ydl_opts['fragment_retries'] = 10
                ydl_opts['socket_timeout'] = 120
            elif platform == 'twitter' or platform == 'x':
                ydl_opts['http_headers'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Referer': 'https://twitter.com/'
                }
            elif platform == 'facebook':
                ydl_opts['http_headers'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Referer': 'https://www.facebook.com/'
                }
            else:
                ydl_opts['http_headers'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Referer': 'https://www.google.com/'
                }

            max_retries = 3
            retry_delay = 3

            for attempt in range(max_retries):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        video_path = ydl.prepare_filename(info)

                        if os.path.exists(video_path):
                            if not video_path.endswith('.mp4'):
                                new_path = f"{os.path.splitext(video_path)[0]}.mp4"
                                cmd = f"ffmpeg -i \"{video_path}\" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k \"{new_path}\""
                                subprocess.call(cmd, shell=True)

                                if os.path.exists(new_path):
                                    if os.path.exists(video_path):
                                        os.remove(video_path)
                                    video_path = new_path

                            logger.info(f"Видео успешно скачано: {video_path}")
                            return video_path

                    raise ValueError("Не удалось найти скачанное видео")

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
                        logger.info(f"Ожидание {retry_delay} секунд перед следующей попыткой...")
                        time_module.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(f"Все попытки скачать через yt-dlp не удались: {e}")
                        raise

    except Exception as e:
        logger.error(f"Ошибка при скачивании видео: {e}")
        raise


def compress_video(video_path):
    compressed_path = f"{os.path.splitext(video_path)[0]}_compressed.mp4"

    try:
        probe_cmd = f"ffprobe -v error -select_streams v:0 -show_entries stream=width,height,display_aspect_ratio -of csv=s=,:p=0 \"{video_path}\""
        probe_result = subprocess.check_output(probe_cmd, shell=True, text=True).strip().split(',')

        if len(probe_result) >= 2:
            width, height = int(probe_result[0]), int(probe_result[1])
            aspect_ratio = float(width) / float(height)

            logger.info(f"Оригинальное видео: {width}x{height}, соотношение сторон: {aspect_ratio:.2f}")

            if height > width:
                logger.info("Обнаружено вертикальное видео, применяю специальную обработку для мобильных устройств")

                target_height = min(720, height)
                target_width = int(target_height * aspect_ratio)
                target_width = target_width - (target_width % 2)

                filter_complex = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,setsar=1:1,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"

                cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 26 -preset fast ' \
                      f'-vf "{filter_complex}" ' \
                      f'-r 30 -c:a aac -b:a 128k ' \
                      f'-movflags +faststart -pix_fmt yuv420p "{compressed_path}"'

                logger.info(f"Запуск команды для вертикального видео: {cmd}")
                subprocess.call(cmd, shell=True)
            else:
                logger.info("Обнаружено горизонтальное видео")

                target_width = min(720, width)
                target_height = int(target_width / aspect_ratio)
                target_height = target_height - (target_height % 2)

                filter_complex = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,setsar=1:1,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"

                cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 26 -preset fast ' \
                      f'-vf "{filter_complex}" ' \
                      f'-r 30 -c:a aac -b:a 128k ' \
                      f'-movflags +faststart -pix_fmt yuv420p "{compressed_path}"'

                logger.info(f"Запуск команды для горизонтального видео: {cmd}")
                subprocess.call(cmd, shell=True)
        else:
            logger.warning("Не удалось определить размеры видео, использую безопасный метод сжатия")

            cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 28 -preset fast ' \
                  f'-vf "scale=-2:540:force_original_aspect_ratio=decrease,pad=720:540:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1" ' \
                  f'-r 30 -c:a aac -b:a 128k ' \
                  f'-movflags +faststart -pix_fmt yuv420p "{compressed_path}"'

            logger.info(f"Запуск безопасного метода сжатия: {cmd}")
            subprocess.call(cmd, shell=True)
    except Exception as e:
        logger.error(f"Ошибка при анализе видео: {e}")

        cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 28 -preset fast ' \
              f'-vf "scale=-2:540:force_original_aspect_ratio=decrease,pad=720:540:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1" ' \
              f'-r 30 -c:a aac -b:a 128k ' \
              f'-movflags +faststart -pix_fmt yuv420p "{compressed_path}"'

        logger.info(f"Запуск запасного метода сжатия: {cmd}")
        subprocess.call(cmd, shell=True)

    if os.path.exists(compressed_path) and os.path.getsize(compressed_path) <= 50 * 1024 * 1024:
        logger.info(f"Видео успешно сжато: {compressed_path}")
        return compressed_path

    more_compressed_path = f"{os.path.splitext(video_path)[0]}_more_compressed.mp4"

    try:
        probe_cmd = f"ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=,:p=0 \"{video_path}\""
        probe_result = subprocess.check_output(probe_cmd, shell=True, text=True).strip().split(',')

        if len(probe_result) >= 2:
            width, height = int(probe_result[0]), int(probe_result[1])
            aspect_ratio = float(width) / float(height)

            if height > width:
                target_height = min(480, height)
                target_width = int(target_height * aspect_ratio)
                target_width = target_width - (target_width % 2)

                filter_complex = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,setsar=1:1,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
            else:
                target_width = min(480, width)
                target_height = int(target_width / aspect_ratio)
                target_height = target_height - (target_height % 2)

                filter_complex = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,setsar=1:1,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"

            logger.info(f"Применяю дополнительное сжатие с размерами {target_width}x{target_height}")

            cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 32 -preset fast ' \
                  f'-vf "{filter_complex}" ' \
                  f'-r 24 -c:a aac -b:a 96k ' \
                  f'-movflags +faststart -pix_fmt yuv420p "{more_compressed_path}"'

            logger.info(f"Запуск команды для дополнительного сжатия: {cmd}")
            subprocess.call(cmd, shell=True)
        else:
            logger.warning("Не удалось определить размеры для дополнительного сжатия")

            cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 32 -preset fast ' \
                  f'-vf "scale=-2:360:force_original_aspect_ratio=decrease,pad=480:360:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1" ' \
                  f'-r 24 -c:a aac -b:a 96k ' \
                  f'-movflags +faststart -pix_fmt yuv420p "{more_compressed_path}"'

            logger.info(f"Запуск универсального метода дополнительного сжатия: {cmd}")
            subprocess.call(cmd, shell=True)
    except Exception as e:
        logger.error(f"Ошибка при дополнительном сжатии: {e}")

        cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 32 -preset fast ' \
              f'-vf "scale=-2:360:force_original_aspect_ratio=decrease,pad=480:360:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1" ' \
              f'-r 24 -c:a aac -b:a 96k ' \
              f'-movflags +faststart -pix_fmt yuv420p "{more_compressed_path}"'

        logger.info(f"Запуск запасного метода дополнительного сжатия: {cmd}")
        subprocess.call(cmd, shell=True)

    if os.path.exists(more_compressed_path) and os.path.getsize(more_compressed_path) <= 50 * 1024 * 1024:
        if os.path.exists(compressed_path):
            os.remove(compressed_path)
        logger.info(f"Видео успешно сжато с дополнительной компрессией: {more_compressed_path}")
        return more_compressed_path

    extreme_compressed_path = f"{os.path.splitext(video_path)[0]}_extreme_compressed.mp4"

    cmd = f'ffmpeg -i "{video_path}" -c:v libx264 -crf 40 -preset fast ' \
          f'-vf "scale=-2:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1" ' \
          f'-r 15 -c:a aac -b:a 48k ' \
          f'-movflags +faststart -pix_fmt yuv420p "{extreme_compressed_path}"'

    logger.info(f"Запуск экстремального метода сжатия: {cmd}")
    subprocess.call(cmd, shell=True)

    if os.path.exists(extreme_compressed_path) and os.path.getsize(extreme_compressed_path) <= 50 * 1024 * 1024:
        if os.path.exists(compressed_path):
            os.remove(compressed_path)
        if os.path.exists(more_compressed_path):
            os.remove(more_compressed_path)
        logger.info(f"Видео успешно сжато с экстремальной компрессией: {extreme_compressed_path}")
        return extreme_compressed_path

    logger.error("Не удалось сжать видео до размера менее 50 МБ")

    if os.path.exists(extreme_compressed_path):
        os.remove(extreme_compressed_path)
    if os.path.exists(more_compressed_path):
        os.remove(more_compressed_path)
    if os.path.exists(compressed_path):
        os.remove(compressed_path)

    return None


def cleanup_video_files(video_path):
    temp_files = [
        video_path,
        f"{os.path.splitext(video_path)[0]}_compressed.mp4",
        f"{os.path.splitext(video_path)[0]}_more_compressed.mp4"
    ]

    for file in temp_files:
        if os.path.exists(file):
            os.remove(file)


def download_and_send_video(url, platform, chat_id, status_message_id):
    try:
        cleanup_temp_files()

        video_path = download_video(url, platform)

        file_size = os.path.getsize(video_path)
        max_telegram_size = 50 * 1024 * 1024  # 50 МБ в байтах

        if file_size > max_telegram_size:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": status_message_id,
                    "text": "⏳ Видео слишком большое, применяю дополнительное сжатие..."
                }
            )

            compressed_path = compress_video(video_path)
            if compressed_path:
                video_path = compressed_path
            else:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                    json={
                        "chat_id": chat_id,
                        "message_id": status_message_id,
                        "text": "❌ Видео слишком большое для отправки в Telegram даже после сжатия (>50MB)"
                    }
                )
                cleanup_video_files(video_path)
                return

        with open(video_path, 'rb') as video_file:
            files = {
                'video': video_file
            }
            data = {
                'chat_id': chat_id,
                'caption': f"🎬 Видео из {platform.capitalize()}\n",
                'supports_streaming': 'true'
            }

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                files=files,
                data=data
            )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
            json={
                "chat_id": chat_id,
                "message_id": status_message_id
            }
        )

        cleanup_video_files(video_path)

    except Exception as e:
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
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": status_message_id,
                    "text": f"{error_text}: {short_error}"
                }
            )
        except Exception:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"{error_text}: {short_error}"
                }
            )

        logger.error(f"Ошибка при обработке URL {url}: {e}")


def download_and_send_video_no_status(url, platform, chat_id):
    try:
        cleanup_temp_files()

        video_path = download_video(url, platform)

        file_size = os.path.getsize(video_path)
        max_telegram_size = 50 * 1024 * 1024  # 50 МБ в байтах

        if file_size > max_telegram_size:
            compressed_path = compress_video(video_path)
            if compressed_path:
                video_path = compressed_path
            else:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "❌ Видео слишком большое для отправки в Telegram даже после сжатия (>50MB)"
                    }
                )
                cleanup_video_files(video_path)
                return

        with open(video_path, 'rb') as video_file:
            files = {
                'video': video_file
            }
            data = {
                'chat_id': chat_id,
                'caption': f"🎬 Видео из {platform.capitalize()}\n",
                'supports_streaming': 'true'
            }

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                files=files,
                data=data
            )

        cleanup_video_files(video_path)

    except Exception as e:
        error_message = str(e)
        short_error = error_message[:100] + "..." if len(error_message) > 100 else error_message

        error_text = "❌ Произошла ошибка при скачивании видео"

        if "Unsupported URL" in error_message:
            error_text = "❌ Не удалось скачать видео: ссылка не поддерживается или контент недоступен."
        elif "Private video" in error_message or "This video is private" in error_message:
            error_text = "❌ Это приватное видео, доступ к нему ограничен."
        elif "Login required" in error_message or "sign in" in error_message.lower():
            error_text = "❌ Для доступа к этому контенту требуется авторизация."

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"{error_text}: {short_error}"
            }
        )

        logger.error(f"Ошибка при обработке URL {url}: {e}")


async def set_webhook_async(webhook_url):
    try:
        logger.info(f"Удаляем текущий вебхук...")
        await bot.delete_webhook()

        logger.info(f"Устанавливаем новый вебхук на {webhook_url}")
        webhook_info = await bot.set_webhook(url=webhook_url)

        logger.info(f"Вебхук успешно установлен: {webhook_info}")
        return f'Webhook настроен на {webhook_url}. Результат: {webhook_info}'
    except Exception as e:
        logger.error(f"Ошибка в асинхронной функции настройки вебхука: {e}")
        raise


@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    try:
        update_data = request.get_json(force=True)
        logger.info(f"Получено обновление: {update_data}")

        if 'message' not in update_data:
            return 'OK'

        chat_id = update_data['message']['chat']['id']

        if 'text' not in update_data['message']:
            return 'OK'

        text = update_data['message']['text']
        logger.info(f"Получено сообщение от {chat_id}: {text}")

        if text.startswith('/start') or text.startswith('/старт'):
            logger.info(f"Обработка команды /старт от {chat_id}")
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "👋 Привет! Я бот для скачивания видео из соцсетей.\n\n"
                            "Просто отправь мне ссылку на пост из Instagram, TikTok, Twitter, YouTube или Facebook или LinkedIn, "
                            "и я извлеку видео для тебя.\n\n"
                            "Для получения справки используй команду /инфо"
                }
            )
            return 'OK'

        if text.startswith('/help') or text.startswith('/инфо'):
            logger.info(f"Обработка команды /инфо от {chat_id}")
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "📋 <b>Инструкция по использованию бота</b>\n\n"
                            "1. Скопируйте ссылку на пост с видео из поддерживаемой соцсети\n"
                            "2. Отправьте эту ссылку мне в сообщении\n"
                            "3. Дождитесь, пока я скачаю и отправлю вам видео\n\n"
                            "<b>Поддерживаемые платформы:</b>\n"
                            "• Instagram (посты и Reels)\n"
                            "• TikTok\n"
                            "• Twitter/X\n"
                            "• YouTube\n"
                            "• Facebook\n"
                            "• LinkedIn\n\n"
                            "<b>Команды бота:</b>\n"
                            "/старт - запустить бота\n"
                            "/инфо - показать эту справку",
                    "parse_mode": "HTML"
                }
            )
            return 'OK'

        url = extract_url(text)
        if url and is_supported_url(url):
            platform = get_platform(url)
            logger.info(f"Обнаружена ссылка на {platform} от {chat_id}: {url}")

            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"⏳ Скачиваю видео из {platform.capitalize()}..."
                }
            )

            status_message_id = None
            if response.status_code == 200:
                response_json = response.json()
                if response_json['ok']:
                    status_message_id = response_json['result']['message_id']

            if status_message_id:
                thread = threading.Thread(
                    target=download_and_send_video,
                    args=(url, platform, chat_id, status_message_id)
                )
                thread.daemon = True
                thread.start()
            else:
                thread = threading.Thread(
                    target=download_and_send_video_no_status,
                    args=(url, platform, chat_id)
                )
                thread.daemon = True
                thread.start()
        else:
            if not text.startswith('/'):
                logger.info(f"Отправка информационного сообщения пользователю {chat_id}")
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "Пожалуйста, отправьте ссылку на видео из поддерживаемой соцсети. Для получения справки используйте команду /инфо"
                    }
                )

    except Exception as e:
        logger.error(f"Ошибка при обработке webhook: {e}")

    return 'OK'


@app.route('/')
def index():
    return 'Бот работает!'


@app.route('/set_webhook')
def set_webhook_route():
    app_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    webhook_base_url = None

    if app_domain:
        if not app_domain.startswith(('http://', 'https://')):
            webhook_base_url = f"https://{app_domain}"
        else:
            webhook_base_url = app_domain
    else:
        static_url = os.environ.get('RAILWAY_STATIC_URL')
        if static_url:
            webhook_base_url = static_url
        else:
            webhook_base_url = os.environ.get('APP_URL', 'https://your-app-url.railway.app')

    if webhook_base_url.endswith('/'):
        webhook_base_url = webhook_base_url[:-1]

    webhook_url = f"{webhook_base_url}/{BOT_TOKEN}"

    logger.info(f"Пытаемся установить вебхук на: {webhook_url}")

    try:
        result = asyncio.run(set_webhook_async(webhook_url))
        return result
    except Exception as e:
        logger.error(f"Ошибка при настройке вебхука: {e}")
        alt_webhook_base_url = f"https://{os.environ.get('RAILWAY_SERVICE_NAME', 'videopirat')}.up.railway.app"
        alt_webhook_url = f"{alt_webhook_base_url}/{BOT_TOKEN}"
        logger.info(f"Пробуем альтернативный URL: {alt_webhook_url}")

        try:
            result = asyncio.run(set_webhook_async(alt_webhook_url))
            return result
        except Exception as e2:
            logger.error(f"Ошибка при настройке вебхука (альтернативный URL): {e2}")
            return f'Не удалось настроить webhook: Попробовали {webhook_url} и {alt_webhook_url}'


@app.route('/remove_webhook')
def remove_webhook():
    try:
        asyncio.run(bot.delete_webhook())
        return 'Webhook удален'
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
        return f'Ошибка при удалении webhook: {e}'


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))

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

        if webhook_base_url.endswith('/'):
            webhook_base_url = webhook_base_url[:-1]

        webhook_url = f"{webhook_base_url}/{BOT_TOKEN}"
        logger.info(f"Настраиваем вебхук на {webhook_url}")

        threading.Thread(
            target=lambda: asyncio.run(set_webhook_async(webhook_url)),
            daemon=True
        ).start()
    except Exception as e:
        logger.error(f"Ошибка при настройке вебхука при запуске: {e}")
        logger.info(
            "Продолжаем запуск сервера без настройки вебхука. Вы можете настроить вебхук вручную через /set_webhook")

    app.run(host='0.0.0.0', port=port)
