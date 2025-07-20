"""
trader_executor.py

Исполняет сделки на основе сигналов.
Управляет капиталом, рассчитывает лотность,
сохраняет статистику торговли в Excel и строит график изменения депозита.
"""

import pandas as pd
from tinkoff.invest import Client, OrderDirection, OrderType, AccountType
from tinkoff.invest.sandbox.client import SandboxClient
from config import TICKERS, TOKEN, DB_CONFIG, TELEGRAM_CHAT_ID, COMMISSION, SANDBOX_MODE, STARTING_DEPOSIT, MAX_OPERATION_AMOUNT, ACCOUNT_ID, MAX_SHARES_PER_TRADE
#from signals_processor import update_position, log_signal, was_buy_signal_received, get_last_n_days, connect
from signals_processor import update_position, log_signal, get_last_n_days, connect
from telegram_bot import send_telegram_message
import psycopg2
import matplotlib.pyplot as plt
import os
import time
import datetime
from tqdm import tqdm
import sys
import logging
from decimal import Decimal

# === Настройка логирования ===
LOG_FILE = "trading_log.txt"

# Создаём форматтер: время - уровень - сообщение
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Конфигурируем логгер
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Логгирование в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Логгирование в файл
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Запишем стартовый лог
logging.info("=== Запуск торгового робота ===")

N=2

STARTING_DEPOSIT = STARTING_DEPOSIT  # Начальный депозит
MAX_OPERATION_AMOUNT = MAX_OPERATION_AMOUNT  # Максимум на одну операцию
EXCEL_FILE = "trade_history.xlsx"
CHART_FILE = "balance_chart.png"

ACCOUNT_ID = "92b38166-c110-4801-b7b9-af65b8b3bd28"  # Твой фиксированный ID

def get_current_balance():
    """Получает текущий общий баланс счёта: деньги + стоимость акций."""
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                # Получаем список активных счетов
                accounts = client.users.get_accounts().accounts
                if not accounts:
                    raise Exception("Нет активных счетов")
                account_id = accounts[0].id

                # Получаем позиции (денежные средства и акции)
                positions = client.operations.get_positions(account_id=account_id)

                # Получаем текущие цены по акциям
                figis = [sec.instrument_uid for sec in positions.securities]
                if figis:
                    last_prices = client.market_data.get_last_prices(figi=figis)
                    price_dict = {price.figi: price.price for price in last_prices.last_prices}

                    # Рассчитываем стоимость акций
                    shares_value = 0.0
                    for sec in positions.securities:
                        figi = sec.instrument_uid
                        if figi in price_dict:
                            price = price_dict[figi].units + price_dict[figi].nano / 1e9
                            shares_value += float(sec.balance * price)
                        else:
                            print(f"[!] Не удалось получить цену для {figi}")
                else:
                    shares_value = 0.0

                money_rub = sum(
                    money.units + money.nano / 1e9
                    for money in positions.money
                    if money.currency == "rub"
                )

                return money_rub + shares_value

        else:
            with Client(TOKEN) as client:
                # Аналогично для реального режима
                accounts = client.users.get_accounts().accounts
                if not accounts:
                    raise Exception("Нет активных счетов на реальном аккаунте")
                account_id = accounts[0].id

                positions = client.operations.get_positions(account_id=account_id)

                figis = [sec.instrument_uid for sec in positions.securities]
                if figis:
                    last_prices = client.market_data.get_last_prices(figi=figis)
                    price_dict = {price.figi: price.price for price in last_prices.last_prices}

                    shares_value = 0.0
                    for sec in positions.securities:
                        figi = sec.instrument_uid
                        if figi in price_dict:
                            price = price_dict[figi].units + price_dict[figi].nano / 1e9
                            shares_value += float(sec.balance * price)
                        else:
                            print(f"[!] Не удалось получить цену для {figi}")
                else:
                    shares_value = 0.0

                money_rub = sum(
                    money.units + money.nano / 1e9
                    for money in positions.money
                    if money.currency == "rub"
                )

                return money_rub + shares_value

    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка получения баланса: {e}")
        return STARTING_DEPOSIT

