"""
signals_processor.py
Назначение: Обрабатывает торговые сигналы на основе исторических данных
из базы данных, рассчитывает гармоническую среднюю цену и отправляет уведомления в Telegram.
Функционал:
- "Внимание" → цена закрытия ниже нижней полосы Боллинджера, после падения ниже SMA(20)
- "Купи" → цена следующей свечи (или более далёкой) ниже close сигнальной свечи "ВНИМАНИЕ", но не выше SMA(20)
- "Докупи" → цена ниже текущей гармонической средней
- "Продай" → цена выше SMA(20)
"""

import psycopg2
import pandas as pd
from datetime import datetime
from tqdm import tqdm  # Импортируем tqdm для прогресс-бара
from config import DB_CONFIG, TICKERS
from telegram_bot import send_telegram_message
import time

N = 5  # Количество дней истории (влево) для проверки наличия сигнала ВНИМАНИЕ

# Задержка в отправке сообщений
def send_with_delay(message):
    try:
        send_telegram_message(message)
        time.sleep(3)  # Задержка 3 секунды между сообщениями
    except Exception as e:
        print(f" Ошибка при отправке сообщения: {e}")
        time.sleep(5)  # Увеличиваем задержку при ошибке

# Добавлено 17.07.25 Сообщение о начала анализа сигналов
msg = "* ПЕСОЧНИЦА Начинаем анализ сигналов*"
send_with_delay(msg)
print(msg)

def connect():
    """Подключение к базе данных PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG)


# Создаёт таблицу для хранения сигналов
def create_signals_log_table():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signals_log (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    signal_date DATE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    parent_id INTEGER REFERENCES signals_log(id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(ticker, signal_type, signal_date, parent_id)
                )
            """)
            conn.commit()


def get_last_n_days(ticker, n=N):
    """Получает последние N дней котировок по тикеру"""
    table_name = f"quotes_{ticker.lower()}"
    query = f"""
        SELECT date, open, high, low, close, volume, sma, upper_band, lower_band
        FROM {table_name}
        WHERE date <= CURRENT_DATE
        ORDER BY date DESC
        LIMIT %s
    """
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (n,))
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                df = pd.DataFrame(data, columns=columns)
                return df.sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f"Ошибка при загрузке данных для {ticker}: {e}")
        return pd.DataFrame()


# Класс определяющий порядок поступления сигналов
class PositionState:
    def __init__(self):
        self.state = {}  # ticker -> 'attention' / 'in_market'

    def set_attention(self, ticker, date, price):
        self.state[ticker] = {'status': 'attention', 'date': date, 'price': price}

    def set_in_market(self, ticker):
        if ticker in self.state:
            self.state[ticker]['status'] = 'in_market'

    def reset(self, ticker):
        self.state.pop(ticker, None)

    def get_state(self, ticker):
        return self.state.get(ticker, None)


position_state = PositionState()


def calculate_harmonic_avg(prices):
    """Рассчитывает гармоническое среднее значение цен"""
    if not prices:
        return None
    try:
        inv_sum = sum(1 / price for price in prices)
        return len(prices) / inv_sum
    except ZeroDivisionError:
        return None


def create_positions_table():
    """Создаёт таблицу для хранения открытых позиций и истории покупок"""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL UNIQUE,
                    buy_level NUMERIC,
                    avg_price NUMERIC,
                    quantity INT DEFAULT 10,
                    in_market BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP
                    )
            """)
            conn.commit()


def log_signal(ticker, signal_type, signal_date, parent_id=None):
    """Записывает сигнал в таблицу signals_log с указанием родительского сигнала"""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO signals_log (ticker, signal_type, signal_date, parent_id)
                VALUES (%s, %s, %s, %s)
            """, (ticker, signal_type, signal_date, parent_id))
            conn.commit()


def has_active_attention_signal(ticker, date):
    """
    Проверяет, есть ли активный сигнал "ВНИМАНИЕ" для указанной даты
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM signals_log
                WHERE ticker = %s AND signal_type = 'ВНИМАНИЕ'
                  AND signal_date = %s AND is_active = TRUE
                LIMIT 1
            """, (ticker, date))
            return cur.fetchone() is not None


def deactivate_related_signals(ticker):
    """
    Деактивирует все связанные сигналы после продажи
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE signals_log
                SET is_active = FALSE
                WHERE ticker = %s
                  AND signal_type IN ('ВНИМАНИЕ', 'КУПИ', 'ДОКУПИ')
                  AND is_active = TRUE
            """, (ticker,))


