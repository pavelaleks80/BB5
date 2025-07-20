"""
config.py

Хранит все параметры системы: токены, тикеры, настройки БД.
"""

from decimal import Decimal

# Режим песочницы Tinkoff Invest API
SANDBOX_MODE = True  # Установите False для реального счёта

# Токен для доступа к Tinkoff Invest API
#TOKEN = '' # Боевой
#TOKEN = 't.dEx9c4Yej8AJGAxaKZOUAOq9UQWxJvzKqNiaDx7xJGFA6FgV6i1YABSUuB80bEsmheTWiPPKevR7Ix9dNS-maw' # Песочница
TOKEN = 't.r75yhXqlYNDre3i1FVpWS_E4LEdAF1pRjmf7lGCMgJUY-3g0dVatxM4lhk94eMqnM9hxUVOcdEHfob5jumRfZA' # Песочница



# Токен для Telegram API | bot: @bollbandbot
TELEGRAM_BOT_TOKEN = '7380650846:AAGdPGshlMvV96RHeIYiWD6Dw12TX5bt7Ys'
# ID канала в Telegram | CHAT https://t.me/bollingerbandbot1 | @bollingerbandbot1
TELEGRAM_CHAT_ID = -1001900882369

TICKERS = [
#    'SBER', 'SBERP', 'NVTK', 'LKOH', 'GAZP', 'SIBN', 'GMKN', 'TATN', 'TATNP', 
#    'SNGS', 'SNGSP', 'PLZL', 'CHMF', 'YDEX', 'NLMK', 'PHOR', 'IRKT', 'MGNT', 
#    'AKRN', 'MAGN', 'MTSS', 'PIKK', 'RUAL', 'ALRS', 'T', 'UNAC', 'BANE', 
#    'BANEP', 'VSMO', 'ROSN', 'TRNFP', 'VTBR'
    'SBER', 'SBERP', 'ROSN', 'LKOH', 'NVTK', 'GAZP', 'SIBN', 'PLZL', 'GMKN', 'YDEX', 
    'TATN', 'TATNP', 'SNGS', 'SNGSP', 'VTBR', 'X5', 'TRNFP', 'T', 'CHMF', 'PHOR', 
    'NLMK', 'AKRN', 'UNAC', 'MTSS', 'RUAL', 'MOEX', 'MGNT', 'SVCB', 'PIKK', 'MAGN',
    'VSMO', 'ALRS', 'IRAO', 'BANE', 'BANEP', 'IRKT', 'AFLT', 'ENPG', 'CBOM', 'HYDR',
    'RTKM', 'FLOT', 'NMTP', 'FESH', 'BSPB', 'LENT', 'HEAD', 'RASP', 'NKNC', 'GCHE', 
    'KZOS', 'AFKS', 'UGLD', 'FEES', 'LSNG', 'FIXP', 'UWGN', 'TRMK', 'RAGR', 'UPRO', 
    'MGTSP', 'UDMN', 'MSNG', 'PRMD', 'KAZT', 'ASTR', 'POSI', 'LSRG', 'APTK', 'MDMG', 
    'LEAS', 'KMAZ', 'SMLT', 'MSRS', 'RENI']

DB_CONFIG = {
    'dbname': 'pg4',
    'user': 'postgres',
#    'password': 'your_password',
    'host': 'localhost',
    'port': 5432,
}

# Строка подключения
DATABASE_URI = f"postgresql://{DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

N_DAYS = 120 # Число дней тестирования

# Параметры для Bollinger Bands
BOLLINGER_CONFIG = {
    'window': 20,      # Период для SMA
    'num_std': 2       # Количество стандартных отклонений для полос
}

# Лимиты запросов к API
API_LIMITS = {
    'candles_per_request': 30,  # Дней данных за один запрос
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
