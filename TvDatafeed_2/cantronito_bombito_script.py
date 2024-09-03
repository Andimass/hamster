import datetime
import enum
import gc
import itertools
import json
import warnings
from collections import defaultdict
import logging
import os
import random
import re
import string
import sys
import time
from math import sqrt
import ta
from scipy.optimize import minimize
from ta.volatility import AverageTrueRange
import plotly.graph_objs as go
from plotly.subplots import make_subplots

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from websocket import create_connection
import pandas_ta as ta
from telegram import Bot


logger = logging.getLogger(__name__)

bot_token = '7279656159:AAFxY2azZj8F6_kWviRfpp-yKR0naeJUeK8'
chat_id = '901107007'
bot = Bot(token=bot_token)

THREE_MINUTE_PATH = os.path.join(os.path.dirname(__file__), 'three_minute.json')
LAST_COIN_INDEX_PATH = os.path.join(os.path.dirname(__file__), 'last_coin_index.txt')

username = 'masyuckevich12345@gmail.com'
password = 'LHJybrk777;'

while True:
    try:

        class Interval(enum.Enum):
            in_1_minute = "1"
            in_3_minute = "3"
            in_5_minute = "5"
            in_15_minute = "15"
            in_30_minute = "30"
            in_45_minute = "45"
            in_1_hour = "1H"
            in_2_hour = "2H"
            in_3_hour = "3H"
            in_4_hour = "4H"
            in_daily = "1D"
            in_weekly = "1W"
            in_monthly = "1M"


        class TvDatafeed:
            __sign_in_url = 'https://www.tradingview.com/accounts/signin/'
            __search_url = 'https://symbol-search.tradingview.com/symbol_search/?text={}&hl=1&exchange={}&lang=en&type=&domain=production'
            __ws_headers = json.dumps({"Origin": "https://data.tradingview.com"})
            __signin_headers = {'Referer': 'https://www.tradingview.com'}
            __ws_timeout = 5

            def __init__(self, username: str = None, password: str = None) -> None:
                self.ws_debug = False
                self.token = self.__auth(username, password)
                if self.token is None:
                    self.token = "unauthorized_user_token"
                self.ws = None
                self.session = self.__generate_session()
                self.chart_session = self.__generate_chart_session()

            def __auth(self, username, password):
                if username is None or password is None:
                    token = None
                else:
                    data = {"username": username, "password": password, "remember": "on"}
                    try:
                        response = requests.post(url=self.__sign_in_url, data=data, headers=self.__signin_headers)
                        token = response.json()['user']['auth_token']
                    except Exception as e:
                        logger.error('error while signin')
                        token = None
                return token

            def __create_connection(self):
                logging.debug("creating websocket connection")
                self.ws = create_connection("wss://data.tradingview.com/socket.io/websocket", headers=self.__ws_headers,
                                            timeout=self.__ws_timeout)

            @staticmethod
            def __filter_raw_message(text):
                try:
                    found = re.search('"m":"(.+?)",', text).group(1)
                    found2 = re.search('"p":(.+?"}"])}', text).group(1)
                    return found, found2
                except AttributeError:
                    logger.error("error in filter_raw_message")

            @staticmethod
            def __generate_session():
                stringLength = 12
                letters = string.ascii_lowercase
                random_string = "".join(random.choice(letters) for i in range(stringLength))
                return "qs_" + random_string

            @staticmethod
            def __generate_chart_session():
                stringLength = 12
                letters = string.ascii_lowercase
                random_string = "".join(random.choice(letters) for i in range(stringLength))
                return "cs_" + random_string

            @staticmethod
            def __prepend_header(st):
                return "~m~" + str(len(st)) + "~m~" + st

            @staticmethod
            def __construct_message(func, param_list):
                return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

            def __create_message(self, func, paramList):
                return self.__prepend_header(self.__construct_message(func, paramList))

            def __send_message(self, func, args):
                m = self.__create_message(func, args)
                if self.ws_debug:
                    print(m)
                self.ws.send(m)

            @staticmethod
            def __create_df(raw_data, symbol):
                try:
                    out = re.search('"s":\[(.+?)\}\]', raw_data).group(1)
                    x = out.split(',{"')
                    data = []
                    for xi in x:
                        xi = re.split("\[|:|,|\]", xi)
                        ts = datetime.datetime.fromtimestamp(float(xi[4]))
                        row = [ts]
                        for i in range(5, 10):
                            if i == 9:
                                if len(xi) > 9:
                                    try:
                                        row.append(float(xi[i]))
                                    except ValueError:
                                        row.append(None)
                                else:
                                    row.append(None)
                            else:
                                try:
                                    row.append(float(xi[i]))
                                except ValueError:
                                    row.append(None)
                        data.append(row)
                    data = pd.DataFrame(data, columns=["datetime", "open", "high", "low", "close", "volume"]).set_index(
                        "datetime")
                    data.insert(0, "symbol", value=symbol)
                    return data
                except AttributeError:
                    logger.error("no data, please check the exchange and symbol")

            @staticmethod
            def __format_symbol(symbol, exchange, contract: int = None):
                if ":" in symbol:
                    pass
                elif contract is None:
                    symbol = f"{exchange}:{symbol}"
                elif isinstance(contract, int):
                    symbol = f"{exchange}:{symbol}{contract}!"
                else:
                    raise ValueError("not a valid contract")
                return symbol

            def get_hist(self, symbol: str, exchange: str = "NSE", interval: Interval = Interval.in_daily,
                         n_bars: int = 10, fut_contract: int = None, extended_session: bool = False) -> pd.DataFrame:
                symbol = self.__format_symbol(symbol=symbol, exchange=exchange, contract=fut_contract)
                interval = interval.value
                self.__create_connection()
                self.__send_message("set_auth_token", [self.token])
                self.__send_message("chart_create_session", [self.chart_session, ""])
                self.__send_message("quote_create_session", [self.session])
                self.__send_message("quote_set_fields", [
                    self.session, "ch", "chp", "current_session", "description", "local_description", "language",
                    "exchange", "fractional", "is_tradable", "lp", "lp_time", "minmov", "minmove2", "original_name",
                    "pricescale", "pro_name", "short_name", "type", "update_mode", "volume", "currency_code", "rchp",
                    "rtc",
                ])
                self.__send_message("quote_add_symbols", [self.session, symbol, {"flags": ["force_permission"]}])
                self.__send_message("quote_fast_symbols", [self.session, symbol])
                self.__send_message("resolve_symbol", [self.chart_session, "symbol_1",
                                                       '={"symbol":"' + symbol + '","adjustment":"splits","session":' + (
                                                           '"regular"' if not extended_session else '"extended"') + "}", ])
                self.__send_message("create_series", [self.chart_session, "s1", "s1", "symbol_1", interval, n_bars])
                self.__send_message("switch_timezone", [self.chart_session, "exchange"])

                raw_data = ""
                logger.debug(f"getting data for {symbol}...")
                while True:
                    try:
                        result = self.ws.recv()
                        raw_data = raw_data + result + "\n"
                    except Exception as e:
                        logger.error(e)
                        break

                    if "series_completed" in result:
                        break

                return self.__create_df(raw_data, symbol)


            @staticmethod
            def geter_hist(self, symbol: str, exchange: str = "NSE", interval: str = "1D", n_bars: int = 10,
                           fut_contract: int = None, extended_session: bool = False) -> pd.DataFrame:
                symbol = self.__format_symbol(symbol=symbol, exchange=exchange, contract=fut_contract)
                interval = Interval.in_1_hour
                self.__create_connection()
                self.__send_message("set_auth_token", [self.token])
                self.__send_message("chart_create_session", [self.chart_session, ""])
                self.__send_message("quote_create_session", [self.session])
                self.__send_message("quote_set_fields", [
                    self.session, "ch", "chp", "current_session", "description", "local_description", "language",
                    "exchange", "fractional", "is_tradable", "lp", "lp_time", "minmov", "minmove2", "original_name",
                    "pricescale", "pro_name", "short_name", "type", "update_mode", "volume", "currency_code", "rchp",
                    "rtc",
                ])
                self.__send_message("quote_add_symbols", [self.session, symbol, {"flags": ["force_permission"]}])
                self.__send_message("quote_fast_symbols", [self.session, symbol])
                self.__send_message("resolve_symbol", [self.chart_session, "symbol_1",
                                                       f'={{"symbol":"{symbol}","adjustment":"splits","session": {"regular" if not extended_session else "extended"}}}'])
                self.__send_message("create_series", [self.chart_session, "s1", "s1", "symbol_1", interval, n_bars])
                self.__send_message("switch_timezone", [self.chart_session, "exchange"])

                raw_data = ""
                logger.debug(f"getting data for {symbol}...")
                while True:
                    try:
                        result = self.ws.recv()
                        raw_data += result + "\n"
                    except Exception as e:
                        logger.error(e)
                        break

                    if "series_completed" in result:
                        break

                hist_data = self.__create_df(raw_data, symbol)
                if hist_data is None:
                    logger.error(f"Failed to retrieve data for {symbol}")

                return hist_data


            @staticmethod
            def calculate_rsi(hist_data, window=14):
                delta = hist_data['close'].diff()
                gain = delta.clip(lower=0)
                loss = -delta.clip(upper=0)

                avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()

                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                return rsi


            @staticmethod
            def gauss(x, h):
                return np.exp(-(x ** 2) / (2 * h ** 2))


            # Nadaraya-Watson Envelope calculation
            @staticmethod
            def nadaraya_watson_envelope(src, bandwidth, mult, repaint=True):
                n = len(src)
                coefs = np.zeros(n)
                out = np.zeros(n)
                sae = 0
                h = bandwidth

                if not repaint:
                    for i in range(n):
                        w = tv.gauss(i, h)
                        coefs[i] = w

                    den = np.sum(coefs)

                    for i in range(n):
                        out[i] = np.sum(src[:n - i] * coefs[i:n]) / den

                    mae = pd.Series(np.abs(src - out)).rolling(window=n).mean().iloc[-1] * mult
                    upper = out + mae
                    lower = out - mae
                    return upper, lower
                else:
                    sae = np.zeros(n)
                    for i in range(n):
                        sum = 0
                        sumw = 0
                        for j in range(n):
                            w = tv.gauss(i - j, h)
                            sum += src[j] * w
                            sumw += w

                        y2 = sum / sumw
                        sae[i] = y2
                    sae_mae = pd.Series(np.abs(src - sae)).rolling(window=n).mean().iloc[-1] * mult
                    upper = sae + sae_mae
                    lower = sae - sae_mae
                    return upper, lower

            @staticmethod
            def calculate_bb(rsi, length=20, mult=2.0):
                """Calculates Bollinger Bands."""
                sma = rsi.rolling(window=length).mean()
                std = rsi.rolling(window=length).std()
                upper_band = sma + (std * mult)
                lower_band = sma - (std * mult)
                return sma, upper_band, lower_band

        if __name__ == "__main__":
            logging.basicConfig(level=logging.FATAL)
            for logger_name in ['matplotlib', 'urllib3']:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.WARNING)
            pd.set_option('display.max_rows', None)
            warnings.simplefilter(action='ignore', category=FutureWarning)
            warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)
            coins = ["BTCUSDT"]

            while True:
                for symbol in coins:
                    tv = TvDatafeed()
                    exchange = "BINANCE"
                    interval = Interval.in_4_hour
                    n_bars = 3500

                    highs = []
                    lows = []
                    opens = []
                    closes = []
                    labels = []

                    hist_data = tv.get_hist(symbol, exchange, interval, n_bars)
                    timestamps = hist_data.index.tolist()  # Список меток времени

                    highs = hist_data["high"].tolist()
                    lows = hist_data["low"].tolist()
                    opens = hist_data["open"].tolist()
                    closes = hist_data["close"].tolist()
                    volume = hist_data["volume"].tolist()
                    current_price = closes[-1]

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_5_minute, n_bars)

                    rsi_dictionaries = {}
                    color = 'black'


                    def calculate_rsi(data, period=14):
                        delta = data['close'].diff()
                        gain = delta.clip(lower=0)
                        loss = -delta.clip(upper=0)

                        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
                        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                        return rsi


                    hist_data = tv.get_hist(symbol, exchange, Interval.in_4_hour, n_bars)
                    rsi = calculate_rsi(hist_data)


                    def calculate_wma(values, period):
                        weights = np.arange(1, period + 1)
                        return values.rolling(period).apply(lambda prices: np.dot(prices, weights) / weights.sum(),
                                                            raw=True)


                    def calculate_hma(data, period=14):
                        half_length = int(period / 2)
                        sqrt_length = int(np.sqrt(period))

                        wma_half_length = calculate_wma(data, half_length)
                        wma_full_length = calculate_wma(data, period)
                        hma = (calculate_wma(2 * wma_half_length - wma_full_length, sqrt_length))
                        return hma


                    HMA_RSI = calculate_hma(rsi)
                    formation_points = []

                    for entry_idx in range(len(hist_data) - 5):
                        if entry_idx + 5 < len(hist_data):
                            entry_close = hist_data.iloc[entry_idx]['close']
                            next_close = hist_data.iloc[entry_idx + 1]['close']
                            next_open = hist_data.iloc[entry_idx + 1]['open']
                            next_low = hist_data.iloc[entry_idx + 1]['low']

                            # Условие для входа
                            if (next_close > entry_close and
                                    (next_open - next_low) <= 3 * (entry_close - next_low) and
                                    all(hist_data.iloc[entry_idx + i]['low'] >= next_low for i in
                                        range(2, 5)) and
                                    (hist_data.iloc[entry_idx + 5]['close'] - hist_data.iloc[entry_idx + 5][
                                        'open']) >= 2 * (entry_close - next_low)):
                                formation_points.append(entry_idx + 1)


                    def find_local_extrema_with_averages(rsi_values: np.ndarray):
                        local_maxima = []
                        local_minima = []
                        maxima_context = []
                        minima_context = []
                        local_maxima_value = []
                        local_minima_value = []

                        for i in range(2, len(rsi_values) - 2):
                            # Локальный максимум
                            if rsi_values[i] > rsi_values[i - 1] and rsi_values[i] > rsi_values[i - 2] and \
                                    rsi_values[i] > rsi_values[i + 1] and rsi_values[i] > rsi_values[i + 2]:
                                local_maxima.append(i)
                                local_maxima_value.append(rsi_values[i])
                                average_maxima = np.mean(rsi_values[i - 2:i + 2])
                                maxima_context.append((i, average_maxima))

                            # Локальный минимум
                            if rsi_values[i] < rsi_values[i - 1] and rsi_values[i] < rsi_values[i - 2] and \
                                    rsi_values[i] < rsi_values[i + 1] and rsi_values[i] < rsi_values[i + 2]:
                                local_minima.append(i)
                                local_minima_value.append(rsi_values[i])
                                average_minima = np.mean(rsi_values[i - 2:i + 2])
                                minima_context.append((i, average_minima))

                        return local_maxima, local_minima, maxima_context, minima_context, local_maxima_value, local_minima_value


                    local_maxima, local_minima, maxima_context, minima_context, local_maxima_value, local_minima_value = find_local_extrema_with_averages(
                        rsi)


                    def calculate_weighted_minima(rsi_values, weight_below_30, weight_30_40, weight_above_40):
                        """Рассчитываем взвешенные значения для minima_context на основе переданных весов."""
                        weighted_minima = []

                        for idx, avg_value in minima_context:
                            if avg_value > 50:
                                continue  # Пропускаем значения больше 50

                            if 40 <= avg_value <= 50:
                                weight = weight_above_40
                            elif 30 <= avg_value < 40:
                                weight = weight_30_40
                            elif 20 <= avg_value < 30:
                                weight = weight_below_30
                            else:
                                weight = 0

                            weighted_minima.append((idx, weight * avg_value))

                        return weighted_minima


                    def calculate_weighted_maxima(rsi_values, weight_above_70, weight_60_70, weight_below_60):
                        """Рассчитываем взвешенные значения для maxima_context на основе переданных весов."""
                        weighted_maxima = []

                        for idx, avg_value in maxima_context:
                            if avg_value < 60:
                                continue  # Пропускаем значения меньше 60

                            if 60 <= avg_value <= 70:
                                weight = weight_60_70
                            elif 70 <= avg_value < 80:
                                weight = weight_above_70
                            else:
                                continue

                            weighted_maxima.append((idx, weight * avg_value))

                        return weighted_maxima


                    def interpolate_line(indexes, values, total_length):
                        """Функция для интерполяции линии между точками."""
                        interpolated_values = np.zeros(total_length)

                        # Применение интерполяции между значениями
                        for i in range(1, len(indexes)):
                            start_idx = indexes[i - 1]
                            end_idx = indexes[i]
                            interpolated_values[start_idx:end_idx] = np.linspace(values[i - 1], values[i],
                                                                                 end_idx - start_idx)

                        interpolated_values[end_idx:] = values[-1]  # Заполнение остатка

                        return interpolated_values


                    def mse_loss(weights):
                        """Функция потерь для минимизации MSE."""
                        weight_below_30, weight_30_40, weight_above_40 = weights

                        weighted_minima = calculate_weighted_minima(rsi.values, weight_below_30, weight_30_40,
                                                                    weight_above_40)
                        minima_indices, minima_values = zip(*weighted_minima)

                        weighted_minima_line = interpolate_line(minima_indices, minima_values, len(rsi))

                        minima_indices = [idx for idx, _ in minima_context]  # Только индексы
                        # MSE для точек ниже 30
                        mse_below_30 = np.mean(
                            (rsi.values[minima_indices] - weighted_minima_line[minima_indices]) ** 2)

                        # Инвертированный MSE для точек выше 40 (чтобы отдалить линию от них)
                        mse_above_40 = np.mean(
                            (weighted_minima_line[minima_indices] - rsi.values[minima_indices]) ** 2)

                        # Комбинируем потери, учитывая требования
                        total_mse = mse_below_30 + mse_above_40
                        return total_mse


                    def mse_loss_maxima(weights):
                        """Функция потерь для минимизации MSE по точкам максимума."""
                        weight_above_70, weight_60_70, weight_below_60 = weights

                        weighted_maxima = calculate_weighted_maxima(rsi.values, weight_above_70, weight_60_70,
                                                                    weight_below_60)
                        maxima_indices, maxima_values = zip(*weighted_maxima)

                        weighted_maxima_line = interpolate_line(maxima_indices, maxima_values, len(rsi))

                        maxima_indices = [idx for idx, _ in maxima_context]  # Только индексы
                        # MSE для точек выше 70
                        mse_above_70 = np.mean(
                            (rsi.values[maxima_indices] - weighted_maxima_line[maxima_indices]) ** 2)

                        # Инвертированный MSE для точек ниже 60 (чтобы отдалить линию от них)
                        mse_below_60 = np.mean(
                            (weighted_maxima_line[maxima_indices] - rsi.values[maxima_indices]) ** 2)

                        # Комбинируем потери, учитывая требования
                        total_mse = mse_above_70 + mse_below_60
                        return total_mse


                    def optimize_weights():
                        """Оптимизация весов для лучшего соответствия линии."""
                        initial_guess = [1.5, 1.0, 0.5]

                        result = minimize(mse_loss, initial_guess, method='Nelder-Mead')

                        if result.success:
                            optimal_weights = result.x
                            return 2 - optimal_weights
                        else:
                            raise ValueError("Оптимизация не удалась")


                    def optimize_weights_maxima():
                        """Оптимизация весов для лучшего соответствия линии по точкам максимума."""
                        initial_guess = [1.5, 1.0, 0.5]

                        result = minimize(mse_loss_maxima, initial_guess, method='Nelder-Mead')

                        if result.success:
                            optimal_weights = result.x
                            return 2 - optimal_weights
                        else:
                            raise ValueError("Оптимизация не удалась")


                    # Оптимизация весов
                    optimal_weights = optimize_weights()

                    print(f"Optimal Weights: {optimal_weights}")

                    # Используем оптимальные веса для расчета взвешенной линии
                    final_weighted_minima = calculate_weighted_minima(rsi.values, *optimal_weights)
                    minima_indices, minima_values = zip(*final_weighted_minima)
                    final_weighted_minima_line = interpolate_line(minima_indices, minima_values, len(rsi))

                    optimal_weights_maxima = optimize_weights_maxima()

                    print(f"Optimal Weights for Maxima Context: {optimal_weights_maxima}")

                    # Используем оптимальные веса для расчета взвешенной линии
                    final_weighted_maxima = calculate_weighted_maxima(rsi.values, *optimal_weights_maxima)
                    maxima_indices, maxima_values = zip(*final_weighted_maxima)
                    final_weighted_maxima_line = interpolate_line(maxima_indices, maxima_values, len(rsi))


                    def optimize_coefficient(hma_values, rsi_values, local_minima, min_coeff=0.1, max_coeff=2.0,
                                             step=0.01):
                        best_coeff = None
                        min_error = float('inf')

                        total_combinations = int((max_coeff - min_coeff) / step)
                        current_combination = 0

                        for coeff in np.arange(min_coeff, max_coeff, step):
                            adjusted_hma = hma_values * coeff
                            error = np.mean(np.abs(adjusted_hma.iloc[local_minima] - rsi_values.iloc[local_minima]))

                            if error < min_error:
                                min_error = error
                                best_coeff = coeff

                            # Обновляем прогресс
                            current_combination += 1
                            progress = (current_combination / total_combinations) * 100
                            print(f"Progress: {progress:.2f}%")

                        return best_coeff, min_error


                    def optimize_coefficient_2(hma_values, rsi_values, local_maxima, min_coeff=0.1, max_coeff=4.0,
                                               step=0.01):
                        best_coeff = None
                        min_error = float('inf')

                        total_combinations = int((max_coeff - min_coeff) / step)
                        current_combination = 0

                        for coeff in np.arange(min_coeff, max_coeff, step):
                            adjusted_hma = hma_values * coeff
                            error = np.mean(np.abs(adjusted_hma.iloc[local_maxima] - rsi_values.iloc[local_maxima]))

                            if error < min_error:
                                min_error = error
                                best_coeff = coeff

                            # Обновляем прогресс
                            current_combination += 1
                            progress = (current_combination / total_combinations) * 100
                            print(f"Progress: {progress:.2f}%")

                        return best_coeff, min_error


                    # Оптимизация коэффициента
                    best_coeff, min_error = optimize_coefficient(HMA_RSI, rsi, local_minima)
                    adjusted_HMA_RSI_minima = HMA_RSI * best_coeff

                    best_coeff_maxima, min_error_maxima = optimize_coefficient_2(HMA_RSI, rsi,
                                                                                 local_maxima)
                    adjusted_HMA_RSI_maxima = HMA_RSI * best_coeff_maxima

                    print(f'Лучший коэффициент: {best_coeff}')
                    print(f'Минимальная ошибка: {min_error}')
                    print(local_minima)

                    print(f'Лучший коэффициент для максимумов: {best_coeff_maxima}')
                    print(f'Минимальная ошибка для максимумов: {min_error_maxima}')

                    bandwidth = 8.0
                    mult = 2.0
                    rsi_values = list(rsi.values)
                    upper, lower = tv.nadaraya_watson_envelope(rsi_values[1:], bandwidth, mult, repaint=True)
                    ema_l = []
                    ema_h = []
                    for i in range(len(local_minima_value)):
                        if i > 1:
                            emas = (local_minima_value[i] * (2/50)) + (ema_l[i-1] * (1 - (2/50)))
                            ema_l.append(emas)
                        else:
                            ema_l.append((local_minima_value[i] * sqrt(2)) / 2)

                    for i in range(len(local_maxima_value)):
                        if i > 1:
                            emas = (local_maxima_value[i] * (2/50)) + (ema_h[i-1] * (1 - (2/50)))
                            ema_h.append(emas)
                        else:
                            ema_h.append(local_maxima_value[i])

                    emall = []
                    emahh = []
                    print(ema_l)
                    for i in ema_l:
                        i = (i * sqrt(2)) / 2
                        emall.append(i)
                    for i in ema_h:
                        i = (i / sqrt(2)) * 1.7
                        emahh.append(i)
                    sma, upper_band, lower_band = tv.calculate_bb(rsi)


                    def save_signal_to_json(signal_type, index, rsi_value, json_file='signals.json'):
                        signal = {
                            "signal_type": signal_type,
                            "index": index,
                            "rsi_value": rsi_value
                        }

                        # Сохраняем только последний сигнал, перезаписывая существующий
                        with open(json_file, 'w') as f:
                            json.dump([signal], f, indent=4)


                    # Логика для определения сигналов и их сохранения
                    for i in range(1, len(upper)):
                        if adjusted_HMA_RSI_minima[i] > upper[i] and adjusted_HMA_RSI_maxima[i] > upper[i] and \
                                rsi_values[i] > upper[i]:
                            save_signal_to_json("short", i, rsi.iloc[i])

                        if adjusted_HMA_RSI_minima[i] < lower[i] and adjusted_HMA_RSI_maxima[i] < lower[i] and \
                                rsi_values[i] < lower[i]:
                            save_signal_to_json("long", i, rsi.iloc[i])


                    def save_nw_signal_to_json(signal_type, json_file='signals_nw.json'):
                        signal = {
                            "signal_type": signal_type,
                        }

                        # Сохраняем только последний сигнал, перезаписывая существующий
                        with open(json_file, 'w') as f:
                            json.dump([signal], f, indent=4)


                    # Логика для определения сигналов и их сохранения
                    if upper[-1] > emahh[-1]:
                        save_nw_signal_to_json("long")
                    if lower[-1] < emall[-1]:
                        save_nw_signal_to_json("short")

                    fig = make_subplots(rows=1, cols=1)

                    # Отображение RSI
                    fig.add_trace(go.Scatter(x=hist_data.index, y=rsi, mode='lines', name='RSI'))

                    # Отображение HMA на основе RSI
                    fig.add_trace(go.Scatter(x=hist_data.index, y=adjusted_HMA_RSI_minima, mode='lines', name='HMA_RSI',
                                             line=dict(color='green')))

                    fig.add_trace(go.Scatter(x=hist_data.index, y=adjusted_HMA_RSI_maxima, mode='lines',
                                             name='Adjusted HMA_RSI Maxima', line=dict(color='red')))

                    fig.add_trace(go.Scatter(
                        x=hist_data.index,
                        y=upper,
                        mode='lines',
                        line=dict(color='purple'),
                        name='Optimized Weighted Minima Line'
                    ))

                    fig.add_trace(go.Scatter(
                        x=hist_data.index,
                        y=lower, mode='lines',
                        name='Weighted Maxima Line',
                        line=dict(color='purple')
                    ))

                    fig.add_trace(go.Scatter(
                        x=hist_data.index[local_minima],
                        y=emall,  # Используем "опущенные" значения ema
                        mode='lines',
                        name='Weighted Maxima Line',
                        line=dict(color='black')
                    ))

                    fig.add_trace(go.Scatter(
                        x=hist_data.index[local_maxima],
                        y=emahh,  # Используем "опущенные" значения ema
                        mode='lines',
                        name='Weighted Maxima Line',
                        line=dict(color='black')
                    ))

                    fig.add_trace(go.Scatter(
                        x=hist_data.index[local_maxima],
                        y=rsi.iloc[local_maxima],
                        mode='markers',
                        marker=dict(color='green', size=10),
                        name='Local Maxima'
                    ))

                    # Отображение локальных минимумов на RSI
                    fig.add_trace(go.Scatter(
                        x=hist_data.index[local_minima],
                        y=rsi.iloc[local_minima],
                        mode='markers',
                        marker=dict(color='red', size=10),
                        name='Local Minima'
                    ))

                    fig.add_trace(go.Scatter(x=hist_data.index[formation_points], y=rsi.iloc[formation_points], mode='markers',
                                             marker=dict(color='blue', size=10), name='Formation Points'))

                    # Настройка графика
                    fig.update_layout(title='RSI and Hull Moving Average (HMA) on RSI', xaxis_title='Date',
                                      yaxis_title='Value')

                    # fig.show()

                    del hist_data, timestamps, highs, lows, opens, closes, volume, current_price

                    # Force garbage collection
                    gc.collect()
                break

        gc.collect()

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print(f"Тип ошибки: {exc_type}")
        print(f"Строка № {exc_tb.tb_lineno}")
        print("Перезапуск кода...")
        time.sleep(5)