def get_full_balance_details():
    """
    Возвращает подробную информацию о балансе:
    - Денежные средства,
    - Стоимость акций,
    - Общий баланс.
    """
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                positions = client.operations.get_positions(account_id=ACCOUNT_ID)
                money_rub = sum(
                    float(money.units + money.nano / 1e9)
                    for money in positions.money
                    if money.currency == "rub"
                )
                figis = [sec.instrument_uid for sec in positions.securities]
                shares_value = 0.0
                if figis:
                    last_prices = client.market_data.get_last_prices(figi=figis)
                    price_dict = {price.figi: price.price for price in last_prices.last_prices}
                    for sec in positions.securities:
                        figi = sec.instrument_uid
                        if figi in price_dict:
                            price = price_dict[figi].units + price_dict[figi].nano / 1e9
                            shares_value += float(sec.balance * price)
                        else:
                            print(f"[!] Не удалось получить цену для {figi}")
                return {
                    "money": money_rub,
                    "shares": shares_value,
                    "total": money_rub + shares_value
                }
        else:
            with Client(TOKEN) as client:
                positions = client.operations.get_positions(account_id=ACCOUNT_ID)
                money_rub = sum(
                    float(money.units + money.nano / 1e9)
                    for money in positions.money
                    if money.currency == "rub"
                )
                figis = [sec.instrument_uid for sec in positions.securities]
                shares_value = 0.0
                if figis:
                    last_prices = client.market_data.get_last_prices(figi=figis)
                    price_dict = {price.figi: price.price for price in last_prices.last_prices}
                    for sec in positions.securities:
                        figi = sec.instrument_uid
                        if figi in price_dict:
                            price = price_dict[figi].units + price_dict[figi].nano / 1e9
                            shares_value += float(sec.balance * price)
                        else:
                            print(f"[!] Не удалось получить цену для {figi}")
                return {
                    "money": money_rub,
                    "shares": shares_value,
                    "total": money_rub + shares_value
                }
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при получении детального баланса: {e}")
        return {
            "money": 0.0,
            "shares": 0.0,
            "total": STARTING_DEPOSIT
        }
 
def execute_order(figi, quantity, direction):
    """
    Выполняет рыночный ордер.
    """
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                accounts = client.users.get_accounts().accounts
                account_id = ACCOUNT_ID if ACCOUNT_ID else accounts[0].id

                if direction == "BUY":
                    client.orders.post_order(  # Исправлено на новый метод
                        figi=figi,
                        quantity=quantity,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        direction=OrderDirection.ORDER_DIRECTION_BUY
                    )
                    print(f"[+] Куплено {quantity} шт. {figi}")
                elif direction == "SELL":
#                    client.sandbox.post_sandbox_order(
                    client.orders.post_order(
                        figi=figi,
                        quantity=quantity,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        direction=OrderDirection.ORDER_DIRECTION_SELL
                    )
                    print(f"[- ПЕСОЧНИЦА] Продано {quantity} шт. {figi}")
        else:
            with Client(TOKEN) as client:
                accounts = client.users.get_accounts().accounts
                account_id = ACCOUNT_ID if ACCOUNT_ID else accounts[0].id

                if direction == "BUY":
                    client.orders.post_order(
                        figi=figi,
                        quantity=quantity,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        direction=OrderDirection.ORDER_DIRECTION_BUY
                    )
                    print(f"[+ РЕАЛ] Куплено {quantity} шт. {figi}")

                elif direction == "SELL":
                    client.orders.post_order(
                        figi=figi,
                        quantity=quantity,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        direction=OrderDirection.ORDER_DIRECTION_SELL
                    )
                    print(f"[- РЕАЛ] Продано {quantity} шт. {figi}")
        return True
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка выполнения ордера: {e}")
        return False

