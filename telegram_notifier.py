"""
telegram_notifier.py

Однократно проверяет наличие новых сигналов в БД,
отправляет их в Telegram и завершает работу.
"""

import time
import psycopg2
from telegram_bot import send_telegram_message
from config import DB_CONFIG
from tqdm import tqdm

SEND_DELAY = 3
ERROR_DELAY = 5


def connect():
    """Подключение к базе данных PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG)


def get_unsent_signals():
    """
    Получает список сигналов, которые ещё не были отправлены (нет в signals_sent)
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, ticker, signal_type, signal_date FROM signals_log
                WHERE is_active = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM signals_sent
                      WHERE signal_id = signals_log.id
                  )
                ORDER BY signal_date DESC
            """)
            return cur.fetchall()


def mark_as_sent(signal_id):
    """
    Помечает сигнал как отправленный, записывая его ID в таблицу signals_sent
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO signals_sent (signal_id)
                VALUES (%s)
                ON CONFLICT (signal_id) DO NOTHING
            """, (signal_id,))
            conn.commit()


def create_sent_table():
    """
    Создаёт таблицу signals_sent, если её нет
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signals_sent (
                    signal_id INT PRIMARY KEY
                )
            """)
            conn.commit()


def send_queued_signals():
    """
    Отправляет сигналы из БД в Telegram и завершает работу.
    Подходит для однократного запуска через планировщик.
    """
    create_sent_table()
    print("[+] Telegram Notifier: запущен")

    # Получаем список сигналов
    signals = get_unsent_signals()

    if not signals:
        print("[-] Нет новых сигналов. Завершение работы.")
        return

    print(f"[+] Найдено {len(signals)} новых сигналов. Отправка...")

    # Отправляем каждый сигнал
    for signal in tqdm(signals, desc="Отправка сигналов", unit="сигнал"):
        signal_id, ticker, signal_type, signal_date = signal
        message = f"* Сигнал {signal_type} ({ticker})\nДата: {signal_date}"

        try:
            send_telegram_message(message)
            mark_as_sent(signal_id)
            time.sleep(SEND_DELAY)
        except Exception as e:
            tqdm.write(f"[X] Ошибка при отправке сигнала {signal_id}: {e}")
            time.sleep(ERROR_DELAY)

    print("[V] Все сигналы отправлены. Работа завершена.")


if __name__ == "__main__":
    send_queued_signals()