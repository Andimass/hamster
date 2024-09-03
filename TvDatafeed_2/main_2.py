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

logger = logging.getLogger(__name__)

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
            def update_prices(highs, lows, bar_indices, ax):
                high_prices_arr = [highs[0]] * 10
                high_indexs_arr = [bar_indices[0]] * 10
                low_prices_arr = [lows[0]] * 10
                low_indexs_arr = [bar_indices[0]] * 10
                high_ = False
                low_ = False
                sw_high_price = None
                sw_high_index = None
                sw_low_price = None
                sw_low_index = None
                prew_high_price = None
                prew_high_index = None
                prew_low_price = None
                prew_low_index = None
                bull_bos = False
                bear_bos = False
                l_h_line = None
                h_l_line = None
                hh = []
                hl = []
                ll = []
                lh = []
                bull_bos_ends = []
                bear_bos_ends = []

                def plot_label(x, y, text, color, y_offset=0):
                    ax.text(x, y, text, fontsize=8, color=color, ha='center', va='center')

                def plot_line(start_idx, start_price, end_idx, end_price, color):
                    return ax.plot([start_idx, end_idx], [start_price, end_price], color=color, linestyle='-')

                def delete_line(line):
                    if line:
                        line[0].remove()

                for i in range(4, len(highs)):
                    if highs[i - 2] >= highs[i - 1] and highs[i - 2] >= highs[i - 3] and highs[i - 2] >= highs[i] and \
                            highs[
                                i - 2] >= highs[i - 4]:
                        high_prices_arr.append(highs[i - 2])
                        high_indexs_arr.append(bar_indices[i - 2])
                        if high_ and (
                                low_prices_arr and min(low_prices_arr) < sw_low_price or highs[i - 2] > sw_high_price):
                            if low_prices_arr:
                                prew_low_price = sw_low_price
                                prew_low_index = sw_low_index
                                u = 0
                                for r in range(len(low_prices_arr)):
                                    if sw_high_index > low_indexs_arr[r]:
                                        u += 1
                                slice_low_indexs_arr = low_indexs_arr[u:]
                                slice_low_prices_arr = low_prices_arr[u:]
                                for j in range(len(slice_low_prices_arr)):
                                    if slice_low_prices_arr[j] == min(slice_low_prices_arr) and sw_high_price > min(
                                            slice_low_prices_arr):
                                        sw_low_index = slice_low_indexs_arr[j]
                                if sw_high_price > min(slice_low_prices_arr):
                                    sw_low_price = min(slice_low_prices_arr)
                                    low_prices_arr.clear()
                                    low_indexs_arr.clear()
                                h_l_line = plot_line(sw_high_index, sw_high_price, sw_low_index, sw_low_price, 'purple')
                                high_ = False
                                low_ = True
                                if sw_high_price >= prew_high_price:
                                    plot_label(sw_high_index, sw_high_price, "HH", 'blue', y_offset=5)
                                    hh.append(sw_high_index)  # Append HH index
                                if sw_high_price <= prew_high_price:
                                    plot_label(sw_high_index, sw_high_price, "LH", 'red', y_offset=5)
                                    lh.append(sw_high_index)
                        if sw_high_price is None:
                            sw_high_price = highs[i - 2]
                            sw_high_index = bar_indices[i - 2]
                            prew_high_price = sw_high_price
                            prew_high_index = sw_high_index
                            low_prices_arr.clear()
                            low_indexs_arr.clear()
                            high_ = True

                    if lows[i - 2] <= lows[i - 1] and lows[i - 2] <= lows[i - 3] and lows[i - 2] <= lows[i] and lows[
                        i - 2] <= \
                            lows[i - 4]:
                        low_prices_arr.append(lows[i - 2])
                        low_indexs_arr.append(bar_indices[i - 2])
                        if low_ and (
                                high_prices_arr and max(high_prices_arr) > sw_high_price or lows[i - 2] < sw_low_price):
                            if high_prices_arr:
                                prew_high_price = sw_high_price
                                prew_high_index = sw_high_index
                                u = 0
                                for r in range(len(high_indexs_arr)):
                                    if sw_low_index > high_indexs_arr[r]:
                                        u += 1
                                slice_high_indexs_arr = high_indexs_arr[u:]
                                slice_high_prices_arr = high_prices_arr[u:]
                                for j in range(len(slice_high_prices_arr)):
                                    if slice_high_prices_arr[j] == max(slice_high_prices_arr) and sw_low_price < max(
                                            slice_high_prices_arr):
                                        sw_high_index = slice_high_indexs_arr[j]
                                if sw_low_price < max(slice_high_prices_arr):
                                    sw_high_price = max(slice_high_prices_arr)
                                    high_prices_arr.clear()
                                    high_indexs_arr.clear()
                                if l_h_line and sw_high_price > prew_high_price:
                                    delete_line(l_h_line)
                                l_h_line = plot_line(sw_low_index, sw_low_price, sw_high_index, sw_high_price, 'purple')
                                low_ = False
                                high_ = True
                                if sw_low_price >= prew_low_price:
                                    plot_label(sw_low_index, sw_low_price, "HL", 'blue', y_offset=-5)
                                    hl.append(sw_low_index)  # Append HL index
                                if sw_low_price <= prew_low_price:
                                    plot_label(sw_low_index, sw_low_price, "LL", 'red', y_offset=-5)
                                    ll.append(sw_low_index)  # Append HL index
                        if sw_low_price is None:
                            sw_low_price = lows[i - 2]
                            sw_low_index = bar_indices[i - 2]
                            prew_low_price = sw_low_price
                            prew_low_index = sw_low_index
                            high_prices_arr.clear()
                            high_indexs_arr.clear()
                            low_ = True

                    if sw_high_price is not None and highs[i] > sw_high_price:
                        if not bull_bos:
                            bull_bos = True
                            bear_bos = False
                            ax.plot([sw_high_index, bar_indices[i]], [sw_high_price, sw_high_price], color='g',
                                    linestyle='-')
                            bull_bos_ends.append(bar_indices[i])

                    if sw_low_price is not None and lows[i] < sw_low_price:
                        if not bear_bos:
                            bear_bos = True
                            bull_bos = False
                            ax.plot([sw_low_index, bar_indices[i]], [sw_low_price, sw_low_price], color='r',
                                    linestyle='-')
                            bear_bos_ends.append(bar_indices[i])

                return hh, hl, lh, ll, bull_bos_ends, bear_bos_ends

            @staticmethod
            def calculate_average(highs, lows, hh, hl):
                if hh is None or hl is None:
                    return "Один из индексов имеет значение None, проверьте данные."

                if hh < len(highs) and hl < len(lows):
                    average_value = (highs[hh] + lows[hl]) / 2
                    return average_value
                else:
                    return "Индексы выходят за пределы данных."

            @staticmethod
            def find_nearest(array, value):
                """ Возвращает индекс ближайшего значения в массиве к заданному значению. """
                array = np.asarray(array)
                idx = (np.abs(array - value)).argmin()
                return idx

            @staticmethod
            def find_nearest_from_indices(index, indices_lists, direction='before'):
                """ Находит ближайший индекс из списка списков индексов до (before) или после (after) заданного индекса. """
                nearest = None
                nearest_new = print()
                nearest_distance = float('inf')

                for indices in indices_lists:
                    for idx in indices:
                        if (direction == 'before' and idx < index) or (direction == 'after' and idx > index):
                            distance = abs(index - idx)
                            if distance < nearest_distance:
                                nearest = idx
                                nearest_distance = distance
                return nearest

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
            def calculate_sma(hist_data, window=14):
                return hist_data['close'].rolling(window=window).mean()

            @staticmethod
            def plot_rsi_and_sma(hist_data, rsi, sma):



                # График RSI
                # ax2.plot(hist_data.index, rsi, label='RSI', color='purple')
                # ax2.axhline(70, linestyle='--', color='red', label='Overbought (70)')
                # ax2.axhline(30, linestyle='--', color='green', label='Oversold (30)')
                # ax2.set_title('RSI')
                # ax2.legend()

                # Аннотация последнего значения RSI
                last_rsi_value = rsi.iloc[-1]
                last_date = rsi.index[-1]  # Используем индекс DataFrame для последней даты
                # ax2.annotate(f'{last_rsi_value:.2f}', xy=(last_date, last_rsi_value),
                #              xytext=(10, 0), textcoords='offset points',
                #              horizontalalignment='right', verticalalignment='center',
                #              color='purple', fontsize=10, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="b", lw=1))
                #
                # plt.tight_layout()
                # plt.show()

            @staticmethod
            def calculate_mfi(hist_data, length=14):
                # Ensure that 'high', 'low', 'close', and 'volume' are all in the DataFrame
                if not {'high', 'low', 'close', 'volume'}.issubset(hist_data.columns):
                    raise ValueError("hist_data must include 'high', 'low', 'close', and 'volume' columns")

                # Compute typical price
                hist_data['typical_price'] = (hist_data['high'] + hist_data['low'] + hist_data['close']) / 3

                # Compute raw money flow
                hist_data['raw_money_flow'] = hist_data['typical_price'] * hist_data['volume']

                # Compute positive and negative money flows using shift for comparison
                hist_data['positive_flow'] = np.where(hist_data['typical_price'] > hist_data['typical_price'].shift(1),
                                                      hist_data['raw_money_flow'], 0)
                hist_data['negative_flow'] = np.where(hist_data['typical_price'] < hist_data['typical_price'].shift(1),
                                                      hist_data['raw_money_flow'], 0)

                # Convert positive and negative flows to Series for rolling operation
                positive_mf = pd.Series(hist_data['positive_flow']).rolling(window=length).sum()
                negative_mf = pd.Series(hist_data['negative_flow']).rolling(window=length).sum()

                # Compute money flow ratio
                money_flow_ratio = positive_mf / negative_mf

                # Compute MFI
                hist_data['MFI'] = 100 - (100 / (1 + money_flow_ratio))

                return hist_data
            @staticmethod
            def plot_mfi_over_timeframes(timeframes, symbol, exchange, n_bars, tv):
                fig, ax = plt.subplots(figsize=(12, 8))
                mfi_dictionaries = {}
                colors = ['red', 'blue', 'green', 'purple']  # Цвета для различных таймфреймов

                for timeframe, color in zip(timeframes, colors):
                    hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                    if not hist_data.empty:
                        hist_data_with_mfi = TvDatafeed.calculate_mfi(hist_data)
                        # ax.plot(hist_data_with_mfi.index, hist_data_with_mfi['MFI'], label=f'MFI {timeframe}',
                        #         color=color)
                        mfi_dictionaries[timeframe] = hist_data_with_mfi['MFI'].iloc[-1]  # Сохраняем последнее значение MFI

                # ax.set_title('MFI Comparison Across Different Timeframes')
                # ax.legend()
                # plt.show()
                return mfi_dictionaries

            # Добавление функциональности сравнения
            @staticmethod
            def compare_mfi_values(mfi_values):
                timeframes_order = [Interval.in_15_minute, Interval.in_30_minute, Interval.in_1_hour,
                                    Interval.in_2_hour]
                timeframe_labels = {
                    Interval.in_15_minute: "15m",
                    Interval.in_30_minute: "30m",
                    Interval.in_1_hour: "1h",
                    Interval.in_2_hour: "2h"
                }
                comparisons = {}
                for i in range(len(timeframes_order) - 1):
                    first_timeframe = timeframes_order[i]
                    second_timeframe = timeframes_order[i + 1]
                    key = f"{timeframe_labels[first_timeframe]} > {timeframe_labels[second_timeframe]}"
                    comparisons[key] = mfi_values[first_timeframe] > mfi_values[second_timeframe]
                return comparisons


            @staticmethod
            def calculate_macd(hist_data, fast_length=12, slow_length=26, signal_length=9):
                """Рассчитывает значения MACD."""
                if 'close' not in hist_data.columns:
                    raise ValueError("DataFrame must contain 'close' column")
                fast_ema = hist_data['close'].ewm(span=fast_length, adjust=False).mean()
                slow_ema = hist_data['close'].ewm(span=slow_length, adjust=False).mean()
                macd = fast_ema - slow_ema
                signal = macd.ewm(span=signal_length, adjust=False).mean()
                hist = macd - signal
                return macd, signal, hist


            @staticmethod
            def plot_macd(hist_data, macd, signal, hist):

                # Получаем последние дату и значения для MACD и сигнала
                last_date = hist_data.index[-1]
                last_macd = macd.iloc[-1]
                last_signal = signal.iloc[-1]

                # plt.show()

            @staticmethod
            def ifisher(src, length):
                src = pd.Series(src)  # Convert to Series
                hi = src.rolling(window=length).max()
                lo = src.rolling(window=length).min()
                value0 = 0.0
                ifisher_vals = []
                for i in range(len(src)):
                    if i == 0:
                        value0 = 0.0
                    else:
                        value0 = 0.66 * ((src.iloc[i] - lo.iloc[i]) / max(hi.iloc[i] - lo.iloc[i],
                                                                          0.001) - 0.5) + 0.67 * value0
                    value1 = min(0.999, max(-0.999, value0))
                    ifisher_val = 0.5 * np.log((1 + value1) / max(1 - value1, 0.001)) + 0.5 * ifisher_vals[
                        -1] if ifisher_vals else 0
                    ifisher_vals.append(ifisher_val)
                return np.array(ifisher_vals)

            @staticmethod
            def normalize(src, length):
                src = pd.Series(src)  # Convert to Series
                hi = src.rolling(window=length).max()
                lo = src.rolling(window=length).min()
                return (src - lo) / (hi - lo)

            @staticmethod
            def aroon(highs, lows, length):
                highs = pd.Series(highs)  # Convert to Series
                lows = pd.Series(lows)  # Convert to Series
                highest_high = highs.rolling(window=length + 1).apply(lambda x: np.argmax(x[::-1]), raw=True)
                lowest_low = lows.rolling(window=length + 1).apply(lambda x: np.argmin(x[::-1]), raw=True)
                upper = 100 * (highest_high + length) / length
                lower = 100 * (lowest_low + length) / length
                return upper, lower

            @staticmethod
            def calculate_aroon_indicator(highs, lows, p, indicator_type):
                upper, lower = TvDatafeed.aroon(highs, lows, p)
                if indicator_type == "Original Aroon":
                    aup = upper
                    adn = lower
                elif indicator_type == "Binarized Aroon":
                    aup = TvDatafeed.normalize(TvDatafeed.ifisher(upper, p), 2)
                    adn = TvDatafeed.normalize(TvDatafeed.ifisher(lower, p), 2)
                elif indicator_type == "Smoothed Aroon":
                    aup = TvDatafeed.normalize(TvDatafeed.ifisher(upper, p), 100)
                    adn = TvDatafeed.normalize(TvDatafeed.ifisher(lower, p), 100)
                elif indicator_type == "Differenced Aroon":
                    aup = upper - lower
                    adn = None
                else:
                    raise ValueError(f"Unknown indicator type: {indicator_type}")
                return aup, adn

            @staticmethod
            def plot_aroon(timestamps, aup, adn, symbol):
                return None
                # plt.figure(figsize=(50, 25))
                # plt.title(f'Aroon Indicator for {symbol}', fontsize=20)
                #
                # plt.plot(timestamps, aup, label='Aroon Up', color='blue')
                # if adn is not None:
                #     plt.plot(timestamps, adn, label='Aroon Down', color='red')
                #
                # plt.text(timestamps[-1], aup[-1], f'{aup[-1]:.2f}', color='blue', fontsize=12)
                # if adn is not None:
                #     plt.text(timestamps[-1], adn[-1], f'{adn[-1]:.2f}', color='red', fontsize=12)

                # plt.xlabel('Date')
                # plt.ylabel('Aroon Value')
                # plt.legend()
                # plt.grid(True)
                # plt.show()

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
            def calculate_st(hist_data, k_length=14, k_smoothing=1, d_smoothing=3):
                """Calculates the Stochastic Oscillator values."""
                L = hist_data['low'].rolling(window=k_length).min()
                H = hist_data['high'].rolling(window=k_length).max()
                k = 100 * ((hist_data['close'] - L) / (H - L))
                k_smooth = k.rolling(window=k_smoothing).mean()
                d = k_smooth.rolling(window=d_smoothing).mean()
                return k_smooth, d

            @staticmethod
            def plot_st(hist_data, k):


                # Get the last date and values for %K and %D
                last_date = hist_data.index[-1]
                last_k = k.iloc[-1]

                # plt.text(last_date, last_k, f'{last_k:.2f}', color='#2962FF', verticalalignment='center',
                #          horizontalalignment='right')
                # plt.text(last_date, last_d, f'{last_d:.2f}', color='#FF6D00', verticalalignment='center',
                #          horizontalalignment='right')
                #
                # plt.title('Stochastic Oscillator')
                # plt.legend()
                # plt.show()

            @staticmethod
            def calculate_bb(hist_data, length=20, mult=2.0):
                """Calculates Bollinger Bands."""
                sma = hist_data['close'].rolling(window=length).mean()
                std = hist_data['close'].rolling(window=length).std()
                upper_band = sma + (std * mult)
                lower_band = sma - (std * mult)
                return sma, upper_band, lower_band

            @staticmethod
            def plot_bb(hist_data, sma, upper_band, lower_band):

                # Get the last date and values for SMA, upper_band and lower_band
                last_date = hist_data.index[-1]
                last_sma = sma.iloc[-1]
                last_upper = upper_band.iloc[-1]
                last_lower = lower_band.iloc[-1]
                # plt.show()

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

            # Plotting function
            @staticmethod
            def plot_nwe(timestamps, src, upper, lower, labels, symbol):
                plt.figure(figsize=(24, 14))
                plt.plot(timestamps, src, label='Close Price', color='black')
                plt.plot(timestamps, upper, label='Upper Band', color='teal')
                plt.plot(timestamps, lower, label='Lower Band', color='red')

                for label in labels:
                    plt.annotate(label['text'], (label['x'], label['y']), textcoords="offset points", xytext=(0, 10),
                                 ha='center')

                # Annotate last values
                plt.annotate(f'Upper: {upper[-1]:.2f}', (timestamps[-1], upper[-1]), textcoords="offset points",
                             xytext=(0, 10), ha='center', color='teal')
                plt.annotate(f'Lower: {lower[-1]:.2f}', (timestamps[-1], lower[-1]), textcoords="offset points",
                             xytext=(0, -15), ha='center', color='red')

                plt.title(f'Nadaraya-Watson Envelope for {symbol}')
                plt.legend()
                # plt.show()

            @staticmethod
            def rbf_kernel(x1: np.array = np.array([]), x2: np.array = np.array([]), sigma_f: float = 1,
                           length: int = 1):
                """
                One-dimnensional Gaussian RBF kernel, the go-to choice.
                """
                # sigma_f is not in use yet
                return float(sigma_f * np.exp(-(np.linalg.norm(x1 - x2) ** 2) / (2 * length ** 2)))

            # Helper function to calculate the respective covariance matrices
            @staticmethod
            def cov_matrix(x1, x2, cov_function, length) -> np.array:
                return np.array([[cov_function(a, b, 1, length) for a in x1] for b in x2])

            def calculate_gpr(self, hist_data: pd.DataFrame, n_of_observations: int, forecast_length: int) -> tuple[
                np.ndarray, np.ndarray]:
                """
                The Gaussian process regression itself.

                Parameters
                ----------
                `hist_data`:         training data
                `n_of_observations`: number of observations (bars) to get processed
                `forecast_length`:   length of forecast (bars)
                """
                # TODO: store calculated values that are being used multiple times for efficiency

                x_train = list(range(n_of_observations))

                # centering the price data (subtracting simple moving average values)
                sma = tv.calculate_sma(hist_data[-n_of_observations:], n_of_observations).values[-1]
                y_train = hist_data["close"].tail(n_of_observations) - sma

                # makeshift solution for hopefully only cutoff cases
                if len(y_train) != len(x_train):
                    x_train = list(range(len(y_train)))

                x_test = x_train + [x_train[-1] + i + 1 for i in range(forecast_length)]

                # Store the inverse of covariance matrix of input (+ machine epsilon on diagonal) since it is needed for every prediction
                _K_inv = np.linalg.inv(
                    self.cov_matrix(x_train, x_train, self.rbf_kernel, 20) + 0.0001 * np.identity(len(x_train)))
                K_s_T = self.cov_matrix(x_train, x_test, self.rbf_kernel, 20)
                K_ss = self.cov_matrix(x_test, x_test, self.rbf_kernel, 20)

                # Mean with adjustemnt
                mean = K_s_T.dot(_K_inv.T).dot(y_train)
                mean += sma

                # Covariance matrix
                cov_m = K_ss - K_s_T.dot(_K_inv).dot(K_s_T.T)

                # Adding value larger than machine epsilon to ensure positive semi definite
                # unnecessary, at least for now.
                # cov_m = cov_m + 3e-7 * np.ones(np.shape(cov_m[0]))

                # Variance
                var = np.diag(cov_m)

                return mean, var

            @staticmethod
            def get_gpr_predictions(pred_window: int, timeframes: list[str], n_of_observations: int, symbol: str,
                                    exchange: str, cutoff_timestamp: pd.Timestamp = None) -> dict[
                str, list[float, pd.Timestamp, int]]:
                """
                Getting GP regressor predictions on given `timeframes`.

                Parameters
                ----------
                pred_window : int
                    Number of minutes for which the prediction is desired.
                timeframes : list[str], optional
                    List of strings representing the timeframes on which to make the predictions.
                hist_data : pd.DataFrame
                    Training data for GPR.
                n_of_observations : int
                    Number of observations to get processed.
                cutoff_time : pd.Timestamp, optional
                    Timestamp at which to cut the data, leaving points less or equal to the timestamp.

                Returns
                -------
                dict[str, list[float, pd.Timestamp, int]]
                    A dictionary with names of timeframes and corresponding nested dicts of predictions, their time and bool values.

                    Bool values depend on condition if predicted value is bigger (1) or not (0) than last close price on the timeframe.
                """
                predictions = {}

                for str_tf in timeframes:
                    # getting appropriate timeframe hist_data's
                    match str_tf:
                        case "1":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_1_minute, n_of_observations,
                                                    cutoff_timestamp)
                        case "3":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_3_minute, n_of_observations,
                                                    cutoff_timestamp)
                        case "5":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_5_minute, n_of_observations,
                                                    cutoff_timestamp)
                        case "15":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_15_minute, n_of_observations,
                                                    cutoff_timestamp)
                        case "30":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_30_minute, n_of_observations,
                                                    cutoff_timestamp)
                        case "45":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_45_minute, n_of_observations,
                                                    cutoff_timestamp)
                        case "1H":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_of_observations,
                                                    cutoff_timestamp)
                        case "2H":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_2_hour, n_of_observations,
                                                    cutoff_timestamp)
                        case "3H":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_3_hour, n_of_observations,
                                                    cutoff_timestamp)
                        case "4H":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_4_hour, n_of_observations,
                                                    cutoff_timestamp)
                        case "1D":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_daily, n_of_observations,
                                                    cutoff_timestamp)
                        case "1W":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_weekly, n_of_observations)
                        case "1M":
                            hist_data = tv.get_hist(symbol, exchange, Interval.in_monthly, n_of_observations,
                                                    cutoff_timestamp)

                    # bringing timeframe values to minutes if necessary
                    if not type(str_tf) is int:
                        if str_tf.isdigit():
                            tf_in_minutes = int(str_tf)
                        else:
                            # assuming all tfs with letters have only one letter
                            match tf_in_minutes:
                                case 'H':
                                    tf_in_minutes = int(str_tf[:-1]) * 60
                                case 'D':
                                    tf_in_minutes = int(str_tf[:-1]) * 60 * 24
                                case 'W':
                                    tf_in_minutes = int(str_tf[:-1]) * 60 * 24 * 7
                                # roughly a month
                                case 'M':
                                    tf_in_minutes = int(str_tf[:-1]) * 60 * 24 * 7 * 30
                    else:
                        tf_in_minutes = str_tf

                    # calculating # of bars needed to match forecast time
                    forecast_bars = pred_window // tf_in_minutes
                    prediction_value = tv.calculate_gpr(hist_data=hist_data, n_of_observations=n_of_observations,
                                                        forecast_length=forecast_bars)[0][-1]
                    # TODO: # of observations changes somewhere here after 1st loop (over 5)

                    # calculating time at which prediction takes place
                    prediction_time = hist_data.index[-1] + pd.Timedelta(minutes=forecast_bars * tf_in_minutes)

                    # setting bool value to 1 if forecasted value is bigger than last known close price and 0 otherwise
                    prediction_list = [prediction_time, prediction_value,
                                       1 if prediction_value > hist_data["close"].iloc[-1] else 0]
                    predictions[str_tf] = prediction_list

                return predictions

            @staticmethod
            def calculate_obv_ema(hist_data):
                if 'close' not in hist_data.columns or 'volume' not in hist_data.columns:
                    raise ValueError("DataFrame must contain 'close' and 'volume' columns")

                # Инициализация OBV
                obv = [0]  # Начальное значение OBV
                for i in range(1, len(hist_data)):
                    if hist_data['close'].iloc[i] > hist_data['close'].iloc[i - 1]:
                        obv.append(obv[-1] + hist_data['volume'].iloc[i])
                    elif hist_data['close'].iloc[i] < hist_data['close'].iloc[i - 1]:
                        obv.append(obv[-1] - hist_data['volume'].iloc[i])
                    else:
                        obv.append(obv[-1])

                # Создание Series с временными метками и значениями OBV
                obv_series = pd.Series(obv, index=hist_data.index)
                return obv_series

            @staticmethod
            def calculate_ema(prices, period):
                ema_values = []
                alpha = 2 / (period + 1)
                ema_values.append(prices[0])  # Инициализация с первым значением цены

                for price in prices[1:]:
                    ema_values.append(alpha * price + (1 - alpha) * ema_values[-1])

                return pd.Series(ema_values, index=prices.index)

            @staticmethod
            def calculate_supertrend(df, atr_period=50, factor=4.0):
                """
                Рассчитывает значения Supertrend.

                :param df: DataFrame с историческими данными. Ожидаются столбцы: 'open', 'high', 'low', 'close'.
                :param atr_period: Период ATR.
                :param factor: Множитель для расчета Supertrend.
                :return: DataFrame с колонками 'supertrend' и 'direction'.
                """

                data = pd.DataFrame({
                    'close': hist_data['close'],
                    'high': hist_data['high'],
                    'low': hist_data['low'],
                    'open': hist_data['open'],
                    'volume': hist_data['volume']
                }, index=hist_data.index)

                ema_100 = tv.calculate_ema(data['close'], 100)


                df = df.copy()

                # Вычисляем ATR
                df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=atr_period,
                                             fillna=False).average_true_range()

                # Вычисляем EMA 100
                df['ema_100'] = df['close'].ewm(span=100, adjust=False).mean()

                # Вычисляем Basic Upper Band и Basic Lower Band
                df['basic_ub'] = (df['high'] + df['low']) / 2 + factor * df['atr']
                df['basic_lb'] = (df['high'] + df['low']) / 2 - factor * df['atr']

                # Инициализация столбцов final_ub и final_lb
                df['final_ub'] = 0.0
                df['final_lb'] = 0.0
                df['supertrend'] = 0.0
                df['direction'] = 0

                for i in range(1, len(df)):
                    df['final_ub'][i] = df['basic_ub'][i] if (
                            (df['basic_ub'][i] < df['final_ub'][i - 1]) or (
                                df['close'][i - 1] > df['final_ub'][i - 1])) else df['final_ub'][i - 1]
                    df['final_lb'][i] = df['basic_lb'][i] if (
                            (df['basic_lb'][i] > df['final_lb'][i - 1]) or (
                                df['close'][i - 1] < df['final_lb'][i - 1])) else df['final_lb'][i - 1]

                    # Логика пересечения и корректировки тренда
                    if df['close'][i] > df['final_ub'][i - 1] and df['close'][i] > ema_100[i]:
                        df['supertrend'][i] = df['final_lb'][i]
                        df['direction'][i] = 1  # Восходящий тренд
                    elif df['close'][i] < df['final_lb'][i - 1] and df['close'][i] < ema_100[i]:
                        df['supertrend'][i] = df['final_ub'][i]
                        df['direction'][i] = -1  # Нисходящий тренд
                    else:
                        df['supertrend'][i] = df['supertrend'][i - 1]
                        df['direction'][i] = df['direction'][i - 1]

                return df[['supertrend', 'direction']]


        if __name__ == "__main__":
            logging.basicConfig(level=logging.FATAL)
            for logger_name in ['matplotlib', 'urllib3']:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.WARNING)
            pd.set_option('display.max_rows', None)
            warnings.simplefilter(action='ignore', category=FutureWarning)
            warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)
            coins = ["BTCUSDT", "ETHUSDT", "ARBUSDT"]

            value = 1000
            value_3_percent = (value / 100) * 3
            itog = 1000

            csv_file_path_15 = "BINANCE_BTCUSDT, 15_969da.csv"
            csv_file_path_30 = "BINANCE_BTCUSDT, 30_03dcc.csv"
            csv_file_path_1 = "BINANCE_BTCUSDT, 60_379df.csv"
            csv_file_path_2 = "BINANCE_BTCUSDT, 120_b5321.csv"
            csv_file_path_4 = "BINANCE_BTCUSDT, 240_4961b.csv"
            csv_file_path_8h = "BINANCE_BTCUSDT, 480_d0a25.csv"

            while True:
                for symbol in coins:
                    tv = TvDatafeed()
                    exchange = "BINANCE"
                    interval = Interval.in_3_minute
                    n_bars = 1500

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

                    # на 8 часов
                    pred_minutes = 8 * 60
                    # для таймфреймов
                    timeframes = ['5', '15', '30', '1H', '4H']
                    # с обучающей выборкой в, баров:
                    n_of_observations = 500

                    if hist_data is not None:
                        # получаем наши прогнозы для текущего момента
                        gpr_preds = tv.get_gpr_predictions(pred_window=pred_minutes, timeframes=timeframes,
                                                           n_of_observations=n_of_observations, symbol=symbol,
                                                           exchange=exchange)

                        ## Для функции check_gpr (проверки прогнозов gpr на текущий момент) в боте:
                        print(gpr_preds)
                        ## Если нужно вывести только "голоса" для каждого из таймфреймов:
                        votes_dict = {}
                        for i in gpr_preds:
                            votes_dict[i] = gpr_preds[i][2]
                        print(votes_dict)

                        ## Для оповещений:
                        # проверяем, совпадают ли "голоса" gpr, построенных по разным таймфреймам:
                        bool_values = [value[2] for value in gpr_preds.values()]
                        # если совпали,
                        # if len(set(bool_values)) == 1:
                        # возвращаем первый
                        print(f'{bool_values}')

                        if symbol == "BTCUSDT":
                            with open('gauss.json', 'w') as json_file:
                                json.dump(votes_dict, json_file, indent=4)

                    open_figures = []

                    timeframes = [Interval.in_5_minute, Interval.in_15_minute, Interval.in_1_hour]

                    for timeframe in timeframes:
                        hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                        supertrend_df = tv.calculate_supertrend(hist_data, atr_period=50, factor=4.0)

                        # Печать первых 5 строк результата
                        print(supertrend_df.head())

                        # Пример проверки условий для создания сигналов
                        supertrend_df['trend_change'] = supertrend_df['direction'].diff().abs()
                        uptrend_signals = supertrend_df[
                            (supertrend_df['direction'] == 1) & (supertrend_df['trend_change'] == 2)]
                        downtrend_signals = supertrend_df[
                            (supertrend_df['direction'] == -1) & (supertrend_df['trend_change'] == 2)]

                        print("Uptrend signals:")
                        print(uptrend_signals)
                        print("Downtrend signals:")
                        print(downtrend_signals)

                        # Построение графика
                        fig = make_subplots(rows=1, cols=1)

                        # Добавление цены закрытия
                        fig.add_trace(go.Scatter(
                            x=hist_data.index[10:],
                            y=hist_data['close'][10:],
                            mode='lines',
                            name='Close Price',
                            line=dict(color='blue', width=2),
                            opacity=0.5
                        ))

                        # Добавление линии Supertrend
                        fig.add_trace(go.Scatter(
                            x=supertrend_df.index[10:],
                            y=supertrend_df['supertrend'][10:],
                            mode='lines',
                            name='Supertrend',
                            line=dict(color='red', width=2),
                            opacity=0.7
                        ))

                        # Настройка графика
                        fig.update_layout(
                            title='Supertrend Indicator',
                            xaxis_title='Date',
                            yaxis_title='Price',
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )

                        # fig.show()

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_3_minute, n_bars)

                    plt.figure(figsize=(24, 14), clear=True)
                    fig, ax = plt.subplots(figsize=(24, 14), clear=True)

                    bar_width = 0.5

                    hh_ind, hl_ind, lh_ind, ll_ind, bull_bos_ends, bear_bos_ends = tv.update_prices(highs, lows,
                                                                                                    range(len(highs)),
                                                                                                    ax)

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)

                    if hist_data is not None:
                        sma, upper_band, lower_band = tv.calculate_bb(hist_data)

                        # last_upper = upper_band[-1]
                        # last_lower = lower_band[-1]

                    if hist_data is not None:
                        k_smooth, d = tv.calculate_st(hist_data)

                    if hist_data is not None:
                        hist_data_with_mfi = TvDatafeed.calculate_mfi(hist_data)

                    if hist_data is not None:
                        macd, signal, hist = tv.calculate_macd(hist_data)

                    if symbol == "BTCUSDT":
                        timeframes = [Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour, Interval.in_daily]
                        bands_info = {}

                        for timeframe in timeframes:

                            hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                            closes = hist_data["close"].tolist()
                            highs = hist_data["high"].tolist()
                            lows = hist_data["low"].tolist()
                            sma, upper, lower = tv.calculate_bb(hist_data)
                            last_close = closes[-1]  # Assuming 'closes' is already defined as list of close prices

                            if timeframe == Interval.in_1_hour or Interval.in_2_hour:
                                last_close = closes[-12:]  # Предполагаем, что 'closes' уже определен как список закрытых цен

                                # Проверка условий и преобразование в логические значения Python
                                is_above_upper_high = any(high > up for high, up in zip(highs[-12:], upper[-12:]))
                                is_above_upper_close = any(closes > up for closes, up in zip(last_close, upper[-12:]))
                                is_below_lower_low = any(low < low_band for low, low_band in zip(lows[-12:], lower[-12:]))
                                is_below_lower_close = any(
                                    closes < low_band for closes, low_band in zip(last_close, lower[-12:]))

                                # Хранение результатов в словаре
                                bands_info[str(timeframe)] = {
                                    "is_above_upper_high": is_above_upper_high,
                                    "is_above_upper_close": is_above_upper_close,
                                    "is_below_lower_low": is_below_lower_low,
                                    "is_below_lower_close": is_below_lower_close
                                }

                            if timeframe == Interval.in_4_hour:
                                last_close = closes[-6:]  # Предполагаем, что 'closes' уже определен как список закрытых цен

                                # Проверка условий и преобразование в логические значения Python
                                is_above_upper_high = any(high > up for high, up in zip(highs[-6:], upper[-6:]))
                                is_above_upper_close = any(closes > up for closes, up in zip(last_close, upper[-6:]))
                                is_below_lower_low = any(
                                    low < low_band for low, low_band in zip(lows[-6:], lower[-6:]))
                                is_below_lower_close = any(
                                    closes < low_band for closes, low_band in zip(last_close, lower[-6:]))

                                # Хранение результатов в словаре
                                bands_info[str(timeframe)] = {
                                    "is_above_upper_high": is_above_upper_high,
                                    "is_above_upper_close": is_above_upper_close,
                                    "is_below_lower_low": is_below_lower_low,
                                    "is_below_lower_close": is_below_lower_close
                                }

                            if timeframe == Interval.in_daily:
                                last_close = closes[-3:]  # Предполагаем, что 'closes' уже определен как список закрытых цен

                                # Проверка условий и преобразование в логические значения Python
                                is_above_upper_high = any(high > up for high, up in zip(highs[-3:], upper[-3:]))
                                is_above_upper_close = any(closes > up for closes, up in zip(last_close, upper[-3:]))
                                is_below_lower_low = any(
                                    low < low_band for low, low_band in zip(lows[-3:], lower[-3:]))
                                is_below_lower_close = any(
                                    closes < low_band for closes, low_band in zip(last_close, lower[-3:]))

                                # Хранение результатов в словаре
                                bands_info[str(timeframe)] = {
                                    "is_above_upper_high": is_above_upper_high,
                                    "is_above_upper_close": is_above_upper_close,
                                    "is_below_lower_low": is_below_lower_low,
                                    "is_below_lower_close": is_below_lower_close
                                }

                        # Saving the results to a JSON file
                        with open('band_conditions.json', 'w') as f:
                            json.dump(bands_info, f, indent=4)

                        print("JSON data has been saved.")

                    # indicator_type = "Original Aroon"  # Change this to test other types
                    # p = 7  # Lookback window
                    #
                    # aup, adn = TvDatafeed.calculate_aroon_indicator(highs, lows, p, indicator_type)
                    #
                    # # Plot Aroon indicator
                    # TvDatafeed.plot_aroon(timestamps, aup, adn, symbol)
                    def collect_stoch_data(tv, symbol, exchange, timeframes, n_bars):
                        stoch_dictionaries = {}  # Словарь для сохранения значений %K и %D для каждого таймфрейма

                        for timeframe in timeframes:
                            # Получение исторических данных для данного таймфрейма
                            hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                            if hist_data is not None and not hist_data.empty:
                                # Расчет стохастического осциллятора
                                k, d = tv.calculate_st(hist_data)

                                if k is not None and not k.empty and d is not None and not d.empty:
                                    # Сохранение значений %K и %D в словарь для текущего таймфрейма
                                    stoch_dictionaries[timeframe] = {
                                        'k_values': k.iloc[-100:].to_dict(),  # Сохраняем последние 5 значений %K
                                        'd_values': d.iloc[-100:].to_dict()  # Сохраняем последние 5 значений %D
                                    }
                            else:
                                print(f"No historical data available for {timeframe}")

                        return stoch_dictionaries


                    def compare_stoch_values(stoch_dictionaries):
                        comparisons = {}
                        for timeframe, data in stoch_dictionaries.items():
                            last_k = list(data['k_values'].values())[-1]
                            last_d = list(data['d_values'].values())[-1]

                            # Сравнение %K и %D
                            comparison_key = f"%K > %D in {timeframe}"
                            comparisons[comparison_key] = last_k > last_d

                        return comparisons


                    if symbol == "BTCUSDT":

                        timeframes = [Interval.in_15_minute, Interval.in_30_minute, Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour]
                        n_bars = 200  # Количество баров для анализа
                        stoch_data = collect_stoch_data(tv, symbol, exchange, timeframes, n_bars)
                        stoch_comparisons = compare_stoch_values(stoch_data)
                        print(stoch_comparisons)

                        def plot_stochastic_oscillator(stoch_dictionaries, timeframes):
                            colors_k = ['red', 'blue', 'green', 'purple']
                            colors_d = ['#FF6347', '#4682B4', '#32CD32', '#800080']

                            # Словарь для сохранения последних значений %K и %D для Interval.in_1_hour
                            last_values = {}

                            for timeframe, color_k, color_d in zip(timeframes, colors_k, colors_d):
                                data = stoch_dictionaries.get(timeframe)
                                if data:
                                    k_values = list(data['k_values'].values())
                                    d_values = list(data['d_values'].values())
                                    dates = list(data['k_values'].keys())

                                    if timeframe == Interval.in_1_hour:  # Указываем интересующий интервал
                                        last_values['last_k'] = k_values[-1]
                                        last_values['last_d'] = d_values[-1]

                            return last_values, k_values, d_values


                        if symbol == "BTCUSDT":
                            last_stoch_values, k_values, d_values = plot_stochastic_oscillator(stoch_data, timeframes)

                            # Включение последних значений в JSON для сохранения
                            stoch_comparisons['last_values'] = last_stoch_values

                            with open('stoch_comparisons.json', 'w') as json_file:
                                json.dump(stoch_comparisons, json_file, indent=4)

                    if symbol == "BTCUSDT":

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

                    timeframes = [Interval.in_4_hour, Interval.in_2_hour, Interval.in_1_hour, Interval.in_30_minute,
                                  Interval.in_15_minute]
                    rsi_dictionaries = {}
                    rsi_dictionaries_2 = {}

                    timeframes = [Interval.in_4_hour, Interval.in_2_hour, Interval.in_1_hour, Interval.in_30_minute,
                                  Interval.in_15_minute]
                    for timeframe in timeframes:
                        # Получение исторических данных для данного таймфрейма
                        hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                        if hist_data is not None and not hist_data.empty:
                            # Расчёт RSI
                            rsi = tv.calculate_rsi(hist_data)

                            if rsi is not None and not rsi.empty:
                                # Обновление словаря с последними 5 значениями RSI
                                rsi_dictionaries[timeframe] = rsi.iloc[-5:].to_dict()
                                rsi_dictionaries_2[timeframe] = rsi.iloc[-110:].to_dict()

                    print("RSI", rsi[-1])

                    # Проверка условий для RSI на различных таймфреймах
                    if all(timeframe in rsi_dictionaries for timeframe in timeframes):
                        rsi_15m = rsi_dictionaries[Interval.in_15_minute]
                        rsi_30m = rsi_dictionaries[Interval.in_30_minute]
                        rsi_1h = rsi_dictionaries[Interval.in_1_hour]
                        rsi_2h = rsi_dictionaries[Interval.in_2_hour]
                        rsi_4h = rsi_dictionaries[Interval.in_4_hour]

                        if all(timeframe in rsi_dictionaries_2 for timeframe in timeframes):
                            rsi_15m_2 = rsi_dictionaries_2[Interval.in_15_minute]
                            rsi_30m_2 = rsi_dictionaries_2[Interval.in_30_minute]
                            rsi_1h_2 = rsi_dictionaries_2[Interval.in_1_hour]
                            rsi_2h_2 = rsi_dictionaries_2[Interval.in_2_hour]
                            rsi_4h_2 = rsi_dictionaries_2[Interval.in_4_hour]


                        last_rsi_15m = list(rsi_15m.values())[-1]
                        last_rsi_30m = list(rsi_30m.values())[-1]
                        last_rsi_1h = list(rsi_1h.values())[-1]
                        last_rsi_2h = list(rsi_2h.values())[-1]
                        last_rsi_4h = list(rsi_4h.values())[-1]

                        # Сравнение каждого таймфрейма с другим и вывод результатов
                        comparisons = {
                            "15m > 30m": last_rsi_15m > last_rsi_30m,
                            "30m > 1h": last_rsi_30m > last_rsi_1h,
                            "1h > 2h": last_rsi_1h > last_rsi_2h,
                            "2h > 4h": last_rsi_2h > last_rsi_4h,
                            "15m < 30m": last_rsi_15m < last_rsi_30m,
                            "30m < 1h": last_rsi_30m < last_rsi_1h,
                            "1h < 2h": last_rsi_1h < last_rsi_2h,
                            "2h < 4h": last_rsi_2h < last_rsi_4h
                        }

                        if symbol == "BTCUSDT":
                            last_rsi_1h = round(list(rsi_1h.values())[-1], 2)

                            data_to_save = {
                                "comparisons": comparisons,
                                "last_rsi_1h": last_rsi_1h
                            }
                            with open('rsi_comparisons.json', 'w') as json_file:
                                json.dump(data_to_save, json_file, indent=4)

                        divergence_dict = defaultdict(lambda: defaultdict(list))
                        for symbol in coins:
                            def finder_divergences(rsi, hist_data):
                                divergences = []
                                close = hist_data['close']
                                timestamps = hist_data.index.tolist()

                                ignore_count = 4

                                def is_valid_divergence(first_idx, second_idx, first_value, second_value,
                                                        check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and rsi[k] > second_value:
                                                return False
                                            if not check_greater and rsi[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and rsi[k] > first_value:
                                                return False
                                            if not check_greater and rsi[k] < first_value:
                                                return False
                                    return True

                                def is_valid_divergence_close(first_idx, second_idx, first_value, second_value,
                                                              check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and close[k] > second_value:
                                                return False
                                            if not check_greater and close[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and close[k] > first_value:
                                                return False
                                            if not check_greater and close[k] < first_value:
                                                return False
                                    return True

                                for i in range(2, len(rsi) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if rsi[i] > rsi[i - 1] and rsi[i] > rsi[i - 2] and rsi[i] > rsi[i + 1] and rsi[i] > rsi[i + 2]:
                                        first_rsi_max = rsi[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений RSI на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(rsi))):
                                            if rsi[j] > rsi[j - 1] and rsi[j] > rsi[j - 2]:
                                                second_rsi_max = rsi[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_rsi_max > second_rsi_max and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_rsi_max, second_rsi_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_rsi_max < second_rsi_max and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_rsi_max, second_rsi_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(rsi) - 2):
                                    # Проверяем, является ли текущая точка локальным минимумом
                                    if rsi[i] < rsi[i - 1] and rsi[i] < rsi[i - 2] and rsi[i] < rsi[i + 1] and rsi[i] < rsi[i + 2]:
                                        first_rsi_min = rsi[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений RSI на наличие локальных минимумов
                                        for j in range(i + 1, min(i + 101, len(rsi))):
                                            if rsi[j] < rsi[j - 1] and rsi[j] < rsi[j - 2]:
                                                second_rsi_min = rsi[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_rsi_min > second_rsi_min and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_rsi_min, second_rsi_min,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_rsi_min < second_rsi_min and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_rsi_min, second_rsi_min,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] > close[i - 1] and close[i] > close[i - 2] and close[i] > close[
                                        i + 1] and close[i] > close[i + 2]:
                                        first_close_max = close[i]
                                        first_rsi_value = rsi[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] > close[j - 1] and close[j] > close[j - 2]:
                                                second_close_max = close[j]
                                                second_rsi_value = rsi[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_rsi_value < second_rsi_value:
                                                    if is_valid_divergence_close(i, j, first_close_max,
                                                                                 second_close_max, check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_rsi_value > second_rsi_value:
                                                    if is_valid_divergence_close(i, j, first_close_max,
                                                                                 second_close_max, check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] < close[i - 1] and close[i] < close[i - 2] and close[i] < close[
                                        i + 1] and close[i] < close[i + 2]:
                                        first_close_max = close[i]
                                        first_rsi_value = rsi[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] < close[j - 1] and close[j] < close[j - 2]:
                                                second_close_max = close[j]
                                                second_rsi_value = rsi[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_rsi_value < second_rsi_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_rsi_value > second_rsi_value:
                                                     if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                return divergences


                            def finder_divergences_macd(macd, hist_data):
                                divergences = []
                                close = hist_data['close']
                                timestamps = hist_data.index.tolist()
                                ignore_count = 4

                                def is_valid_divergence(first_idx, second_idx, first_value, second_value,
                                                        check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and macd[k] > second_value:
                                                return False
                                            if not check_greater and macd[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and macd[k] > first_value:
                                                return False
                                            if not check_greater and macd[k] < first_value:
                                                return False
                                    return True

                                def is_valid_divergence_close(first_idx, second_idx, first_value, second_value,
                                                              check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and close[k] > second_value:
                                                return False
                                            if not check_greater and close[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and close[k] > first_value:
                                                return False
                                            if not check_greater and close[k] < first_value:
                                                return False
                                    return True

                                for i in range(2, len(macd) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if macd[i] > macd[i - 1] and macd[i] > macd[i - 2] and macd[i] > macd[i + 1] and macd[i] > macd[i + 2]:
                                        first_macd_max = macd[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений macd на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(macd))):
                                            if macd[j] > macd[j - 1] and macd[j] > macd[j - 2]:
                                                second_macd_max = macd[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1494 and first_macd_max > second_macd_max and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_macd_max, second_macd_max,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_macd_max < second_macd_max and first_price > second_price:
                                                   if is_valid_divergence(i, j, first_macd_max, second_macd_max,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(macd) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if macd[i] < macd[i - 1] and macd[i] < macd[i - 2] and macd[i] < macd[i + 1] and macd[i] < macd[i + 2]:
                                        first_macd_min = macd[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений macd на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(macd))):
                                            if macd[j] < macd[j - 1] and macd[j] < macd[j - 2]:
                                                second_macd_min = macd[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1496 and first_macd_min > second_macd_min and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_macd_min, second_macd_min,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_macd_min < second_macd_min and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_macd_min, second_macd_min,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] > close[i - 1] and close[i] > close[i - 2] and close[
                                        i] > close[
                                        i + 1] and close[i] > close[i + 2]:
                                        first_close_max = close[i]
                                        first_macd_value = macd[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] > close[j - 1] and close[j] > close[j - 2]:
                                                second_close_max = close[j]
                                                second_macd_value = macd[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_macd_value < second_macd_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_macd_value > second_macd_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                        (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] < close[i - 1] and close[i] < close[i - 2] and close[
                                        i] < close[
                                        i + 1] and close[i] < close[i + 2]:
                                        first_close_max = close[i]
                                        first_macd_value = macd[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] < close[j - 1] and close[j] < close[j - 2]:
                                                second_close_max = close[j]
                                                second_macd_value = macd[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_macd_value < second_macd_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_macd_value > second_macd_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                                # Продолжаем поиск "вторых" точек
                                return divergences


                            def finder_divergences_macd_k(signal, hist_data):
                                divergences = []
                                close = hist_data['close']
                                timestamps = hist_data.index.tolist()
                                ignore_count = 4

                                def is_valid_divergence(first_idx, second_idx, first_value, second_value,
                                                        check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and signal[k] > second_value:
                                                return False
                                            if not check_greater and signal[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and signal[k] > first_value:
                                                return False
                                            if not check_greater and signal[k] < first_value:
                                                return False
                                    return True

                                def is_valid_divergence_close(first_idx, second_idx, first_value, second_value,
                                                              check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and close[k] > second_value:
                                                return False
                                            if not check_greater and close[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and close[k] > first_value:
                                                return False
                                            if not check_greater and close[k] < first_value:
                                                return False
                                    return True

                                for i in range(2, len(signal) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if signal[i] > signal[i - 1] and signal[i] > signal[i - 2] and signal[i] > signal[i + 1] and signal[i] > signal[i + 2]:
                                        first_signal_max = signal[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений signal на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(signal))):
                                            if signal[j] > signal[j - 1] and signal[j] > signal[j - 2]:
                                                second_signal_max = signal[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1496 and first_signal_max > second_signal_max and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_signal_max, second_signal_max,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_signal_max < second_signal_max and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_signal_max, second_signal_max,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(signal) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if signal[i] < signal[i - 1] and signal[i] < signal[i - 2] and signal[i] < signal[i + 1] and signal[i] < signal[i + 2]:
                                        first_signal_min = signal[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений signal на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(signal))):
                                            if signal[j] < signal[j - 1] and signal[j] < signal[j - 2]:
                                                second_signal_min = signal[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1494 and first_signal_min > second_signal_min and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_signal_min, second_signal_min,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_signal_min < second_signal_min and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_signal_min, second_signal_min,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] > close[i - 1] and close[i] > close[i - 2] and close[i] > close[
                                        i + 1] and close[i] > close[i + 2]:
                                        first_close_max = close[i]
                                        first_signal_value = signal[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] > close[j - 1] and close[j] > close[j - 2]:
                                                second_close_max = close[j]
                                                second_signal_value = signal[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_signal_value < second_signal_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                             (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_signal_value > second_signal_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] < close[i - 1] and close[i] < close[i - 2] and close[i] < close[
                                        i + 1] and close[i] < close[i + 2]:
                                        first_close_max = close[i]
                                        first_signal_value = signal[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] < close[j - 1] and close[j] < close[j - 2]:
                                                second_close_max = close[j]
                                                second_signal_value = signal[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_signal_value < second_signal_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_signal_value > second_signal_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))
                                return divergences


                            def finder_divergences_obv(obv, hist_data):
                                divergences = []
                                close = hist_data['close']
                                timestamps = hist_data.index.tolist()
                                ignore_count = 4

                                def is_valid_divergence(first_idx, second_idx, first_value, second_value,
                                                        check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and obv[k] > second_value:
                                                return False
                                            if not check_greater and obv[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and obv[k] > first_value:
                                                return False
                                            if not check_greater and obv[k] < first_value:
                                                return False
                                    return True

                                def is_valid_divergence_close(first_idx, second_idx, first_value, second_value,
                                                              check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and close[k] > second_value:
                                                return False
                                            if not check_greater and close[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and close[k] > first_value:
                                                return False
                                            if not check_greater and close[k] < first_value:
                                                return False
                                    return True

                                for i in range(2, len(obv) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if obv[i] > obv[i - 1] and obv[i] > obv[i - 2] and obv[i] > obv[i + 1] and obv[i] > obv[i + 2]:
                                        first_obv_max = obv[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений obv на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(obv))):
                                            if obv[j] > obv[j - 1] and obv[j] > obv[j - 2]:
                                                second_obv_max = obv[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1496 and first_obv_max > second_obv_max and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_obv_max, second_obv_max,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_obv_max < second_obv_max and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_obv_max, second_obv_max,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(obv) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if obv[i] < obv[i - 1] and obv[i] < obv[i - 2] and obv[i] < obv[i + 1] and obv[i] < obv[i + 2]:
                                        first_obv_min = obv[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений obv на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(obv))):
                                            if obv[j] < obv[j - 1] and obv[j] < obv[j - 2]:
                                                second_obv_min = obv[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1496 and first_obv_min > second_obv_min and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_obv_min, second_obv_min,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_obv_min < second_obv_min and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_obv_min, second_obv_min,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] > close[i - 1] and close[i] > close[i - 2] and close[i] > close[
                                        i + 1] and close[i] > close[i + 2]:
                                        first_close_max = close[i]
                                        first_obv_value = obv[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] > close[j - 1] and close[j] > close[j - 2]:
                                                second_close_max = close[j]
                                                second_obv_value = obv[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_obv_value < second_obv_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_obv_value > second_obv_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                         (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] < close[i - 1] and close[i] < close[i - 2] and close[i] < close[
                                        i + 1] and close[i] < close[i + 2]:
                                        first_close_max = close[i]
                                        first_obv_value = obv[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] < close[j - 1] and close[j] < close[j - 2]:
                                                second_close_max = close[j]
                                                second_obv_value = obv[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_obv_value < second_obv_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_obv_value > second_obv_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))
                                return divergences

                            def finder_divergences_stoch_k(k, hist_data):
                                divergences = []
                                close = hist_data['close']
                                timestamps = hist_data.index.tolist()
                                ignore_count = 4

                                def is_valid_divergence(first_idx, second_idx, first_value, second_value,
                                                        check_greater=True):
                                    if first_idx < second_idx:
                                        for r in range(first_idx + 1, second_idx):
                                            if check_greater and k[r] > second_value:
                                                return False
                                            if not check_greater and k[r] < second_value:
                                                return False
                                    else:
                                        for r in range(second_idx + 1, first_idx):
                                            if check_greater and k[r] > first_value:
                                                return False
                                            if not check_greater and k[r] < first_value:
                                                return False
                                    return True

                                def is_valid_divergence_close(first_idx, second_idx, first_value, second_value,
                                                              check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and close[k] > second_value:
                                                return False
                                            if not check_greater and close[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and close[k] > first_value:
                                                return False
                                            if not check_greater and close[k] < first_value:
                                                return False
                                    return True

                                for i in range(2, len(k) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if k[i] > k[i - 1] and k[i] > k[i - 2] and k[i] > k[i + 1] and k[i] > k[i + 2]:
                                        first_k_max = k[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений k на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(k))):
                                            if k[j] > k[j - 1] and k[j] > k[j - 2]:
                                                second_k_max = k[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1495 and first_k_max > second_k_max and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_k_max, second_k_max,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_k_max < second_k_max and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_k_max, second_k_max,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(k) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if k[i] < k[i - 1] and k[i] < k[i - 2] and k[i] < k[i + 1] and k[i] < k[i + 2]:
                                        first_k_min = k[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений k на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(k))):
                                            if k[j] < k[j - 1] and k[j] < k[j - 2]:
                                                second_k_min = k[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1495 and first_k_min > second_k_min and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_k_min, second_k_min,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1495 and first_k_min < second_k_min and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_k_min, second_k_min,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] > close[i - 1] and close[i] > close[i - 2] and close[i] > close[
                                        i + 1] and close[i] > close[i + 2]:
                                        first_close_max = close[i]
                                        first_k_value = k[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] > close[j - 1] and close[j] > close[j - 2]:
                                                second_close_max = close[j]
                                                second_k_value = k[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_k_value < second_k_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_k_value > second_k_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(close) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if close[i] < close[i - 1] and close[i] < close[i - 2] and close[i] < close[
                                        i + 1] and close[i] < close[i + 2]:
                                        first_close_max = close[i]
                                        first_k_value = k[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений Close на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(close))):
                                            if close[j] < close[j - 1] and close[j] < close[j - 2]:
                                                second_close_max = close[j]
                                                second_k_value = k[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции и что дивергенция не произошла менее 4 свечей назад
                                                if j >= 1494 and first_close_max > second_close_max and first_k_value < second_k_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=True):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1494 and first_close_max < second_close_max and first_k_value > second_k_value:
                                                    if is_valid_divergence_close(i, j, first_close_max, second_close_max,
                                                                           check_greater=False):
                                                        divergences.append(
                                                            (first_time, second_time, 'Bullish Divergence'))
                                return divergences

                            def finder_divergences_stoch_d(d, hist_data):
                                divergences = []
                                close = hist_data['close']
                                timestamps = hist_data.index.tolist()
                                ignore_count = 4

                                def is_valid_divergence(first_idx, second_idx, first_value, second_value,
                                                        check_greater=True):
                                    if first_idx < second_idx:
                                        for r in range(first_idx + 1, second_idx):
                                            if check_greater and d[r] > second_value:
                                                return False
                                            if not check_greater and d[r] < second_value:
                                                return False
                                    else:
                                        for r in range(second_idx + 1, first_idx):
                                            if check_greater and d[r] > first_value:
                                                return False
                                            if not check_greater and d[r] < first_value:
                                                return False
                                    return True

                                def is_valid_divergence_close(first_idx, second_idx, first_value, second_value,
                                                              check_greater=True):
                                    if first_idx < second_idx:
                                        for k in range(first_idx + 1, second_idx):
                                            if check_greater and close[k] > second_value:
                                                return False
                                            if not check_greater and close[k] < second_value:
                                                return False
                                    else:
                                        for k in range(second_idx + 1, first_idx):
                                            if check_greater and close[k] > first_value:
                                                return False
                                            if not check_greater and close[k] < first_value:
                                                return False
                                    return True

                                for i in range(2, len(d) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if d[i] > d[i - 1] and d[i] > d[i - 2] and d[i] > d[i + 1] and d[i] > d[i + 2]:
                                        first_d_max = d[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений d на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(d))):
                                            if d[j] > d[j - 1] and d[j] > d[j - 2]:
                                                second_d_max = d[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1496 and first_d_max > second_d_max and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_d_max, second_d_max,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_d_max < second_d_max and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_d_max, second_d_max,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))

                                for i in range(2, len(d) - 2):
                                    # Проверяем, является ли текущая точка локальным максимумом
                                    if d[i] < d[i - 1] and d[i] < d[i - 2] and d[i] < d[i + 1] and d[i] < d[i + 2]:
                                        first_d_min = d[i]
                                        first_price = close[i]
                                        first_time = timestamps[i]

                                        # Проверяем следующие 100 значений d на наличие локальных максимумов
                                        for j in range(i + 1, min(i + 101, len(d))):
                                            if d[j] < d[j - 1] and d[j] < d[j - 2]:
                                                second_d_min = d[j]
                                                second_price = close[j]
                                                second_time = timestamps[j]

                                                # Проверяем условия для дивергенции
                                                if j >= 1496 and first_d_min > second_d_min and first_price < second_price:
                                                    if is_valid_divergence(i, j, first_d_min, second_d_min,
                                                                           check_greater=True):
                                                        divergences.append((first_time, second_time, 'Bearish Divergence'))
                                                elif j >= 1496 and first_d_min < second_d_min and first_price > second_price:
                                                    if is_valid_divergence(i, j, first_d_min, second_d_min,
                                                                           check_greater=False):
                                                        divergences.append((first_time, second_time, 'Bullish Divergence'))
                                return divergences


                            timeframes = [Interval.in_4_hour, Interval.in_2_hour, Interval.in_1_hour,
                                          Interval.in_30_minute,
                                          Interval.in_15_minute]

                            for timeframe in timeframes:
                                hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                            timeframes = [Interval.in_4_hour, Interval.in_2_hour, Interval.in_1_hour,
                                          Interval.in_30_minute,
                                          Interval.in_15_minute]

                            last_divergences_rsi = {}
                            last_divergences_macd = {}
                            last_divergences_macd_k = {}
                            last_divergences_obv = {}
                            last_divergences_stoch_k = {}
                            last_divergences_stoch_d = {}

                            for timeframe in timeframes:
                                hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                                timestamps = hist_data.index.tolist()  # Список меток времени

                                if hist_data is not None and not hist_data.empty:
                                    # Расчет RSI и MACD
                                    rsi = tv.calculate_rsi(hist_data)
                                    macd, signal, _ = tv.calculate_macd(hist_data)
                                    obv = tv.calculate_obv_ema(hist_data)
                                    k, d = tv.calculate_st(hist_data)
                                    close = hist_data['close']
                                    volume = hist_data["volume"].tolist()
                                    timestamps = hist_data.index.tolist()

                                    # Находим дивергенции RSI
                                    divergences_rsi = finder_divergences(rsi, hist_data)
                                    if divergences_rsi:
                                        divergences_rsi.sort(key=lambda x: x[1])
                                        last_divergences_rsi[timeframe] = divergences_rsi[-1]
                                    else:
                                        last_divergences_rsi[timeframe] = None

                                    # Находим дивергенции MACD
                                    divergences_macd = finder_divergences_macd(macd, hist_data)
                                    if divergences_macd:
                                        divergences_macd.sort(key=lambda x: x[1])
                                        last_divergences_macd[timeframe] = divergences_macd[-1]
                                    else:
                                        last_divergences_macd[timeframe] = None

                                    divergences_macd_k = finder_divergences_macd_k(signal, hist_data)
                                    if divergences_macd_k:
                                        divergences_macd_k.sort(key=lambda x: x[1])
                                        last_divergences_macd_k[timeframe] = divergences_macd_k[-1]
                                    else:
                                        last_divergences_macd_k[timeframe] = None

                                    divergences_obv = finder_divergences_obv(obv, hist_data)
                                    if divergences_obv:
                                        divergences_obv.sort(key=lambda x: x[1])
                                        last_divergences_obv[timeframe] = divergences_obv[-1]
                                    else:
                                        last_divergences_obv[timeframe] = None

                                    divergences_stoch_k = finder_divergences_stoch_k(k, hist_data)
                                    if divergences_stoch_k:
                                        divergences_stoch_k.sort(key=lambda x: x[1])
                                        last_divergences_stoch_k[timeframe] = divergences_stoch_k[-1]
                                    else:
                                        last_divergences_stoch_k[timeframe] = None

                                    # divergences_stoch_d = finder_divergences_stoch_d(d, hist_data)
                                    # if divergences_stoch_d:
                                    #     divergences_stoch_d.sort(key=lambda x: x[1])
                                    #     last_divergences_stoch_d[timeframe] = divergences_stoch_d[-1]
                                    # else:
                                    #     last_divergences_stoch_d[timeframe] = None

                            # Объединяем дивергенции RSI и MACD
                            for timeframe, divergence in last_divergences_rsi.items():
                                if divergence:
                                    divergence_type = divergence[2]
                                    divergence_data = {
                                        "indicator": "RSI",
                                        "timeframe": str(timeframe),
                                        "first_time": divergence[0].isoformat(),
                                        "second_time": divergence[1].isoformat(),
                                        "type": divergence_type
                                    }
                                    divergence_dict[symbol][divergence_type].append(divergence_data)

                            for timeframe, divergence in last_divergences_macd.items():
                                if divergence:
                                    divergence_type = divergence[2]
                                    divergence_data = {
                                        "indicator": "MACD",
                                        "timeframe": str(timeframe),
                                        "first_time": divergence[0].isoformat(),
                                        "second_time": divergence[1].isoformat(),
                                        "type": divergence_type
                                    }
                                    divergence_dict[symbol][divergence_type].append(divergence_data)

                            for timeframe, divergence in last_divergences_macd_k.items():
                                if divergence:
                                    divergence_type = divergence[2]
                                    divergence_data = {
                                        "indicator": "MACD_K",
                                        "timeframe": str(timeframe),
                                        "first_time": divergence[0].isoformat(),
                                        "second_time": divergence[1].isoformat(),
                                        "type": divergence_type
                                    }
                                    divergence_dict[symbol][divergence_type].append(divergence_data)

                            for timeframe, divergence in last_divergences_obv.items():
                                if divergence:
                                    divergence_type = divergence[2]
                                    divergence_data = {
                                        "indicator": "OBV",
                                        "timeframe": str(timeframe),
                                        "first_time": divergence[0].isoformat(),
                                        "second_time": divergence[1].isoformat(),
                                        "type": divergence_type
                                    }
                                    divergence_dict[symbol][divergence_type].append(divergence_data)

                            for timeframe, divergence in last_divergences_stoch_k.items():
                                if divergence:
                                    divergence_type = divergence[2]
                                    divergence_data = {
                                        "indicator": "STOCH",
                                        "timeframe": str(timeframe),
                                        "first_time": divergence[0].isoformat(),
                                        "second_time": divergence[1].isoformat(),
                                        "type": divergence_type
                                    }
                                    divergence_dict[symbol][divergence_type].append(divergence_data)

                            # for timeframe, divergence in last_divergences_stoch_d.items():
                            #     if divergence:
                            #         divergence_type = divergence[2]
                            #         divergence_data = {
                            #             "indicator": "STOCH_D",
                            #             "timeframe": str(timeframe),
                            #             "first_time": divergence[0].isoformat(),
                            #             "second_time": divergence[1].isoformat(),
                            #             "type": divergence_type
                            #         }
                            #         divergence_dict[divergence_type].append(divergence_data)

                            # Сохраняем данные в файл JSON
                            with open('divergences.json', 'w') as json_file:
                                json.dump(divergence_dict, json_file, indent=4)


                        def finder_divergences_stoch(d_values, close, neighborhood=2):
                            divergence_points = []
                            # Поиск выдающихся точек в d_values
                            for i in range(neighborhood, len(d_values) - neighborhood):
                                local_d_values = d_values.iloc[i - neighborhood:i + neighborhood + 1]
                                local_max = local_d_values.max()
                                local_min = local_d_values.min()

                                if d_values.iloc[i] == local_max or d_values.iloc[i] == local_min:
                                    # Поиск последовательности дивергенций
                                    sequence = [{'index': i, 'd_values': d_values.iloc[i], 'close': close.iloc[i]}]
                                    last_extreme = d_values.iloc[i]

                                    # Определяем направление дивергенции
                                    looking_for_higher = (
                                            d_values.iloc[i] == local_min)  # Ищем выше, если текущая точка - минимум
                                    looking_for_lower = not looking_for_higher

                                    for j in range(i + neighborhood, len(d_values) - neighborhood):
                                        next_local_d_values = d_values.iloc[j - neighborhood:j + neighborhood + 1]
                                        next_local_max = next_local_d_values.max()
                                        next_local_min = next_local_d_values.min()

                                        # Находим следующую крайнюю точку
                                        if (d_values.iloc[j] == next_local_max or d_values.iloc[j] == next_local_min):
                                            if ((looking_for_higher and d_values.iloc[j] > last_extreme) or
                                                    (looking_for_lower and d_values.iloc[j] < last_extreme)):
                                                # Проверяем на дивергенцию
                                                if (sequence[-1]['d_values'] > d_values.iloc[j] and sequence[-1]['close'] <
                                                    close.iloc[j]) or \
                                                        (sequence[-1]['d_values'] < d_values.iloc[j] and sequence[-1][
                                                            'close'] > close.iloc[j]):
                                                    sequence.append(
                                                        {'index': j, 'd_values': d_values.iloc[j], 'close': close.iloc[j]})
                                                    last_extreme = d_values.iloc[j]  # Обновляем последнюю крайнюю точку

                                                    # Продолжаем цикл до тех пор, пока условие прерывания не выполнится
                                                    continue
                                            break  # Нарушение условия продолжения цикла

                                    # Сохраняем найденные дивергенции, если длина последовательности больше 1
                                    if len(sequence) > 1:
                                        for k in range(1, len(sequence)):
                                            divergence_points.append({
                                                'first_time': d_values.index[sequence[k - 1]['index']],
                                                'second_time': d_values.index[sequence[k]['index']],
                                                'first_d_values': sequence[k - 1]['d_values'],
                                                'second_d_values': sequence[k]['d_values'],
                                                'first_close': sequence[k - 1]['close'],
                                                'second_close': sequence[k]['close']
                                            })
                            return divergence_points

                        def finder_divergences_stoch_k(k_values, close, neighborhood=2):
                            divergence_points = []
                            # Поиск выдающихся точек в k_values
                            for i in range(neighborhood, len(k_values) - neighborhood):
                                local_k_values = k_values.iloc[i - neighborhood:i + neighborhood + 1]
                                local_max = local_k_values.max()
                                local_min = local_k_values.min()

                                if k_values.iloc[i] == local_max or k_values.iloc[i] == local_min:
                                    # Поиск последовательности дивергенций
                                    sequence = [{'index': i, 'k_values': k_values.iloc[i], 'close': close.iloc[i]}]
                                    last_extreme = k_values.iloc[i]

                                    # Определяем направление дивергенции
                                    looking_for_higher = (
                                            k_values.iloc[i] == local_min)  # Ищем выше, если текущая точка - минимум
                                    looking_for_lower = not looking_for_higher

                                    for j in range(i + neighborhood, len(k_values) - neighborhood):
                                        next_local_k_values = k_values.iloc[j - neighborhood:j + neighborhood + 1]
                                        next_local_max = next_local_k_values.max()
                                        next_local_min = next_local_k_values.min()

                                        # Находим следующую крайнюю точку
                                        if (k_values.iloc[j] == next_local_max or k_values.iloc[j] == next_local_min):
                                            if ((looking_for_higher and k_values.iloc[j] > last_extreme) or
                                                    (looking_for_lower and k_values.iloc[j] < last_extreme)):
                                                # Проверяем на дивергенцию
                                                if (sequence[-1]['k_values'] > k_values.iloc[j] and sequence[-1]['close'] <
                                                    close.iloc[j]) or \
                                                        (sequence[-1]['k_values'] < k_values.iloc[j] and sequence[-1][
                                                            'close'] > close.iloc[j]):
                                                    sequence.append(
                                                        {'index': j, 'k_values': k_values.iloc[j], 'close': close.iloc[j]})
                                                    last_extreme = k_values.iloc[j]  # Обновляем последнюю крайнюю точку

                                                    # Продолжаем цикл до тех пор, пока условие прерывания не выполнится
                                                    continue
                                            break  # Нарушение условия продолжения цикла

                                    # Сохраняем найденные дивергенции, если длина последовательности больше 1
                                    if len(sequence) > 1:
                                        for k in range(1, len(sequence)):
                                            divergence_points.append({
                                                'first_time': k_values.index[sequence[k - 1]['index']],
                                                'second_time': k_values.index[sequence[k]['index']],
                                                'first_k_values': sequence[k - 1]['k_values'],
                                                'second_k_values': sequence[k]['k_values'],
                                                'first_close': sequence[k - 1]['close'],
                                                'second_close': sequence[k]['close']
                                            })
                            return divergence_points


                        timeframes = [Interval.in_4_hour, Interval.in_2_hour, Interval.in_1_hour, Interval.in_30_minute,
                                      Interval.in_15_minute]

                        # Словарь для хранения последней дивергенции на каждом таймфрейме
                        last_divergences = {}
                        last_divergences_k = {}
                        for timeframe in timeframes:
                            hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                            v_k, v_d = tv.calculate_st(hist_data)

                            print("K", {v_k[-1]}, "D", {v_d[-1]})

                            if hist_data is not None and not hist_data.empty:
                                # Расчет macd
                                last_stoch_values, k_values, d_values = plot_stochastic_oscillator(stoch_data, timeframes)
                                timestamps = timestamps[:len(k_values)]
                                k_values = pd.Series(v_k, index=timestamps)
                                d_values = pd.Series(v_d, index=timestamps)
                                # Получение данных о закрытии
                                close = hist_data['close']

                                # Находим дивергенцииё
                                divergences = finder_divergences_stoch(d_values, close)

                                divergences_k = finder_divergences_stoch_k(k_values, close)

                                if divergences:
                                    # Сохраняем последнюю найденную дивергенцию
                                    last_divergences[timeframe] = divergences[-1]
                                else:
                                    last_divergences[timeframe] = None

                                if divergences_k:
                                    # Сохраняем последнюю найденную дивергенцию
                                    last_divergences_k[timeframe] = divergences_k[-1]
                                else:
                                    last_divergences_k[timeframe] = None

                        # Вывод результатов
                        for timeframe, divergence in last_divergences.items():
                            if divergence:
                                print(f"Последняя дивергенция на таймфрейме {timeframe}:\n{divergence}")
                            else:
                                print(f"На таймфрейме {timeframe} дивергенции не найдены.")


                    if symbol == "BTCUSDT":

                        timeframes = [Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour, Interval.in_daily]

                        current_colors = {}
                        current_values = {}
                        for timeframe in timeframes:
                            hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars = 1000)
                            close = pd.Series(hist_data["close"])  # Преобразуем список в Series

                            def HMA(src, length):
                                return ta.hma(src, length)


                            def EHMA(src, length):
                                half_length = int(length / 2)
                                sqrt_length = int(sqrt(length))
                                ema1 = ta.ema(src, length=half_length)
                                ema2 = ta.ema(src, length=length)
                                return ta.ema(2 * ema1 - ema2, length=sqrt_length)


                            def THMA(src, length):
                                third_length = int(length / 3)
                                half_length = int(length / 2)
                                wma1 = ta.wma(src, length=third_length)
                                wma2 = ta.wma(src, length=half_length)
                                wma3 = ta.wma(src, length=length)
                                return ta.wma(3 * wma1 - wma2 - wma3, length=length)


                            # Входные параметры
                            src = close
                            modeSwitch = "Hma"  # Можно заменить на "Thma" или "Ehma"
                            length = 55
                            lengthMult = 1.0

                            # Выбор режима
                            if modeSwitch == "Hma":
                                HULL = HMA(src, int(length * lengthMult))
                            elif modeSwitch == "Ehma":
                                HULL = EHMA(src, int(length * lengthMult))
                            elif modeSwitch == "Thma":
                                HULL = THMA(src, int(length * lengthMult) // 2)
                            else:
                                HULL = pd.Series([None] * len(src))

                            last_hull_value = HULL.iloc[-1] if not HULL.empty else None
                            last_close_price = close.iloc[-1] if not close.empty else None

                            # Сохранение в словарь
                            current_values[str(timeframe)] = {
                                "last_close_price": last_close_price,
                                "last_hull_value": last_hull_value
                            }

                            print(current_values)
                            # Цвет линии
                            def get_hull_color(HULL):
                                color = []
                                for i in range(2, len(HULL)):
                                    if HULL[i] > HULL[i - 2]:
                                        color.append('green')
                                    else:
                                        color.append('red')
                                return ['orange',
                                        'orange'] + color  # Первые два значения не имеют предыдущих двух значений для сравнения


                            hull_color = get_hull_color(HULL)


                            # Вывод текущего цвета

                        with open('current_colors.json', 'w') as json_file:
                            json.dump(current_values, json_file, indent=4)

                    mfi_values = tv.plot_mfi_over_timeframes(timeframes, symbol, exchange, n_bars, tv)

                    # Сравнение MFI значений

                    def compare_macd_signal(tv, symbol, exchange, timeframes, n_bars):
                        comparisons = {}
                        for timeframe in timeframes:
                            hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                            if symbol == "BTCUSDT":
                                macd, signal, _ = tv.calculate_macd(
                                    hist_data)  # Добавление `_` для игнорирования гистограммы
                                macd_above_signal = macd.iloc[-1] > signal.iloc[-1]
                                comparisons[f"MACD > Signal in {timeframe.value}"] = bool(macd_above_signal)  # Преобразование в bool
                        return comparisons

                    # Пример использования
                    # Предполагаем, что data — это словарь, где ключи — это Interval, а значения — это DataFrame с данными по ценам
                    timeframes = [Interval.in_15_minute, Interval.in_30_minute, Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour]
                    data = {interval: pd.DataFrame() for interval in timeframes}  # Загрузите реальные данные здесь

                    # Выполнение сравнения
                    macd_comparisons = compare_macd_signal(tv, symbol, exchange, timeframes, n_bars)

                    if symbol == "BTCUSDT":
                        with open('macd_comparisons.json', 'w') as json_file:
                            json.dump(macd_comparisons, json_file, indent=4)

                    hist_data = tv.get_hist(symbol, exchange, interval, n_bars)

                    # Преобразование данных в DataFrame
                    data = pd.DataFrame({
                        'close': hist_data['close'],
                        'high': hist_data['high'],
                        'low': hist_data['low'],
                        'open': hist_data['open'],
                        'volume': hist_data['volume']
                    }, index=hist_data.index)


                    # Функция расчета EMA
                    def calculate_ema(prices, period):
                        ema_values = []
                        alpha = 2 / (period + 1)
                        ema_values.append(prices[0])  # Инициализация с первым значением цены

                        for price in prices[1:]:
                            ema_values.append(alpha * price + (1 - alpha) * ema_values[-1])

                        return pd.Series(ema_values, index=prices.index)


                    # Расчет EMA для периодов 20, 50, 100, и 200
                    ema_20 = calculate_ema(data['close'], 20)
                    ema_50 = calculate_ema(data['close'], 50)
                    ema_100 = calculate_ema(data['close'], 100)
                    ema_200 = calculate_ema(data['close'], 200)


                    # Вывод последних значений EMA
                    last_ema_values = {
                        'EMA 20': ema_20.iloc[-1],
                        'EMA 50': ema_50.iloc[-1],
                        'EMA 100': ema_100.iloc[-1],
                        'EMA 200': ema_200.iloc[-1]
                    }

                    print(last_ema_values)

                    # Вывод результатов тестирования

                    # def load_rsi_comparisons():
                    #     with open('rsi_comparisons.json', 'r') as file:
                    #         data = json.load(file)
                    #     return data['comparisons']
                    #
                    #
                    # rsi_comparisons = load_rsi_comparisons()

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)
                    timestamps = hist_data.index.tolist()
                    closes = hist_data["close"].tolist()

                    bandwidth = 8.0
                    mult = 2.0
                    upper, lower = tv.nadaraya_watson_envelope(closes, bandwidth, mult, repaint=True)

                    # Generating labels for crossing points
                    labels = []
                    for i in range(1, len(closes)):
                        if closes[i - 1] > upper[i - 1] and closes[i] < upper[i]:
                            labels.append({'x': timestamps[i], 'y': closes[i], 'text': '▼'})
                        if closes[i - 1] < lower[i - 1] and closes[i] > lower[i]:
                            labels.append({'x': timestamps[i], 'y': closes[i], 'text': '▲'})

                    tv.plot_nwe(timestamps, closes, upper, lower, labels, symbol)

                    if symbol == "BTCUSDT":
                        timeframes = [Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour, Interval.in_daily]
                        nw_info = {}

                        for timeframe in timeframes:
                            hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                            closes = hist_data["close"].tolist()
                            highs = hist_data["high"].tolist()
                            lows = hist_data["low"].tolist()
                            bandwidth = 8.0
                            mult = 3.0
                            if timeframe == Interval.in_daily:
                                mult = 2.0
                            upper, lower = tv.nadaraya_watson_envelope(closes, bandwidth, mult, repaint=True)


                            if timeframe == Interval.in_1_hour or Interval.in_2_hour:

                                last_close = closes[-12:]  # Предполагаем, что 'closes' уже определен как список закрытых цен

                                # Проверка условий и преобразование в логические значения Python
                                is_above_upper_high = any(high > up for high, up in zip(highs[-12:], upper[-12:]))
                                is_above_upper_close = any(closes > up for closes, up in zip(last_close, upper[-12:]))
                                is_below_lower_low = any(low < low_band for low, low_band in zip(lows[-12:], lower[-12:]))
                                is_below_lower_close = any(closes < low_band for closes, low_band in zip(last_close, lower[-12:]))

                                # Хранение результатов в словаре
                                nw_info[str(timeframe)] = {
                                    "is_above_upper_high": is_above_upper_high,
                                    "is_above_upper_close": is_above_upper_close,
                                    "is_below_lower_low": is_below_lower_low,
                                    "is_below_lower_close": is_below_lower_close
                                }

                            if timeframe == Interval.in_4_hour:
                                last_close = closes[-6:]  # Предполагаем, что 'closes' уже определен как список закрытых цен

                                # Проверка условий и преобразование в логические значения Python
                                is_above_upper_high = any(high > up for high, up in zip(highs[-6:], upper[-6:]))
                                is_above_upper_close = any(closes > up for closes, up in zip(last_close, upper[-6:]))
                                is_below_lower_low = any(
                                    low < low_band for low, low_band in zip(lows[-6:], lower[-6:]))
                                is_below_lower_close = any(
                                    closes < low_band for closes, low_band in zip(last_close, lower[-6:]))

                                # Хранение результатов в словаре
                                nw_info[str(timeframe)] = {
                                    "is_above_upper_high": is_above_upper_high,
                                    "is_above_upper_close": is_above_upper_close,
                                    "is_below_lower_low": is_below_lower_low,
                                    "is_below_lower_close": is_below_lower_close
                                }

                            if timeframe == Interval.in_daily:
                                last_close = closes[-3:]  # Предполагаем, что 'closes' уже определен как список закрытых цен

                                # Проверка условий и преобразование в логические значения Python
                                is_above_upper_high = any(high > up for high, up in zip(highs[-3:], upper[-3:]))
                                is_above_upper_close = any(closes > up for closes, up in zip(last_close, upper[-3:]))
                                is_below_lower_low = any(
                                    low < low_band for low, low_band in zip(lows[-3:], lower[-3:]))
                                is_below_lower_close = any(
                                    closes < low_band for closes, low_band in zip(last_close, lower[-3:]))

                                # Хранение результатов в словаре
                                nw_info[str(timeframe)] = {
                                    "is_above_upper_high": is_above_upper_high,
                                    "is_above_upper_close": is_above_upper_close,
                                    "is_below_lower_low": is_below_lower_low,
                                    "is_below_lower_close": is_below_lower_close
                                }

                        # Сохранение результатов в JSON-файл
                        with open('nw_conditions.json', 'w') as f:
                            json.dump(nw_info, f, indent=4)

                        print("JSON data has been saved.")

                    time.sleep(10)

                    del hist_data, timestamps, highs, lows, opens, closes, volume, current_price
                    del open_figures, fig, ax

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
