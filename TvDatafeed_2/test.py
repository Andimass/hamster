import datetime
import itertools
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# Функция для расчета RSI
def calculate_rsi(data, period=14):
    delta = data['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# Загрузка данных
csv_file_path_4 = 'BINANCE_BTCUSDT, 240_4961b.csv'  # Укажите путь к вашему CSV файлу
hist_data = pd.read_csv(csv_file_path_4, parse_dates=['time'], index_col='time')
rsi = calculate_rsi(hist_data)

# Начальный капитал
initial_capital = 1000  # Начальная сумма в долларах
position_size_percentage = 5  # Процент капитала для входа в позицию

# Определение прибыли в зависимости от времени нахождения в позиции
def financial_test(crossing_points, hist_data, max_bars=9):
    best_profit = 0
    best_holding_period = 0

    for bars in range(1, max_bars + 1):
        capital = initial_capital
        for _, _, entry_idx in crossing_points:
            if entry_idx + bars < len(hist_data):
                entry_close = hist_data.iloc[entry_idx]['close']
                exit_close = hist_data.iloc[entry_idx + bars]['close']

                # Размер позиции
                position_size = (capital * position_size_percentage) / 100

                # Расчет прибыли
                profit = (exit_close - entry_close) / entry_close * 100

                # Обновление капитала
                capital += profit

        if capital > best_profit:
            best_profit = capital
            best_holding_period = bars

    return best_profit, best_holding_period

# Функция тестирования стратегии
def test_strategy(params, rsi, hist_data):
    lower_level_dynamic = []
    crossing_points = []

    current_max_rsi = None
    current_lower_level = params['lower_start_50']
    previous_max_rsi_below_50 = None
    time_interval = datetime.timedelta(hours=12)
    last_crossing_time = None

    for idx, value in enumerate(rsi):
        # Логика для нижнего уровня
        if value > 50:
            if current_max_rsi is None or value > current_max_rsi:
                current_max_rsi = value
            current_lower_level = params['lower_start_50'] + (
                    current_max_rsi - params['lower_start_50']) / params['divisor_50']
            previous_max_rsi_below_50 = None
        elif 40 < value < 50:
            if previous_max_rsi_below_50 is None or value > previous_max_rsi_below_50:
                previous_max_rsi_below_50 = value
            current_lower_level = params['lower_start_40'] + (
                    previous_max_rsi_below_50 - params['lower_start_40']) / params['divisor_40']
        elif 30 < value < 40:
            if previous_max_rsi_below_50 is None or value > previous_max_rsi_below_50:
                previous_max_rsi_below_50 = value
            current_lower_level = params['lower_start_30'] + (
                    previous_max_rsi_below_50 - params['lower_start_30']) / params['divisor_30']
        elif value < 30:
            if previous_max_rsi_below_50 is None or value > previous_max_rsi_below_50:
                previous_max_rsi_below_50 = value
            current_lower_level = params['lower_start_20'] + (
                    previous_max_rsi_below_50 - params['lower_start_20']) / params['divisor_20']
        else:
            current_lower_level = params['lower_start_50']
            previous_max_rsi_below_50 = None

        lower_level_dynamic.append(current_lower_level)

        if value <= current_lower_level:
            current_time = hist_data.index[idx]
            if last_crossing_time is None or current_time - last_crossing_time >= time_interval:
                crossing_points.append((current_time, value, idx))
                last_crossing_time = current_time
                current_max_rsi = None
                previous_max_rsi_below_50 = None

    # Финансовый тест для точки пересечения
    best_profit, best_holding_period = financial_test(crossing_points, hist_data)

    # Подсчет удачных и неудачных сделок
    successful_trades = 0
    unsuccessful_trades = 0

    for _, _, entry_idx in crossing_points:
        if entry_idx + 1 < len(hist_data):
            entry_close = hist_data.iloc[entry_idx]['close']
            next_low = hist_data.iloc[entry_idx + 1]['low']

            # Условие для неудачной сделки
            if (entry_close - next_low) / entry_close > 0.01:
                unsuccessful_trades += 1
            else:
                successful_trades += 1

    return successful_trades, unsuccessful_trades, best_profit, best_holding_period

# Поиск лучших параметров и времени удержания позиции
best_params = None
best_holding_period = 0
max_profit = 0

lower_start_values = range(10, 51, 3)
divisor_values = [1.5, 2, 2.5, 3]
params_combinations = itertools.product(
    lower_start_values, lower_start_values, lower_start_values, lower_start_values,
    divisor_values
)

total_combinations = len(lower_start_values) * len(lower_start_values) * len(lower_start_values) * len(lower_start_values) * len(divisor_values)

current_combination = 0

for lower_start_50, lower_start_40, lower_start_30, lower_start_20, divisor in params_combinations:
    params = {
        'lower_start_50': lower_start_50,
        'lower_start_40': lower_start_40,
        'lower_start_30': lower_start_30,
        'lower_start_20': lower_start_20,
        'divisor_50': divisor,
        'divisor_40': divisor,
        'divisor_30': divisor,
        'divisor_20': divisor
    }

    successful_trades, unsuccessful_trades, profit, holding_period = test_strategy(params, rsi, hist_data)

    if profit > max_profit:
        max_profit = profit
        best_params = params
        best_holding_period = holding_period

    current_combination += 1
    progress = (current_combination / total_combinations) * 100
    print(f"Progress: {progress:.2f}%")

# Вывод лучших параметров и оптимального времени нахождения в позиции
print(f"Лучшие параметры: {best_params}")
print(f"Максимальная прибыль: {max_profit:.2f}$")
print(f"Оптимальное время нахождения в позиции: {best_holding_period * 4} часов")
print(f"Количество успешных сделок: {successful_trades}")
print(f"Количество неудачных сделок: {unsuccessful_trades}")
