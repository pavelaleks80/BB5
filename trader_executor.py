"""
trader_executor.py
Исполняет сделки на основе сигналов из БД.
Работает только с таблицами: quotes_{ticker}, signals_log, positions, trade_logs.
Не зависит от signals_processor.py.
"""

import pandas as pd
from tinkoff.invest import Client, OrderDirection, OrderType, AccountType
from tinkoff.invest.sandbox.client import SandboxClient
from config import TICKERS, TOKEN, DB_CONFIG, TELEGRAM_CHAT_ID, COMMISSION, SANDBOX_MODE, STARTING_DEPOSIT, MAX_OPERATION_AMOUNT, ACCOUNT_ID, MAX_SHARES_PER_TRADE
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
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

logging.info("=== Запуск торгового робота ===")

# === Константы ===
N = 2
STARTING_DEPOSIT = STARTING_DEPOSIT
MAX_OPERATION_AMOUNT = MAX_OPERATION_AMOUNT
EXCEL_FILE = "trade_history.xlsx"
CHART_FILE = "balance_chart.png"

# === Подключение к БД ===
def connect_db():
    """Подключение к базе данных"""
    return psycopg2.connect(**DB_CONFIG)

# === Получение FIGI по тикеру ===
def get_figi_by_ticker(ticker):
    """Получает FIGI инструмента по тикеру"""
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                instruments = client.instruments
        else:
            with Client(TOKEN) as client:
                instruments = client.instruments

        if ticker == 'SPY':
            r = instruments.etfs()
        else:
            r = instruments.shares()

        for instrument in r.instruments:
            if instrument.ticker == ticker:
                return instrument.figi
        return None
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при получении FIGI для {ticker}: {e}")
        return None

# === Получение последних N свечей из таблицы quotes_{ticker} ===
def get_last_n_days(ticker, n=2):
    """Получает последние n свечей из таблицы quotes_{ticker}"""
    table_name = f"quotes_{ticker.lower()}"
    query = f"""
        SELECT date, open, close, sma, lower_band
        FROM {table_name}
        ORDER BY date DESC
        LIMIT %s
    """
    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (n,))
                rows = cur.fetchall()
                if not rows:
                    return pd.DataFrame()
                return pd.DataFrame(rows, columns=['date', 'open', 'close', 'sma', 'lower_band'])
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при получении данных из {table_name}: {e}")
        return pd.DataFrame()

# === Выполнение ордера ===
def execute_order(figi, quantity, order_type):
    """Выполняет ордер через Tinkoff API"""
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                account_id = client.sandbox.get_sandbox_accounts().accounts[0].id
                client.sandbox.sandbox_pay_in(account_id=account_id, amount=Decimal(1_000_000))
        else:
            with Client(TOKEN) as client:
                account_id = ACCOUNT_ID

        direction = OrderDirection.ORDER_DIRECTION_BUY if order_type == "BUY" else OrderDirection.ORDER_DIRECTION_SELL

        if SANDBOX_MODE:
            response = client.sandbox.post_order(
                figi=figi,
                quantity=quantity,
                direction=direction,
                account_id=account_id,
                order_type=OrderType.ORDER_TYPE_MARKET,
                order_id=str(hash(figi))[:36]
            )
        else:
            response = client.orders.post_order(
                figi=figi,
                quantity=quantity,
                direction=direction,
                account_id=account_id,
                order_type=OrderType.ORDER_TYPE_MARKET,
                order_id=str(hash(figi))[:36]
            )
        return True
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при выполнении ордера {order_type} для {figi}: {e}")
        return False

# === Получение текущего баланса ===
def get_current_balance():
    """Получает текущий баланс счёта"""
    try:
        if SANDBOX_MODE:
            with SandboxClient(TOKEN) as client:
                accounts = client.sandbox.get_sandbox_accounts()
                if not accounts.accounts:
                    client.sandbox.open_sandbox_account()
                account_id = accounts.accounts[0].id
                positions = client.operations.get_operations(account_id=account_id).positions
        else:
            with Client(TOKEN) as client:
                accounts = client.users.get_accounts()
                account_id = ACCOUNT_ID
                positions = client.operations.get_operations(account_id=account_id).positions

        total_value = 0
        for pos in positions:
            total_value += pos.current_price.units + pos.current_price.nano / 1e9
        return total_value
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при получении баланса: {e}")
        return STARTING_DEPOSIT

# === Логирование сделки в Excel и БД ===
def log_trade(signal_type, ticker, price, quantity, amount, profit=None):
    """Логирует сделку в Excel и в БД"""
    balance = get_current_balance()
    timestamp = datetime.datetime.now()

    df_new = pd.DataFrame([{
        "timestamp": timestamp,
        "signal": signal_type,
        "ticker": ticker,
        "price": price,
        "quantity": quantity,
        "amount": amount,
        "profit": profit,
        "balance": balance
    }])

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

    # === Запись в БД (trade_logs) ===
    try:
        with connect_db() as conn:
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

