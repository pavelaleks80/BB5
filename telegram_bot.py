#"""
#telegram_bot.py
#
#Отправляет уведомления в Telegram через Bot API.
#"""
#
#import requests
#from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#==================================================================
#
#def send_telegram_message(message):
#    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#    payload = {
#        "chat_id": TELEGRAM_CHAT_ID,
#        "text": message,
#        "parse_mode": "Markdown"
#    }
#    try:
#        requests.post(url, json=payload)
#    except Exception as e:
#        print("Ошибка при отправке сообщения:", e)
#
#def send_long_message(message):
#    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#    payload = {
#        "chat_id": TELEGRAM_CHAT_ID,
#        "text": message,
#        "parse_mode": "Markdown"
#    }
#    try:
#        requests.post(url, json=payload)
#    except Exception as e:
#        print("Ошибка при отправке сообщения:", e)
#==================================================================

#=== Изменено 16.07.25 - Добавлено логирование ====================
"""
telegram_bot.py

Отправляет уведомления в Telegram через Bot API.
"""

import requests
import logging
import os
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBot")


def send_telegram_message(message):
    """
    Отправляет короткое сообщение в Telegram.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    chat_id = os.getenv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_notification": False
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Вызывает исключение для HTTP-ошибок
        logger.info(f"[+] Сообщение успешно отправлено: {message[:50]}...")  # Логируем начало сообщения
    except requests.exceptions.RequestException as e:
        error_msg = f"[X TELEGRAM] Ошибка при отправке сообщения: {e}"
        logger.error(error_msg, exc_info=True)
        print(error_msg)


def send_long_message(message):
    """
    Отправляет длинное сообщение по частям (если превышает лимит Telegram).
    """
    MAX_MESSAGE_LENGTH = 4096  # Максимальная длина сообщения в Telegram
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    chat_id = os.getenv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    for i in range(0, len(message), MAX_MESSAGE_LENGTH):
        part = message[i:i + MAX_MESSAGE_LENGTH]
        payload = {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"[+] Часть сообщения отправлена: {part[:50]}...")
        except requests.exceptions.RequestException as e:
            error_msg = f"[X TELEGRAM] Ошибка при отправке части сообщения: {e}"
            logger.error(error_msg, exc_info=True)
            print(error_msg)