def get_figi_by_ticker(ticker):
    """
    Получает FIGI по тикеру.
    """
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                instruments = client.instruments.shares().instruments
                for instrument in instruments:
                    if instrument.ticker == ticker:
                        return instrument.figi
                return None
        else:
            with Client(TOKEN) as client:
                instruments = client.instruments.shares().instruments
                for instrument in instruments:
                    if instrument.ticker == ticker:
                        return instrument.figi
                return None
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при получении FIGI для {ticker}: {e}")
        return None

#=========================================================================
#def log_trade(signal_type, ticker, price, quantity, amount, profit=None):
#    """
#    Логирует сделки в DataFrame и сохраняет в Excel.
#    Создаёт файл, если его нет.
#    """
#    balance = get_current_balance()
#    timestamp = datetime.datetime.now()
#    df_new = pd.DataFrame([{
#        "timestamp": datetime.datetime.now(),
#        "signal": signal_type,
#        "ticker": ticker,
#        "price": price,
#        "quantity": quantity,
#        "amount": amount,
#        "profit": profit,
#        "balance": balance
#    }])
#    
#    try:
#        if not os.path.exists(EXCEL_FILE):
#            df_new.to_excel(EXCEL_FILE, index=False, sheet_name="Trades")
#            print(f"[REPORT ПЕСОЧНИЦА] Создан новый файл отчёта: {EXCEL_FILE}")
#        else:
#            with pd.ExcelWriter(EXCEL_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
#                df_new.to_excel(writer, sheet_name="Trades", header=False, startrow=writer.sheets["Trades"].max_row, index=False)
#            print(f"[OK ПЕСОЧНИЦА] Записана сделка: {ticker}, {signal_type}, {price:.2f} руб.")
#    except Exception as e:
#        print(f"[X ПЕСОЧНИЦА] Ошибка записи в Excel: {e}")
#        df_existing = pd.read_excel(EXCEL_FILE)
#        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
#        df_combined.to_excel(EXCEL_FILE, index=False)
#        print(f"[ПЕСОЧНИЦА] Восстановлен файл отчёта после ошибки")
#=========================================================================
#=== Изменено 20.07.25 ===================================================        
def log_trade(signal_type, ticker, price, quantity, amount, profit=None):
    """
    Логирует сделки в DataFrame и сохраняет в Excel и БД.
    """
    try:
        balance = get_current_balance()
        timestamp = datetime.datetime.now()
    except Exception as e:
        balance = 0.0
        logging.warning(f"[!] Не удалось получить баланс для логирования сделки: {e}")

    df_new = pd.DataFrame([{
        "timestamp": datetime.datetime.now(),
        "signal": signal_type,
        "ticker": ticker,
        "price": price,
        "quantity": quantity,
        "amount": amount,
        "profit": profit,
        "balance": balance
    }])

    # === Логирование в Excel ===
    try:
        if not os.path.exists(EXCEL_FILE):
            df_new.to_excel(EXCEL_FILE, index=False, sheet_name="Trades")
            print(f"[REPORT ПЕСОЧНИЦА] Создан новый файл отчёта: {EXCEL_FILE}")
        else:
            with pd.ExcelWriter(EXCEL_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                df_new.to_excel(writer, sheet_name="Trades", header=False, startrow=writer.sheets["Trades"].max_row, index=False)
            print(f"[OK ПЕСОЧНИЦА] Записана сделка: {ticker}, {signal_type}, {price:.2f} руб.")
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка записи в Excel: {e}")
        logging.error(f"[X ПЕСОЧНИЦА] Ошибка записи в Excel: {e}")

    # === Логирование в БД ===
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trade_logs (ticker, trade_type, price, quantity, amount, profit, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ticker, signal_type, price, quantity, amount, profit, datetime.datetime.now()))
                conn.commit()
        print(f"[OK ПЕСОЧНИЦА] Записана сделка в БД: {ticker}, {signal_type}, {price:.2f} руб.")
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка записи в БД: {e}")
        logging.error(f"[X ПЕСОЧНИЦА] Ошибка записи в БД: {e}")
        
        # === Запись в БД (trade_logs) ===
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trade_logs (ticker, trade_type, price, quantity, amount, profit, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ticker, signal_type, price, quantity, amount, profit, timestamp))
                conn.commit()
        print(f"[OK ПЕСОЧНИЦА] Записана сделка в БД: {ticker}, {signal_type}, {price:.2f} руб.")
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка записи в БД: {e}")
        logging.error(f"[X ПЕСОЧНИЦА] Ошибка записи в БД: {e}")
