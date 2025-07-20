"""
seller.py — скрипт для закрытия всех открытых позиций.
Отправляет отчет в Telegram по каждой сделке.
"""

import datetime
import logging
from decimal import Decimal

from tinkoff.invest import Client, OrderDirection, OrderType
from tinkoff.invest.sandbox.client import SandboxClient
from config import TOKEN, DB_CONFIG, TELEGRAM_CHAT_ID, COMMISSION, SANDBOX_MODE
from telegram_bot import send_telegram_message
import psycopg2


# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def connect_db():
    """Подключение к базе данных."""
    return psycopg2.connect(**DB_CONFIG)


def get_positions():
    """Получаем список всех открытых позиций."""
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ticker, avg_price, quantity, created_at
                FROM positions
                WHERE in_market = TRUE AND quantity > 0
            """)
            return cur.fetchall()


def get_figi_by_ticker(ticker):
    """Получаем FIGI по тикеру."""
    with Client(TOKEN) as client:
        instruments = client.instruments
        if ticker == 'SPY':
            r = instruments.etfs()
        else:
            r = instruments.shares()

        for item in r.instruments:
            if item.ticker == ticker:
                return item.figi
    return None


def sell_position(figi, quantity, price):
    """Выполняем ордер на продажу."""
    with Client(TOKEN) as client:
        response = client.orders.post_order(
            figi=figi,
            quantity=quantity,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            account_id=DB_CONFIG['account_id'],
            order_type=OrderType.ORDER_TYPE_MARKET,
            order_id=str(hash(figi))[:36]
        )
        return response


def update_position_db(ticker):
    """Обновляем запись в БД — закрываем позицию."""
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE positions
                SET avg_price = NULL, quantity = 0, in_market = FALSE
                WHERE ticker = %s
            """, (ticker,))
            conn.commit()


def send_report_to_telegram(positions_data):
    """Формируем и отправляем отчет в Telegram."""
    message = "*[ПЕСОЧНИЦА] Закрыты все открытые позиции*\n\n"

    for data in positions_data:
        ticker = data['ticker']
        entry_price = data['entry_price']
        exit_price = data['exit_price']
        entry_date = data['entry_date'].strftime('%Y-%m-%d')
        exit_date = data['exit_date'].strftime('%Y-%m-%d')
        days = (data['exit_date'] - data['entry_date']).days
        profit_percent = ((exit_price - entry_price) / entry_price) * 100

        message += f"""
[{ticker}]
Вход: {entry_date}, {entry_price:.2f} руб.
Выход: {exit_date}, {exit_price:.2f} руб.
Доходность: {profit_percent:.2f}%
Дней: {days}
{'-' * 20}
        """

    send_telegram_message(message)
    logging.info("[seller.py] Сообщение с отчетом отправлено в Telegram")


def main():
    logging.info("[seller.py] Запуск скрипта для закрытия позиций")

    positions = get_positions()
    if not positions:
        logging.info("[seller.py] Нет открытых позиций для закрытия")
        send_telegram_message("*[seller.py] Нет открытых позиций для закрытия*")
        return

    results = []

    for ticker, avg_price, quantity, created_at in positions:
        figi = get_figi_by_ticker(ticker)
        if not figi:
            logging.warning(f"[seller.py] Не найден FIGI для тикера {ticker}")
            continue

        # Получаем текущую цену (через последнюю свечу или ордербуку)
        # Для примера используем цену закрытия последней свечи (заменить на актуальную)
        exit_price = Decimal(100.00)  # ← здесь должна быть реальная цена из API

        # Выполняем продажу
        try:
            sell_position(figi, quantity, exit_price)
            logging.info(f"[seller.py] Продано {quantity} шт. {ticker} по {exit_price:.2f} руб.")
        except Exception as e:
            logging.error(f"[seller.py] Ошибка при продаже {ticker}: {e}")
            continue

        # Обновляем БД
        update_position_db(ticker)

        # Сохраняем данные для отчета
        results.append({
            'ticker': ticker,
            'entry_price': avg_price,
            'exit_price': exit_price,
            'entry_date': created_at,
            'exit_date': datetime.datetime.now()
        })

    # Отправляем отчет
    if results:
        send_report_to_telegram(results)

    logging.info("[seller.py] Все позиции закрыты")


if __name__ == "__main__":
    main()