# === Построение графика баланса ===
def generate_balance_chart():
    """Строит график изменения баланса"""
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

# === Сброс "сломанных" позиций ===
def reset_broken_positions():
    """Сбрасывает позиции, где in_market=True, но нет акций"""
    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE positions
                    SET in_market = FALSE, quantity = 0
                    WHERE in_market = TRUE AND quantity <= 0
                """)
                conn.commit()
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка при сбросе позиций: {e}")

# === Основной торговый цикл ===
def main_trading_loop():
    print("[ПЕСОЧНИЦА] Начинаем новый торговый цикл")
    logging.info("[ПЕСОЧНИЦА] Начинаем новый торговый цикл")

    balance = get_current_balance()
    print(f"[ПЕСОЧНИЦА] Текущий баланс:")
    print(f"[ПЕСОЧНИЦА] - Денег на счёте: {balance:.2f} руб.")
    print(f"[ПЕСОЧНИЦА] - Стоимость акций: 0.00 руб.")
    print(f"[ПЕСОЧНИЦА] - Итого: {balance:.2f} руб.")

    trade_date = datetime.datetime.now().date()

    for ticker in tqdm(TICKERS, desc="Обработка тикеров"):
        df = get_last_n_days(ticker, N)
        if df.empty or len(df) < 2:
            continue

        latest = df.iloc[0]
        last_candle_date = latest['date'].date()

        # === Получение сигналов из БД ===
        buy_signal = False
        dca_signal = False
        sell_signal = False

        try:
            with connect_db() as conn:
                with conn.cursor() as cur:
                    # Сигнал "КУПИ"
                    cur.execute("""
                        SELECT 1 FROM signals_log
                        WHERE ticker = %s AND signal_type = 'КУПИ'
                        AND signal_date >= %s
                        LIMIT 1
                    """, (ticker, last_candle_date))
                    buy_signal = cur.fetchone() is not None

                    # Сигнал "ДОКУПИ"
                    cur.execute("""
                        SELECT 1 FROM signals_log
                        WHERE ticker = %s AND signal_type = 'ДОКУПИ'
                        AND signal_date >= %s
                        LIMIT 1
                    """, (ticker, last_candle_date))
                    dca_signal = cur.fetchone() is not None

                    # Сигнал "ПРОДАЙ"
                    cur.execute("""
                        SELECT 1 FROM signals_log
                        WHERE ticker = %s AND signal_type = 'ПРОДАЙ'
                        AND signal_date >= %s
                        LIMIT 1
                    """, (ticker, last_candle_date))
                    sell_signal = cur.fetchone() is not None
        except Exception as e:
            print(f"[X ПЕСОЧНИЦА] Ошибка при проверке сигналов для {ticker}: {e}")
            continue

        # === Получение состояния позиции ===
        avg_pos = None
        in_market = False
        try:
            with connect_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT avg_price, in_market FROM positions WHERE ticker = %s", (ticker,))
                    res = cur.fetchone()
                    if res:
                        avg_pos, in_market = res
        except Exception as e:
            print(f"[X ПЕСОЧНИЦА] Ошибка при получении позиции для {ticker}: {e}")
            continue

        # === Сигнал КУПИТЬ ===
        if buy_signal and not avg_pos:
            print(f"[DEBUG] Обработка сигнала КУПИТЬ для тикера: {ticker}")
            logging.info(f"[DEBUG] Обработка сигнала КУПИТЬ для тикера: {ticker}")

            price = latest['open']
            max_qty = MAX_OPERATION_AMOUNT // price
            qty = min(max_qty, MAX_SHARES_PER_TRADE)
            amount = price * qty * (1 + COMMISSION)

            balance_details = {'money': balance}
            if balance_details['money'] > amount:
                figi = get_figi_by_ticker(ticker)
                if figi and execute_order(figi, int(qty), "BUY"):
                    try:
                        with connect_db() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO positions (ticker, avg_price, quantity, in_market, created_at, updated_at)
                                    VALUES (%s, %s, %s, TRUE, NOW(), NOW())
                                    ON CONFLICT (ticker) DO UPDATE SET
                                        avg_price = EXCLUDED.avg_price,
                                        quantity = EXCLUDED.quantity,
                                        in_market = EXCLUDED.in_market,
                                        updated_at = NOW()
                                """, (ticker, price, qty))
                                conn.commit()
                        log_trade("BUY", ticker, price, qty, amount)
                        send_telegram_message(f"*[ПЕСОЧНИЦА] [+] Купили* {ticker}, {qty} шт. по {price:.2f} руб.\nДата: {trade_date}")
                    except Exception as e:
                        print(f"[X ПЕСОЧНИЦА] Ошибка при обновлении позиции {ticker}: {e}")
            time.sleep(2)

        # === Сигнал ДОКУПИТЬ ===
        elif dca_signal and avg_pos and in_market:
            print(f"[DEBUG] Обработка сигнала ДОКУПИТЬ для тикера: {ticker}")
            logging.info(f"[DEBUG] Обработка сигнала ДОКУПИТЬ для тикера: {ticker}")

            price = latest['open']
            new_quantity = MAX_SHARES_PER_TRADE
            amount = price * new_quantity * (1 + COMMISSION)

            balance_details = {'money': balance}
            if balance_details['money'] > amount:
                figi = get_figi_by_ticker(ticker)
                if figi and execute_order(figi, int(new_quantity), "BUY"):
                    try:
                        new_avg_price = (avg_pos * (1 - COMMISSION) + price * (1 + COMMISSION)) / 2
                        new_total_qty = avg_pos + new_quantity
                        with connect_db() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE positions
                                    SET avg_price = %s, quantity = %s, updated_at = NOW()
                                    WHERE ticker = %s
                                """, (new_avg_price, new_total_qty, ticker))
                                conn.commit()
                        log_trade("DCA", ticker, price, new_quantity, amount)
                        send_telegram_message(f"*[ПЕСОЧНИЦА] [~] Докупили* {ticker}, {new_quantity} шт. по {price:.2f} руб.\nДата: {trade_date}")
                    except Exception as e:
                        print(f"[X ПЕСОЧНИЦА] Ошибка при обновлении позиции {ticker}: {e}")
            time.sleep(2)

        # === Сигнал ПРОДАТЬ ===
        elif sell_signal and avg_pos and in_market:
            print(f"[DEBUG] Обработка сигнала ПРОДАТЬ для тикера: {ticker}")
            logging.info(f"[DEBUG] Обработка сигнала ПРОДАТЬ для тикера: {ticker}")

            price = latest['open']
            qty = avg_pos
            amount = price * qty * (1 - COMMISSION)
            profit = (price - avg_pos) * qty * (1 - COMMISSION)

            figi = get_figi_by_ticker(ticker)
            if figi and execute_order(figi, int(qty), "SELL"):
                try:
                    log_trade("SELL", ticker, price, qty, amount, profit)
                    send_telegram_message(f"*[ПЕСОЧНИЦА] [-] Продали* {ticker}, {qty} шт. по {price:.2f} руб. Прибыль: {profit:.2f} руб.\nДата: {trade_date}")
                    with connect_db() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE positions
                                SET avg_price = NULL, quantity = 0, in_market = FALSE, updated_at = NOW()
                                WHERE ticker = %s
                            """, (ticker,))
                            conn.commit()
                except Exception as e:
                    print(f"[X TELEGRAM] Ошибка при отправке сообщения о продаже {ticker}: {e}")
            time.sleep(2)

    # === Финальная очистка ===
    reset_broken_positions()
    print("[OK ПЕСОЧНИЦА] Цикл торговли завершён")
    send_telegram_message("*[ПЕСОЧНИЦА] Цикл торговли завершён*")

    # === Отправка сообщения, если не было сделок ===
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM trade_logs
                WHERE DATE(timestamp) = %s
            """, (trade_date,))
            trade_count = cur.fetchone()[0]

    if trade_count == 0:
        message = f"*[ПЕСОЧНИЦА] [!] Нет сделок* за сегодня.\nДата: {trade_date}"
        send_telegram_message(message)
        print(f"[INFO ПЕСОЧНИЦА] Отправлено сообщение: {message}")
        logging.info(f"[INFO ПЕСОЧНИЦА] Отправлено сообщение: {message}")

# === Запуск ===
if __name__ == "__main__":
    print("[START ПЕСОЧНИЦА] Запуск торгового робота")
    # === Отправляем сообщение в Telegram о запуске ===
    start_msg = "*[ПЕСОЧНИЦА] Запускаем торгового робота*"
    send_telegram_message(start_msg)
    print(start_msg)
    # === Конец Отправляем сообщение в Telegram о запуске ===
    try:
        main_trading_loop()
        generate_balance_chart()
        print("[ПЕСОЧНИЦА] Отчёт сохранён")
    except Exception as e:
        print(f"[X ПЕСОЧНИЦА] Ошибка: {e}")
        logging.error(f"[X ПЕСОЧНИЦА] Ошибка: {e}", exc_info=True)