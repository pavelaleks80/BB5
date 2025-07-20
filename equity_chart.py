import matplotlib.pyplot as plt
import pandas as pd
from datetime import timedelta

# === Входные параметры ===
INITIAL_CAPITAL = 300_000  # Начальный депозит
INVESTMENT_PER_ENTRY = 5000  # Сумма на каждую покупку/докупку

# === Данные сделок из отчёта backtester.py ===
# Формат: (тиккер, тип сделки, дата, цена, профит %)
trade_data = [
    ("NLMK", "buy", "2025-02-04", 1195.58, 0),
    ("NLMK", "rebuy", "2025-02-04", 1195.58, 0),
    ("NLMK", "rebuy", "2025-02-05", 1178.52, 0),
    ("NLMK", "sell", "2025-02-13", 1315.64, 10.57),

    ("CHMF", "buy", "2025-03-27", 1248.13, 0),
    ("CHMF", "rebuy", "2025-03-27", 1248.13, 0),
    ("CHMF", "rebuy", "2025-03-28", 1203.60, 0),
    ("CHMF", "rebuy", "2025-03-29", 1159.47, 0),
    ("CHMF", "rebuy", "2025-03-30", 1132.99, 0),
    ("CHMF", "rebuy", "2025-03-31", 1126.17, 0),
    ("CHMF", "rebuy", "2025-04-02", 1140.01, 0),
    ("CHMF", "rebuy", "2025-04-03", 1164.88, 0),
    ("CHMF", "rebuy", "2025-04-04", 1129.38, 0),
    ("CHMF", "rebuy", "2025-04-05", 1083.24, 0),
    ("CHMF", "rebuy", "2025-04-06", 1094.07, 0),
    ("CHMF", "rebuy", "2025-04-07", 1098.69, 0),
    ("CHMF", "rebuy", "2025-04-08", 1059.17, 0),
    ("CHMF", "rebuy", "2025-04-09", 995.98, 0),
    ("CHMF", "rebuy", "2025-04-10", 1063.18, 0),
    ("CHMF", "rebuy", "2025-04-11", 1025.47, 0),
    ("CHMF", "rebuy", "2025-04-12", 1066.79, 0),
    ("CHMF", "rebuy", "2025-04-13", 1083.44, 0),
    ("CHMF", "rebuy", "2025-04-14", 1085.25, 0),
    ("CHMF", "rebuy", "2025-04-15", 1034.49, 0),
    ("CHMF", "rebuy", "2025-04-16", 1046.53, 0),
    ("CHMF", "rebuy", "2025-04-17", 1044.52, 0),
    ("CHMF", "rebuy", "2025-04-18", 1058.97, 0),
    ("CHMF", "sell", "2025-04-18", 1058.97, 4.05),

    ("SBER", "buy", "2025-03-30", 303.20, 0),
    ("SBER", "rebuy", "2025-03-31", 300.00, 0),
    ("SBER", "rebuy", "2025-04-05", 285.25, 0),
    ("SBER", "rebuy", "2025-04-06", 285.35, 0),
    ("SBER", "rebuy", "2025-04-07", 285.30, 0),
    ("SBER", "rebuy", "2025-04-08", 290.00, 0),
    ("SBER", "rebuy", "2025-04-09", 280.91, 0),
    ("SBER", "rebuy", "2025-04-10", 283.11, 0),
    ("SBER", "rebuy", "2025-04-11", 282.20, 0),
    ("SBER", "rebuy", "2025-04-12", 281.10, 0),
    ("SBER", "sell", "2025-04-13", 300.88, -2.90),

    ("GMKN", "buy", "2025-05-06", 108.08, 0),
    ("GMKN", "rebuy", "2025-05-06", 108.08, 0),
    ("GMKN", "rebuy", "2025-05-07", 108.22, 0),
    ("GMKN", "sell", "2025-05-13", 114.22, 5.63),

    ("TATN", "buy", "2025-04-02", 655.96, 0),
    ("TATN", "rebuy", "2025-04-02", 655.96, 0),
    ("TATN", "rebuy", "2025-04-04", 654.86, 0),
    ("TATN", "rebuy", "2025-04-05", 617.55, 0),
    ("TATN", "rebuy", "2025-04-06", 610.23, 0),
    ("TATN", "rebuy", "2025-04-07", 596.05, 0),
    ("TATN", "rebuy", "2025-04-08", 588.02, 0),
    ("TATN", "rebuy", "2025-04-09", 579.13, 0),
    ("TATN", "rebuy", "2025-04-10", 570.37, 0),
    ("TATN", "rebuy", "2025-04-11", 560.01, 0),
    ("TATN", "rebuy", "2025-04-12", 550.00, 0),
    ("TATN", "sell", "2025-04-13", 556.80, 4.65),

    # Продолжи добавлять свои сделки сюда
]