def was_buy_signal_received(ticker, attention_date):
    """
    Проверяет, был ли сигнал КУПИ на основе данного сигнала ВНИМАНИЕ
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM signals_log
                WHERE ticker = %s AND signal_type = 'КУПИ'
                  AND signal_date > %s
                LIMIT 1
            """, (ticker, attention_date))
            return cur.fetchone() is not None


def find_trend_change(df):
    """Находит индекс последнего случая, когда цена пересекла SMA(20) сверху вниз."""
    df['crossed_below_sma'] = (df['close'] < df['sma']) & (df['close'].shift(1) >= df['sma'].shift(1))
    trend_change_rows = df[df['crossed_below_sma']]
    if not trend_change_rows.empty:
        return trend_change_rows.index[-1]  # самый свежий случай
    return None


def update_position(ticker, price):
    """Обновляет или создаёт новую запись о позиции с флагом in_market = TRUE"""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO positions (ticker, buy_level, avg_price, quantity, in_market, updated_at)
                VALUES (%s, %s, %s, %s, TRUE, NOW())
                ON CONFLICT (ticker) DO UPDATE SET
                    avg_price = (
                        (positions.avg_price * positions.quantity + EXCLUDED.avg_price * EXCLUDED.quantity) /
                        (positions.quantity + EXCLUDED.quantity)
                    ),
                    quantity = positions.quantity + EXCLUDED.quantity,
                    updated_at = NOW(),
                    in_market = TRUE
            """, (ticker, price, price, 10))
            conn.commit()


def check_signals():
    """Основной метод проверки сигналов"""
    create_signals_log_table()
    create_positions_table()
    signals_found = False
    signal_summary = {  # Для хранения информации о найденных сигналах
    "ВНИМАНИЕ": [],
    "КУПИ": [],
    "ДОКУПИ": [],
    "ПРОДАЙ": []
}

    for ticker in tqdm(TICKERS, desc="Проверка сигналов по тикерам"):
        df = get_last_n_days(ticker)
        if len(df) < 2:
            continue

        latest = df.iloc[-1]  # Последняя свеча — самая новая
        print(f"[i] {ticker}: последняя дата = {latest['date'].date()}")

        # === Сигнал 1: ВНИМАНИЕ ===
        trend_change_index = find_trend_change(df)
        if trend_change_index is not None:
            df_after_trend = df.iloc[trend_change_index:]
            attention_rows = df_after_trend[df_after_trend['close'] < df_after_trend['lower_band']]
            if not attention_rows.empty:
                attention_row = attention_rows.iloc[0]

                # Проверяем, есть ли уже активный сигнал "ВНИМАНИЕ"
                if has_active_attention_signal(ticker, attention_row['date'].date()):
                    pass
                else:
                    msg = f"* ПЕСОЧНИЦА [!] ВНИМАНИЕ* ({ticker})\nДата: {attention_row['date'].date()}\nЦена: {attention_row['close']:.2f}"
                    send_with_delay(msg)
                    print(msg)
                    signals_found = True
                    signal_summary["ВНИМАНИЕ"].append(ticker)  # 17.07.25 - Добавляем тикер в итоговый список
                    log_signal(ticker, "ВНИМАНИЕ", attention_row['date'].date())
                    position_state.set_attention(ticker, attention_row['date'], attention_row['close'])

        # === Сигнал 2: КУПИ ===
        state = position_state.get_state(ticker)
        if state and state['status'] == 'attention':
            attention_date = state['date']
            attention_close = state['price']

            # Находим индекс сигнальной свечи
            attention_mask = (df['date'] == attention_date) & (df['close'] == attention_close)
            if attention_mask.any():
                attention_index = df.index[attention_mask][0]

                # Проверяем, был ли уже сформирован сигнал "КУПИ"
                if was_buy_signal_received(ticker, attention_date):
                    pass
                else:
                    for i in range(attention_index + 1, len(df)):
                        current_row = df.iloc[i]
                        if current_row['close'] < attention_close:
                            closes_since_attention = df.iloc[attention_index+1:i+1]['close']
                            smas_since_attention = df.iloc[attention_index+1:i+1]['sma']
                            if all(closes_since_attention <= smas_since_attention):

                                # Получаем ID сигнала "ВНИМАНИЕ"
                                with connect() as conn:
                                    with conn.cursor() as cur:
                                        cur.execute("""
                                            SELECT id FROM signals_log
                                            WHERE ticker = %s AND signal_type = 'ВНИМАНИЕ'
                                            AND signal_date = %s
                                            """, (ticker, attention_row['date'].date()))
                                        result = cur.fetchone()
                                        attention_signal_id = result[0] if result else None

                                # Записываем сигнал "КУПИ" с указанием parent_id
                                if attention_signal_id:
                                    log_signal(ticker, "КУПИ", current_row['date'].date(), parent_id=attention_signal_id)
                                else:
                                    log_signal(ticker, "КУПИ", current_row['date'].date())

                                msg = f"* ПЕСОЧНИЦА [+] КУПИ* ({ticker})\nДата: {current_row['date'].date()}\nЦель: {current_row['open']:.2f} (по open завтра)"
                                send_with_delay(msg)
                                print(msg)
                                signals_found = True
                                signal_summary["КУПИ"].append(ticker)  # 17.07.25 - Добавляем тикер в итоговый список
                                update_position(ticker, current_row['open'])
                                position_state.set_in_market(ticker)
                                break

        # === Сигнал 3: ДОКУПИ ===
        with connect() as conn:
            with conn.cursor() as cur:

# === Изменено 19.06.25 ===
                cur.execute("SELECT avg_price, in_market FROM positions WHERE ticker = %s", (ticker,))
                result = cur.fetchone()
                if result:
                    avg_price, in_market = result
                else:
                    avg_price, in_market = None, False
# === КОНЕЦ Изменено 19.06.25 ===
           
# === Изменено 19.06.25 ===
        if avg_price is not None and in_market and latest['close'] < avg_price:
# === КОНЕЦ Изменено 19.06.25 ===
            
            msg = f" * ПЕСОЧНИЦА [~] ДОКУПИ* ({ticker})\nДата: {latest['date'].date()}\nЦель: {latest['open']:.2f} (по open завтра)"
            send_with_delay(msg)
            print(msg)
            signals_found = True
            signal_summary["ДОКУПИ"].append(ticker)  # 17.07.25 - Добавляем тикер в итоговый список
            update_position(ticker, latest['open'])
            log_signal(ticker, "ДОКУПИ", latest['date'].date())

        # === Сигнал 4: ПРОДАЙ ===
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.avg_price, p.in_market, 
                           (SELECT 1 FROM signals_log 
                            WHERE ticker = %s AND signal_type = 'ПРОДАЙ' 
                            AND signal_date = CURRENT_DATE LIMIT 1) as already_sold
                    FROM positions p 
                    WHERE p.ticker = %s
                """, (ticker, ticker))
                result = cur.fetchone()

        avg_price = result[0] if result else None
        in_market = result[1] if result else False
        already_sold = result[2] if result else False

        if in_market and not already_sold and latest['close'] > latest['sma']:
            msg = f" * ПЕСОЧНИЦА [-] ПРОДАЙ* ({ticker})\nДата: {latest['date'].date()}\nЦель: {latest['open']:.2f} (по open завтра)"
            send_with_delay(msg)
            signals_found = True
            signal_summary["ПРОДАЙ"].append(ticker)  # 17.07.25 - Добавляем тикер в итоговый список
            log_signal(ticker, "ПРОДАЙ", latest['date'].date())
            print(msg)

            # Деактивируем связанные сигналы
            deactivate_related_signals(ticker)

            # Закрываем позицию в БД
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE positions 
                        SET in_market = FALSE, updated_at = NOW() 
                        WHERE ticker = %s
                    """, (ticker,))

            position_state.reset(ticker)

# === Изменено 17.07.25 Добавлено обобщающее сообщение ===        
    # Формируем и отправляем итоговое сообщение
    summary_lines = []
    for signal_type, tickers in signal_summary.items():
        if tickers:
            summary_lines.append(f"{signal_type}: {', '.join(tickers)}")

    if summary_lines:
        summary_text = "* ПЕСОЧНИЦА [i] ИТОГОВЫЕ СИГНАЛЫ *\n\n" + "\n".join(summary_lines)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        summary_text = f"* ПЕСОЧНИЦА [0] Сегодня {today} сигналов нет*"

    try:
        send_with_delay(summary_text)
    except Exception as e:
        print(f"[X] Ошибка при отправке итогового сообщения: {e}")
# === Конец 17.07.25 Добавлено обобщающее сообщение ===

if __name__ == "__main__":

    check_signals()
