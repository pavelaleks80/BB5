"""
data_loader.py

Назначение: Загружает данные по акциям из Tinkoff Invest API,
сохраняет их в PostgreSQL с расчётом Полос Боллинджера.

Используется:
- Tinkoff Invest API
- PostgreSQL
"""
import sys
import time
import os
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql
from tinkoff.invest import Client, CandleInterval
from tinkoff.invest.utils import now
from tinkoff.invest.exceptions import RequestError
from psycopg2.extras import execute_batch
from config import DB_CONFIG, TOKEN, TICKERS

def connect():
    """Подключение к базе данных PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG)

def get_figi_for_ticker(client, ticker):
    
    """
Получает FIGI и дату первой свечи для заданного тикера.

Args:
    client: клиент Tinkoff Invest API
    ticker: тикер акции

Returns:
    figi: уникальный идентификатор инструмента
    first_candle_date: дата первой доступной свечи
"""
    try:
        instruments = client.instruments.shares().instruments
        for instrument in instruments:
            if instrument.ticker == ticker:
                print(f"Для тикера {ticker} найдена дата первой свечи: {instrument.first_1day_candle_date}")
                return instrument.figi, instrument.first_1day_candle_date
        print(f"Для тикера {ticker} не найдена информация о первой свече")
        return None, None
    except RequestError as e:
        print(f"Ошибка при получении FIGI для {ticker}: {e}")
        return None, None


def find_earliest_available_date(client, figi, ticker):
    """
    Ищет самую раннюю доступную дату для получения данных по тикеру.

    Args:
        client: клиент Tinkoff Invest API
        figi: идентификатор инструмента
        ticker: тикер акции

    Returns:
        date: самая ранняя доступная дата
    """
    end_date = now()
    start_date = datetime(1900, 1, 1)
    print(f"Поиск самой ранней доступной даты для FIGI {figi} (тикер: {ticker})")

    try:
        candles = client.market_data.get_candles(
            figi=figi,
            from_=start_date,
            to=start_date + timedelta(days=1),
            interval=CandleInterval.CANDLE_INTERVAL_DAY
        )
        if candles.candles:
            print(f"Найдены данные с самой ранней даты {start_date}")
            return start_date
    except RequestError:
        pass

    last_successful_date = None
    while start_date < end_date:
        mid_date = start_date + (end_date - start_date) // 2
        try:
            candles = client.market_data.get_candles(
                figi=figi,
                from_=mid_date,
                to=mid_date + timedelta(days=1),
                interval=CandleInterval.CANDLE_INTERVAL_DAY
            )
            if candles.candles:
                print(f"Найдены данные для даты {mid_date}")
                last_successful_date = mid_date
                end_date = mid_date - timedelta(days=1)
            else:
                start_date = mid_date + timedelta(days=1)
        except RequestError:
            start_date = mid_date + timedelta(days=1)

    if last_successful_date:
        print(f"Самая ранняя доступная дата: {last_successful_date}")
    else:
        print("Не удалось найти доступные данные")
    return last_successful_date


def get_candles(client, figi, from_date, ticker):
    """
    Загружает исторические данные по свечам за указанный период.

    Args:
        client: клиент Tinkoff Invest API
        figi: идентификатор инструмента
        from_date: начальная дата
        ticker: тикер акции

    Returns:
        candles: список свечей
    """
    all_candles = []
    current_date = from_date
    end_date = now()
    chunk_size = timedelta(days=365)

    while current_date < end_date:
        try:
            next_date = min(current_date + chunk_size, end_date)
            candles = client.market_data.get_candles(
                figi=figi,
                from_=current_date,
                to=next_date,
                interval=CandleInterval.CANDLE_INTERVAL_DAY
            )
            if candles.candles:
                all_candles.extend(candles.candles)
            current_date = next_date
        except RequestError as e:
            print(f"Ошибка при получении свечей: {e}")
            break

    print(f"Всего загружено {len(all_candles)} записей для {ticker}")
    return all_candles


def calculate_bollinger_bands(df, window=20, num_std=2):
    """
    Рассчитывает значения Полос Боллинджера.

    Args:
        df: DataFrame с данными по ценам
        window: окно скользящего среднего
        num_std: количество стандартных отклонений

    Returns:
        df: DataFrame с добавленными колонками sma, upper_band, lower_band
    """
    df['sma'] = df['close'].rolling(window=window).mean()
    df['std'] = df['close'].rolling(window=window).std()
    df['upper_band'] = df['sma'] + (num_std * df['std'])
    df['lower_band'] = df['sma'] - (num_std * df['std'])
    return df


def create_table(conn, ticker):
    """
    Создаёт таблицу в PostgreSQL для хранения данных по конкретному тикеру.

    Args:
        conn: соединение с базой данных
        ticker: тикер акции
    """
    table_name = f"quotes_{ticker.lower()}"
    print(f"Создание таблицы {table_name} для тикера {ticker}")

    query = sql.SQL("""
        CREATE TABLE IF NOT EXISTS {} (
            date TIMESTAMP PRIMARY KEY,
            open NUMERIC,
            high NUMERIC,
            low NUMERIC,
            close NUMERIC,
            volume BIGINT,
            sma NUMERIC,
            upper_band NUMERIC,
            lower_band NUMERIC
        )
    """).format(sql.Identifier(table_name))

    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
        conn.commit()
        print(f"Таблица {table_name} успешно создана")
    except Exception as e:
        print(f"Ошибка при создании таблицы: {e}")


def save_to_db(conn, ticker, candles):
    """
    Сохраняет данные о свечах в PostgreSQL после расчёта индикаторов,
    предварительно проверяя, какие даты уже существуют.
    """
    if not candles:
        print(f"Нет данных для сохранения для тикера {ticker}")
        return

    table_name = f"quotes_{ticker.lower()}"
    
    # Получаем список дат, уже существующих в БД
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT date FROM {}").format(sql.Identifier(table_name)))
            existing_dates = set(row[0] for row in cursor.fetchall())
    except Exception as e:
        print(f"Ошибка при чтении существующих дат: {e}")
        existing_dates = set()

    # Преобразование в DataFrame
    data = []
    for candle in candles:
        if candle.time in existing_dates:
            continue  # Пропускаем, если такая дата уже есть
        data.append({
            'date': candle.time,
            'open': float(candle.open.units + candle.open.nano / 1e9),
            'high': float(candle.high.units + candle.open.nano / 1e9),
            'low': float(candle.low.units + candle.low.nano / 1e9),
            'close': float(candle.close.units + candle.close.nano / 1e9),
            'volume': int(candle.volume)
        })

    if not data:
        print(f"Нет новых данных для тикера {ticker}, все записи уже в БД")
        return

    df = pd.DataFrame(data)
    df = calculate_bollinger_bands(df)
    if 'std' in df.columns:
        df.drop(columns=['std'], inplace=True)
    df.dropna(inplace=True)

    # Подготовка данных для вставки
    records = df.to_records(index=False)
    data_to_insert = [
        tuple(
            None if pd.isna(x) else (
                int(x) if isinstance(x, np.integer) else
                float(x) if isinstance(x, np.floating) else x
            )
            for x in row
        )
        for row in records
    ]

    print(f"Сохранение {len(data_to_insert)} новых записей в таблицу {table_name}")
    try:
        with conn.cursor() as cursor:
            insert_query = sql.SQL("""
                INSERT INTO {}
                (date, open, high, low, close, volume, sma, upper_band, lower_band)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date) DO NOTHING
            """).format(sql.Identifier(table_name))
            execute_batch(cursor, insert_query, data_to_insert, page_size=500)
        conn.commit()
        print(f"Новые данные для {ticker} успешно сохранены")
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")

def main():
    """
    Основная функция запуска процесса загрузки данных.
    """    
    start_time = time.time()
    
    # Проверка токена
    if not TOKEN or TOKEN == 'TOKEN':
        print("ОШИБКА: Необходимо указать токен API Тинькофф Инвестиций!")
        return

    # Подключение к PostgreSQL
    try:
        print("Подключение к PostgreSQL...")
        conn = psycopg2.connect(**DB_CONFIG)
        print("Успешное подключение к PostgreSQL")
    except Exception as e:
        print(f"Ошибка подключения к PostgreSQL: {e}")
        return

    # Подключение к API Тинькофф
    try:
        print("Подключение к API Тинькофф Инвестиций...")
        with Client(TOKEN) as client:
            print("Успешное подключение к API Тинькофф")
            for ticker in tqdm(TICKERS, desc="Обработка тикеров"):
                try:
                    print(f"\nНачинаем обработку тикера {ticker}")

                    # Получаем FIGI и дату первой свечи для тикера
                    figi, first_candle_date = get_figi_for_ticker(client, ticker)
                    if not figi:
                        tqdm.write(f"FIGI не найден для тикера {ticker}, пропускаем...")
                        continue

                    # Определяем самую раннюю доступную дату
                    if first_candle_date:
                        earliest_date = first_candle_date
                        print(f"Используем дату первой свечи из информации об инструменте: {earliest_date}")
                    else:
                        print("Дата первой свечи не найдена, выполняем поиск...")
                        earliest_date = find_earliest_available_date(client, figi, ticker)
                        if not earliest_date:
                            tqdm.write(f"Не удалось определить начальную дату для {ticker}, пропускаем...")
                            continue
                        print(f"Найдена самая ранняя доступная дата: {earliest_date}")

                    tqdm.write(f"Тикер {ticker}: загрузка данных с {earliest_date}")

                    # Создаем таблицу в БД
                    create_table(conn, ticker)

                    # Получаем все свечи
                    candles = get_candles(client, figi, earliest_date, ticker)

                    # Сохраняем в БД
                    save_to_db(conn, ticker, candles)

                    tqdm.write(f"Тикер {ticker}: сохранено {len(candles)} записей")

                except Exception as e:
                    tqdm.write(f"Ошибка при обработке тикера {ticker}: {str(e)}")
                    continue

    except Exception as e:
        print(f"Ошибка подключения к API Тинькофф: {e}")

    # Закрываем соединение с БД
    print("Закрытие соединения с PostgreSQL")
    conn.close()
    print("Готово!")

    # Время выполнения
    exec_time = time.time() - start_time
    print(f"\n Все задачи выполнены за {exec_time:.2f} секунд")

if __name__ == "__main__":
    main()