# === Обработка данных ===
# Генерируем фиктивные даты для графика
start_date = pd.to_datetime("2025-02-01")
equity_curve = [INITIAL_CAPITAL]
dates = [start_date]
current_capital = INITIAL_CAPITAL

for trade in trade_data:
    ticker, trade_type, date_str, price, profit_percent = trade
    date = pd.to_datetime(date_str)

    if trade_type == "buy":
        invested = INVESTMENT_PER_ENTRY
        current_capital -= invested
        avg_price = price
        entries = [price]
        entry_amounts = [invested]

    elif trade_type == "rebuy":
        invested = INVESTMENT_PER_ENTRY
        current_capital -= invested
        avg_price = sum(entries + [price]) / (len(entries) + 1)
        entries.append(price)
        entry_amounts.append(invested)

    elif trade_type == "sell":
        total_investment = sum(entry_amounts)
        profit = total_investment * (profit_percent / 100)
        current_capital += total_investment + profit
        equity_curve.append(current_capital)
        dates.append(date)
        # Очищаем позицию после продажи
        entries = []
        entry_amounts = []

# === Построение графика ===
df_equity = pd.DataFrame({
    'Date': dates,
    'Balance': equity_curve
})
df_equity = df_equity.sort_values('Date').reset_index(drop=True)

# Расчёт максимальной просадки
df_equity['Peak'] = df_equity['Balance'].cummax()
df_equity['Drawdown'] = (df_equity['Balance'] - df_equity['Peak']) / df_equity['Peak'] * 100

# === Вывод графика ===
plt.figure(figsize=(14, 7))
plt.plot(df_equity['Date'], df_equity['Balance'], marker='o', linestyle='-', color='green', label="Баланс")
plt.fill_between(df_equity['Date'], df_equity['Balance'], df_equity['Peak'], color='lightcoral', alpha=0.3, label="Просадка")

# Подписи
plt.title("📈 Эквити за 120 дней торговли\n(Начальный депозит: 300 000 ₽ | Вход: 5000 ₽ на покупку/докупку)")
plt.xlabel("Дата")
plt.ylabel("Баланс (₽)")
plt.grid(True)
plt.legend()
plt.tight_layout()

# Отображение графика
plt.show()

# === Метрики ===
total_return = (current_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
days_traded = (df_equity['Date'].iloc[-1] - df_equity['Date'].iloc[0]).days
annualized_return = ((1 + total_return / 100) ** (365 / days_traded)) - 1
annualized_return *= 100
max_drawdown = df_equity['Drawdown'].min()

print(f"\n📈 Общий доход: {total_return:.2f}%")
print(f"📅 Количество дней торговли: {days_traded}")
print(f"🎯 Годовая доходность (анализируемая): ~{annualized_return:.2f}%")
print(f"📉 Максимальная просадка: {max_drawdown:.2f}%")

# === Сохранение в CSV ===
df_equity[['Date', 'Balance']].to_csv("equity_history.csv", index=False)
print("✅ История депозита сохранена в equity_history.csv")