#=== КОНЕЦ Изменено 20.07.25 ===================================================        

def generate_balance_chart():
    """Строит график изменения баланса."""
    if not os.path.exists(EXCEL_FILE):
        print("[X ПЕСОЧНИЦА] Файл trade_history.xlsx не найден")
        return
    try:
        df = pd.read_excel(EXCEL_FILE)
        if 'balance' not in df.columns:
            print("[X ПЕСОЧНИЦА] Нет данных о балансе для построения графика")
            return
        plt.figure(figsize=(12, 6))
        plt.plot(df['timestamp'], df['balance'], label="Баланс", marker='o')
        plt.title("Динамика баланса")
        plt.xlabel("Дата и время")
        plt.ylabel("Рубли")
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(CHART_FILE)
        plt.close()
        print("[ПЕСОЧНИЦА] График баланса успешно создан")
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при построении графика: {e}")

def reset_broken_positions():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE positions
                SET avg_price = NULL, quantity = 0, in_market = FALSE
                WHERE avg_price IS NOT NULL AND quantity = 0
            """)
            conn.commit()

def main_trading_loop():
    print("[START ПЕСОЧНИЦА] Запуск торгового робота")
    logging.info("=== Запуск торгового робота ===")
    # === Сброс повреждённых позиций ===
    reset_broken_positions()
    print("[ПЕСОЧНИЦА] Начинаем новый торговый цикл")
#    send_telegram_message("[ПЕСОЧНИЦА] Начинаем новый торговый цикл")
    logging.info("[ПЕСОЧНИЦА] Начинаем новый торговый цикл")
    balance_details = get_full_balance_details()
    print(f"[ПЕСОЧНИЦА] Текущий баланс:")
    logging.info(f"[ПЕСОЧНИЦА] Текущий баланс:")
    print(f"[ПЕСОЧНИЦА] - Денег на счёте: {balance_details['money']:.2f} руб.")
    logging.info(f"[ПЕСОЧНИЦА] - Денег на счёте: {balance_details['money']:.2f} руб.")
    print(f"[ПЕСОЧНИЦА] - Стоимость акций: {balance_details['shares']:.2f} руб.")
    logging.info(f"[ПЕСОЧНИЦА] - Стоимость акций: {balance_details['shares']:.2f} руб.")
    print(f"[ПЕСОЧНИЦА] - Итого: {balance_details['total']:.2f} руб.")
    logging.info(f"[ПЕСОЧНИЦА] - Итого: {balance_details['total']:.2f} руб.")

    for ticker in tqdm(TICKERS, desc="Обработка тикеров"):
        df = get_last_n_days(ticker)
        if df.empty or len(df) < 2:
            continue

        latest = df.iloc[-1]  # Последняя свеча — самая новая
        last_candle_date = latest['date'].date()
        trade_date = latest['date'].date()

        # Проверяем, был ли сигнал "КУПИ" с момента последней свечи
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM signals_log
                    WHERE ticker = %s AND signal_type = 'КУПИ'
                    AND signal_date >= %s
                    LIMIT 1
                """, (ticker, last_candle_date))
                buy_signal = cur.fetchone() is not None

        # Получаем среднюю цену из позиции
        avg_pos = None
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT avg_price, in_market FROM positions WHERE ticker = %s", (ticker,))
                res = cur.fetchone()
                if res:
                    avg_pos, in_market = res
                else:
                    avg_pos, in_market = None, False

