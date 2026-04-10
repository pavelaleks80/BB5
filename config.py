"""
config.py

Хранит все параметры системы: токены, тикеры, настройки БД.
Токены и чувствительные данные загружаются из переменных окружения (.env файл).
"""

import os
from decimal import Decimal
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Режим песочницы Tinkoff Invest API
SANDBOX_MODE = True  # Установите False для реального счёта

# Токен для доступа к Tinkoff Invest API
# Загружается из переменной окружения TINKOFF_TOKEN
TOKEN = os.getenv('TINKOFF_TOKEN', '')
if not TOKEN:
    raise ValueError("TINKOFF_TOKEN не найден в переменных окружения. Создайте файл .env")

# Токен для Telegram API | bot: @bollbandbot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
# ID канала в Telegram | CHAT https://t.me/bollingerbandbot1 | @bollingerbandbot1
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("⚠️  Предупреждение: TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не настроены")

TICKERS = [
    'SBER', 'SBERP', 'ROSN', 'LKOH', 'NVTK', 'GAZP', 'SIBN', 'PLZL', 'GMKN', 'YDEX', 
    'TATN', 'TATNP', 'SNGS', 'SNGSP', 'VTBR', 'X5', 'TRNFP', 'T', 'CHMF', 'PHOR', 
    'NLMK', 'AKRN', 'UNAC', 'MTSS', 'RUAL', 'MOEX', 'MGNT', 'SVCB', 'PIKK', 'MAGN',
    'VSMO', 'ALRS', 'IRAO', 'BANE', 'BANEP', 'IRKT', 'AFLT', 'ENPG', 'CBOM', 'HYDR',
    'RTKM', 'FLOT', 'NMTP', 'FESH', 'BSPB', 'LENT', 'HEAD', 'RASP', 'NKNC', 'GCHE', 
    'KZOS', 'AFKS', 'UGLD', 'FEES', 'LSNG', 'FIXP', 'UWGN', 'TRMK', 'RAGR', 'UPRO', 
    'MGTSP', 'UDMN', 'MSNG', 'PRMD', 'KAZT', 'ASTR', 'POSI', 'LSRG', 'APTK', 'MDMG', 
    'LEAS', 'KMAZ', 'SMLT', 'MSRS', 'RENI']

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'pg4'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
}

# Строка подключения (с паролем, если указан)
if DB_CONFIG['password']:
    DATABASE_URI = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
else:
    DATABASE_URI = f"postgresql://{DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

N_WEEKS = 120 # Число недель тестирования (для недельного таймфрейма)

# Параметры для Bollinger Bands (на недельном таймфрейме)
BOLLINGER_CONFIG = {
    'window': 20,      # Период для SMA (20 недель)
    'num_std': 2       # Количество стандартных отклонений для полос
}

# Лимиты запросов к API
API_LIMITS = {
    'candles_per_request': 365,  # Недель данных за один запрос (увеличено для недельного ТФ)
    'delay_between_requests': 1   # Задержка (секунды) между запросами
}

STARTING_DEPOSIT = 300_000  # Начальный депозит
MAX_OPERATION_AMOUNT = 5000  # Максимум денег на одну операцию

# Комиссия за вход 0,3% и за выход 0,3%
#COMMISSION = 0.003  # 0.3% комиссии за операцию
COMMISSION = Decimal('0.003')  # теперь это Decimal

ACCOUNT_ID = "92b38166-c110-4801-b7b9-af65b8b3bd28"  # Твой фиксированный ID

# Максимум акций на одну сделку
MAX_SHARES_PER_TRADE = 10

