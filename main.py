"""
main.py

Управляющий скрипт.
Запускает:
- data_loader.py → загрузка данных из Tinkoff Invest API
- signals_processor.py → генерация торговых сигналов
- trader_executor.py → исполнение сделок по сигналам
"""

import subprocess
from tqdm import tqdm
import time
import os
from datetime import datetime, timedelta
import psycopg2
from config import DB_CONFIG

# Файл лога
LOG_FILE = "log_sandbox_main.txt"


def log_message(message):
    """Записывает сообщение в лог с временной меткой"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_script(script_name):
    """ Запускает указанный скрипт и возвращает успех/ошибку """
    try:
        result = subprocess.run(
            ["python", script_name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = f"Ошибка при выполнении {script_name}:\n{e.stderr}"
        return False, error_msg

def clear_log():
    """Очищает лог-файл, если он существует"""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

# Проверяет наличие обновлённых данных в БД
def data_is_ready():
    """
    Проверяет, есть ли данные за предыдущий день хотя бы по одному тикеру
    """
    try:

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM quotes_gazp 
                WHERE date = CURRENT_DATE - INTERVAL '1 day'
            )
        """)
        is_ready = cur.fetchone()[0]
        conn.close()
        return is_ready
    except Exception as e:
        print(f"[ERROR] Не удалось проверить данные в БД: {e}")
        return False

def main():
    start_time = time.time()
    clear_log()

    # --- Добавляем дату и время запуска ---
    launch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{launch_time} Начало выполнения main.py")
    log_message("Начало выполнения main.py")
    # ------------------------------------

    # Список скриптов для запуска
    tasks = [
        ("data_loader.py", 0),  # ждём 10 секунд после загрузки
        ("signals_processor.py", 0),  # ждём 5 секунд после signals_processor
        ("telegram_notifier.py", 0)  # выполняем без задержки
    ]

#===================================================================================
#    for script_name, delay in tqdm(tasks, desc="Выполнение этапов", unit="этап"):
#        tqdm.write(f"[ПЕСОЧНИЦА] Выполняется: {script_name}")
#        success, output = run_script(script_name)
#        if success:
#            log_message(f"{script_name} выполнен успешно.")
#            tqdm.write(f"[ПЕСОЧНИЦА] {script_name} завершён успешно.")
#        else:
#            log_message(output)
#            tqdm.write(f"[X ПЕСОЧНИЦА] Ошибка в {script_name}: {output}")
#        time.sleep(delay)
#===================================================================================
#=== Изменение от 090725 ============================
    for script_name, delay in tqdm(tasks, desc="Выполнение этапов", unit="этап"):
        tqdm.write(f"[ПЕСОЧНИЦА] Выполняется: {script_name}")

        # Если это signals_processor — ждём готовности данных
        if script_name == "signals_processor.py":
            wait_start = time.time()
            timeout = 600  # 10 минут
            while not data_is_ready():
                elapsed = time.time() - wait_start
                if elapsed > timeout:
                    log_message("Таймаут ожидания данных для signals_processor")
                    tqdm.write("Таймаут ожидания данных для signals_processor")
                    break
                tqdm.write("Ожидание загрузки данных...")
                time.sleep(60) # интервал проверки1 минута

    # Запуск скрипта
        success, output = run_script(script_name)
        if success:
            log_message(f"{script_name} выполнен успешно.")
            tqdm.write(f"[ПЕСОЧНИЦА] {script_name} завершён успешно.")
        else:
            log_message(output)
            tqdm.write(f"[X ПЕСОЧНИЦА] Ошибка в {script_name}: {output}")
    
        time.sleep(delay)
#=== END Изменение от 090725 ============================

    log_message("main.py завершил выполнение.")
    print("FIN-ПЕСОЧНИЦА main.py завершил выполнение.")

    exec_time = time.time() - start_time
    print(f"\n ПЕСОЧНИЦА / Все задачи выполнены за {exec_time:.2f} секунд")
    log_message(f"Все задачи выполнены за {exec_time:.2f} секунд")
    
if __name__ == "__main__":
    main()