#=== Изменено 19.06.25 ===
        # === Сигнал КУПИТЬ ===
        if buy_signal and not avg_pos:
            print(f"[DEBUG] Обработка сигнала КУПИТЬ для тикера: {ticker}")
            logging.info(f"[DEBUG] Обработка сигнала КУПИТЬ для тикера: {ticker}")
#===========================================
#            price = latest['open']
#           qty = min(MAX_OPERATION_AMOUNT // price, MAX_SHARES_PER_TRADE)
#            amount = price * qty * (1 + COMMISSION)
#            balance = get_current_balance()
#            print(f"[DEBUG] Текущий баланс: {balance:.2f} руб., Требуется: {amount:.2f} руб.")
#            logging.info(f"[DEBUG] Текущий баланс: {balance:.2f} руб., Требуется: {amount:.2f} руб.")
#            if balance > amount:
#===========================================
            price = latest['open']
            qty = min(MAX_OPERATION_AMOUNT // price, MAX_SHARES_PER_TRADE)
            amount = price * qty * (1 + COMMISSION)
            balance_details = get_full_balance_details()
            print(f"[DEBUG] Денежные средства: {balance_details['money']:.2f} руб., Требуется: {amount:.2f} руб.")
            logging.info(f"[DEBUG] Денежные средства: {balance_details['money']:.2f} руб., Требуется: {amount:.2f} руб.")
            if balance_details['money'] > amount:
                figi = get_figi_by_ticker(ticker)
                if figi and execute_order(figi, int(qty), "BUY"):
                    update_position(ticker, price)
                    log_trade("BUY", ticker, price, qty, amount)
#                    send_telegram_message(
#                        f" *[ПЕСОЧНИЦА] [+] Купили* {ticker}, {qty} шт. по {price:.2f} руб.", f"Дата: {trade_date}")
                    send_telegram_message(
                        f"*[ПЕСОЧНИЦА] [+] Купили* {ticker}, {qty} шт. по {price:.2f} руб.\nДата: {trade_date}"
)
                    time.sleep(2)
            else:
#                print(f"[X ПЕСОЧНИЦА] Недостаточно средств для покупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance:.2f} руб.")
                print(f"[X ПЕСОЧНИЦА] Недостаточно средств для покупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance_details['money']:.2f} руб.")
#                logging.warning(f"[X ПЕСОЧНИЦА] Недостаточно средств для покупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance:.2f} руб.")
                logging.warning(f"[X ПЕСОЧНИЦА] Недостаточно средств для покупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance_details['money']:.2f} руб.")
#=== КОНЕЦ Изменено 19.06.25 ===
        
#=== Изменено 19.06.25 ===                    
        # === Сигнал ДОКУПИТЬ ===
#        elif avg_pos and latest['open'] < avg_pos:
        elif avg_pos is not None and in_market and latest['open'] < avg_pos:
            print(f"[DEBUG] Обработка сигнала ДОКУПИТЬ для тикера: {ticker}")
            logging.info(f"[DEBUG] Обработка сигнала ДОКУПИТЬ для тикера: {ticker}")
#================================
#            price = latest['open']
#            qty = min(MAX_OPERATION_AMOUNT // price, MAX_SHARES_PER_TRADE)
#            amount = price * qty * (1 + COMMISSION)
#            balance = get_current_balance()
#            print(f"[DEBUG] Текущий баланс: {balance:.2f} руб., Требуется: {amount:.2f} руб.")
#            logging.info(f"[DEBUG] Текущий баланс: {balance:.2f} руб., Требуется: {amount:.2f} руб.")
#            
#            if balance > amount:
#=================================
            price = latest['open']
            qty = min(MAX_OPERATION_AMOUNT // price, MAX_SHARES_PER_TRADE)
            amount = price * qty * (1 + COMMISSION)
            balance_details = get_full_balance_details()
            print(f"[DEBUG] Денежные средства: {balance_details['money']:.2f} руб., Требуется: {amount:.2f} руб.")
            logging.info(f"[DEBUG] Денежные средства: {balance_details['money']:.2f} руб., Требуется: {amount:.2f} руб.")
            if balance_details['money'] > amount:

                figi = get_figi_by_ticker(ticker)
                if figi and execute_order(figi, int(qty), "BUY"):
                    update_position(ticker, price)
                    log_trade("DCA", ticker, price, qty, amount)
                    send_telegram_message(
#                        f" *[ПЕСОЧНИЦА] [~] Докупили* {ticker}, {qty} шт. по {price:.2f} руб.", f"Дата: {trade_date}")
                        f"*[ПЕСОЧНИЦА] [~] Докупили* {ticker}, {qty} шт. по {price:.2f} руб.\nДата: {trade_date}")
                    time.sleep(2)
            else:
#                print(f"[X ПЕСОЧНИЦА] Недостаточно средств для докупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance:.2f} руб.")
                print(f"[X ПЕСОЧНИЦА] Недостаточно средств для докупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance_details['money']:.2f} руб.")
#                logging.warning(f"[X ПЕСОЧНИЦА] Недостаточно средств для докупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance:.2f} руб.")
                logging.warning(f"[X ПЕСОЧНИЦА] Недостаточно средств для докупки тикера {ticker}. Требуется: {amount:.2f} руб., Доступно: {balance_details['money']:.2f} руб.")        
#=== КОНЕЦ Изменено 19.06.25 ===

        # === Сигнал ПРОДАТЬ ===
        elif avg_pos and latest['close'] > latest['sma']:
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT avg_price, quantity, in_market FROM positions WHERE ticker = %s", (ticker,))
                    res = cur.fetchone()
                    if res and res[2]:  # Если в рынке
                        price = latest['open']
                        qty = res[1]
                        amount = price * qty * (1 - COMMISSION)
                        profit = (price - res[0]) * qty * (1 - COMMISSION)
                        figi = get_figi_by_ticker(ticker)

                        if figi and execute_order(figi, int(qty), "SELL"):
                            log_trade("SELL", ticker, price, qty, amount, profit)
                            
                            # Расчёт доходности в процентах
                            if avg_pos > 0:
                                profit_percent = ((price - avg_pos) / avg_pos) * 100
                            else:
                                profit_percent = 0.0
                                # Формирование сообщения
                            message = (
                                f"*[ПЕСОЧНИЦА] [-] Продали* {ticker}, {qty} шт. по {price:.2f} руб.\n"
                                f"Прибыль: {profit:.2f} руб. ({profit_percent:.2f}%)\n"
                                f"Дата: {trade_date}"
                            )
                            send_telegram_message(message)

                            try:
                                send_telegram_message(
                                    f"*[ПЕСОЧНИЦА] [-] Продали* {ticker}, {qty} шт. по {price:.2f} руб. Прибыль: {profit:.2f} руб.\nДата: {trade_date}"
                                    )
                            except Exception as e:
                                logging.error(f"[X TELEGRAM] Ошибка при отправке сообщения о продаже {ticker}: {e}")
                                print(f"[X TELEGRAM] Ошибка при отправке сообщения о продаже {ticker}: {e}")
                            
                            # === Деактивация сигналов ===
                            cur.execute("""
                                UPDATE positions 
                                SET avg_price = NULL, quantity = 0, in_market = FALSE 
                                WHERE ticker = %s
                            """, (ticker,))
                            conn.commit()
                            time.sleep(2)
    # === Финальная очистка ===
    reset_broken_positions()
    print("[OK ПЕСОЧНИЦА] Цикл торговли завершён")
    send_telegram_message("*[ПЕСОЧНИЦА] Цикл торговли завершён*")

if __name__ == "__main__":
    print("[START ПЕСОЧНИЦА] Запуск торгового робота")
    try:
        main_trading_loop()
        generate_balance_chart()
        print("[ПЕСОЧНИЦА] Отчёт сохранён")
        logging.error("[ПЕСОЧНИЦА] Отчёт сохранён")
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка: {e}")
        logging.error(f"[X ПЕСОЧНИЦА] Ошибка: {e}", exc_info=True)