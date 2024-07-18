import datetime
import enum
import gc
import json
import logging
import os
import random
import re
import string
import sys
import time
from math import sqrt

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
            def find_imbalance(highs, lows):
                imbalance_zones_green = []
                imbalance_zones_red = []
                n = len(highs)

                for i in range(2, n):
                    if lows[i] > highs[i - 2]:
                        valid = True
                        for j in range(i + 1, n):
                            if highs[i - 2] > lows[j]:
                                valid = True
                                break
                        if valid:
                            imbalance_zones_green.append((i - 2, i))

                for i in range(2, n):
                    if highs[i] < lows[i - 2]:
                        valid = True
                        for j in range(i + 1, n):
                            if lows[i - 2] < highs[j]:
                                valid = True
                                break
                        if valid:
                            imbalance_zones_red.append((i - 2, i))

                return imbalance_zones_green, imbalance_zones_red

            @staticmethod
            def get_4h_imbalance_zones(symbol, exchange, n_bars):
                tv = TvDatafeed()
                four_hour_data = tv.get_hist(symbol, exchange, Interval.in_4_hour, n_bars // 4)
                if four_hour_data is None:
                    logger.error(f"Failed to retrieve 4-hour data for {symbol}")
                    return None
                four_hour_highs = four_hour_data["high"].tolist()
                four_hour_lows = four_hour_data["low"].tolist()
                four_hour_opens = four_hour_data["open"].tolist()
                four_hour_closes = four_hour_data["close"].tolist()
                four_hour_timestamps = four_hour_data.index.tolist()
                n = len(four_hour_highs)

                hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)
                if hist_data is None:
                    logger.error(f"Failed to retrieve hourly data for {symbol}")
                    return None
                highest = hist_data["high"].tolist()
                lowest = hist_data["low"].tolist()
                opens = hist_data["open"].tolist()
                closes = hist_data["close"].tolist()
                hourly_timestamps = hist_data.index.tolist()

            @staticmethod
            def calculate_midpoints(valid_zones_red_day, day_highs, day_lows):
                midpoints = []
                for zone in valid_zones_red_day:
                    start_index, end_index = zone
                    high_at_start = day_highs[start_index]
                    low_at_end = day_lows[end_index]
                    midpoint = (high_at_start + low_at_end) / 2
                    midpoints.append((zone, midpoint))
                return midpoints

            @staticmethod
            def calculate_average_midpoint(midpoints):
                if not midpoints:
                    return None
                total_sum = sum(midpoint for _, midpoint in midpoints)
                average_midpoint = total_sum / len(midpoints)
                return average_midpoint

            @staticmethod
            def find_rejection_blocks(opens, closes):
                rejection_blocks = []
                for i in range(len(opens) - 1):
                    if opens[i] < closes[i] and opens[i + 1] > closes[i + 1]:
                        if closes[i + 1] < opens[i]:
                            rejection_blocks.append(i)
                return rejection_blocks

            # @staticmethod
            # def find_rejection_blocks(opens, highs, lows, closes, window=20):
            #     rejection_blocks = []
            #     closes_series = pd.Series(closes)
            #     sma = closes_series.rolling(window=window).mean()
            #
            #     for i in range(1, len(opens) - 1):
            #         # Условия для rejection block:
            #         # 1. День i-1 заканчивается на повышении
            #         # 2. День i заканчивается на снижении
            #         # 3. Закрытие дня i ниже открытия дня i-1
            #         # 4. Высокий день i меньше максимума дня i-1
            #         # 5. Закрытие дня i ниже скользящей средней
            #         if opens[i - 1] < closes[i - 1] and opens[i] > closes[i]:
            #             if closes[i] < opens[i - 1] and highs[i] < highs[i - 1]:
            #                 if closes[i] < sma[i]:
            #                     rejection_blocks.append(i)
            #     return rejection_blocks

            @staticmethod
            def test_hh_rejection_blocks(hh_indices, rejection_blocks, lows, closes):
                hh_rb_combinations = 0
                below_rb_after_combination = 0
                above_rb_after_combination = 0
                lows_at_rb_indices = []
                lows_after_rb_indices = []
                value = 1000

                for hh_index in hh_indices:
                    for rb_index in rejection_blocks:
                        if 0 <= (rb_index - hh_index) <= 3:
                            hh_rb_combinations += 1
                            rb_min = closes[rb_index]

                            if rb_index + 5 < len(closes):
                                future_low = closes[rb_index + 5]
                                percent_change = ((future_low - rb_min) / rb_min)
                                percent_change = round(percent_change, 3)

                                if future_low < rb_min:
                                    below_rb_after_combination += 1
                                    lows_at_rb_indices.append(rb_min)
                                    lows_after_rb_indices.append(future_low)
                                    value += (value * (abs(percent_change) * 25))
                                elif future_low > rb_min:
                                    # if percent_change > 0.1:
                                    #     percent_change = 0.1
                                    above_rb_after_combination += 1
                                    lows_at_rb_indices.append(rb_min)
                                    lows_after_rb_indices.append(future_low)
                                    value -= (value * (abs(percent_change) * 25))

                return (hh_rb_combinations,
                        below_rb_after_combination,
                        above_rb_after_combination,
                        lows_at_rb_indices,
                        lows_after_rb_indices,
                        value)

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
            def test_highs_after_hh(highs_after_hh, hh_start_array, highs, lows, daily_max_highs, daily_min_lows):
                results = []

                for idx in highs_after_hh:
                    previous_day_max = None
                    previous_day_min = None

                    # Определяем предыдущие максимумы и минимумы дня для текущего индекса
                    for i in range(len(daily_max_highs)):
                        if i < idx:
                            previous_day_max = daily_max_highs[i]
                            previous_day_min = daily_min_lows[i]
                        else:
                            break

                    midpoint = (previous_day_max + previous_day_min) / 2

                    # Проверяем, было ли пересечение midpoint или следующего hh
                    hh_intersection = any(highs[idx] > highs[hh] for hh in hh_start_array if hh > idx)
                    midpoint_intersection = lows[idx] <= midpoint

                    result = {
                        "idx": idx,
                        "hh_intersection": hh_intersection,
                        "midpoint_intersection": midpoint_intersection,
                        "crossed_first": "midpoint" if midpoint_intersection and not hh_intersection else "hh" if hh_intersection and not midpoint_intersection else "both" if midpoint_intersection and hh_intersection else "none"
                    }

                    results.append(result)

                return results

            # @staticmethod
            # def calculate_rsi(period=14):
            #     tv = TvDatafeed()
            #     history_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)
            #     closes = history_data["close"].tolist()
            #     df = pd.DataFrame(closes, columns=['close'])
            #
            #     if len(closes) < period:
            #         logger.error(f"Not enough data to calculate RSI for the given period: {period}")
            #         return None
            #
            #     delta = np.diff(closes)
            #     gains = delta.clip(min=0)
            #     losses = -delta.clip(max=0)
            #
            #     avg_gain = np.mean(gains[:period])
            #     avg_loss = np.mean(losses[:period])
            #
            #     rs = avg_gain / avg_loss if avg_loss != 0 else np.inf
            #     rsi = np.array([100 - (100 / (1 + rs))])
            #     rsi_timestamps = [timestamps[period]]  # Начало с периода
            #
            #     for i in range(period, len(closes) - 1):
            #         avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            #         avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
            #
            #         rs = avg_gain / avg_loss if avg_loss != 0 else np.inf
            #         rsi = np.append(rsi, 100 - (100 / (1 + rs)))
            #         rsi_timestamps.append(timestamps[i + 1])
            #
            #     return rsi, rsi_timestamps

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
            def plot_mfi(hist_data):
                plt.figure(figsize=(10, 6))
                mfi_line, = plt.plot(hist_data.index, hist_data['MFI'], label='Money Flow Index',
                                     color='blue')  # Сохраняем линию как объект

                # Добавляем горизонтальные линии для обозначения уровней перекупленности и перепроданности
                plt.axhline(80, linestyle='--', color='r', label='Overbought (80)')
                plt.axhline(20, linestyle='--', color='g', label='Oversold (20)')

                # Добавление лейбла с текущей ценой в конце линии MFI
                last_date = hist_data.index[-1]  # Последняя дата
                last_mfi = hist_data['MFI'].iloc[-1]  # Последнее значение MFI
                plt.text(last_date, last_mfi, f' {last_mfi:.2f}', color='blue', verticalalignment='center')

                plt.title('Money Flow Index (MFI)')
                plt.legend()
                plt.show()

            @staticmethod
            def plot_mfi_over_timeframes(timeframes, symbol, exchange, n_bars, tv):
                fig, ax = plt.subplots(figsize=(12, 8))
                mfi_dictionaries = {}
                colors = ['red', 'blue', 'green', 'purple']  # Цвета для различных таймфреймов

                for timeframe, color in zip(timeframes, colors):
                    hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                    if not hist_data.empty:
                        hist_data_with_mfi = TvDatafeed.calculate_mfi(hist_data)
                        ax.plot(hist_data_with_mfi.index, hist_data_with_mfi['MFI'], label=f'MFI {timeframe}',
                                color=color)
                        mfi_dictionaries[timeframe] = hist_data_with_mfi['MFI'].iloc[-1]  # Сохраняем последнее значение MFI

                ax.set_title('MFI Comparison Across Different Timeframes')
                ax.legend()
                plt.show()
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
                """Визуализирует MACD, его сигнал и гистограмму."""
                plt.figure(figsize=(14, 7))

                plt.plot(hist_data.index, macd, label='MACD', color='b')
                plt.plot(hist_data.index, signal, label='Signal', color='orange')
                plt.bar(hist_data.index, hist, label='Histogram', color='grey', alpha=0.3)

                # Получаем последние дату и значения для MACD и сигнала
                last_date = hist_data.index[-1]
                last_macd = macd.iloc[-1]
                last_signal = signal.iloc[-1]

                plt.text(last_date, last_macd, f'{last_macd:.2f}', color='b', verticalalignment='center',
                         horizontalalignment='right')
                plt.text(last_date, last_signal, f'{last_signal:.2f}', color='orange', verticalalignment='center',
                         horizontalalignment='right')

                # Добавляем горизонтальные линии для обозначения уровней перекупленности и перепроданности (опционально)
                plt.axhline(0, linestyle='--', color='grey', alpha=0.5)  # Zero Line

                plt.title('MACD, Signal and Histogram')
                plt.legend()
                plt.show()

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
            def plot_st(hist_data, k, d):
                """Plots the Stochastic Oscillator (%K and %D)."""
                plt.figure(figsize=(14, 7))

                plt.plot(hist_data.index, k, label='%K', color='#2962FF')
                plt.plot(hist_data.index, d, label='%D', color='#FF6D00')

                plt.axhline(80, color='#787B86', linestyle='--', label='Upper Band')
                plt.axhline(50, color='#787B86', linestyle='--', alpha=0.5, label='Middle Band')
                plt.axhline(20, color='#787B86', linestyle='--', label='Lower Band')
                plt.fill_between(hist_data.index, 20, 80, color='skyblue', alpha=0.4)

                # Get the last date and values for %K and %D
                last_date = hist_data.index[-1]
                last_k = k.iloc[-1]
                last_d = d.iloc[-1]

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
                """Plots the Bollinger Bands."""
                plt.figure(figsize=(14, 7))

                plt.plot(hist_data.index, hist_data['close'], label='Close Price', color='black')
                plt.plot(hist_data.index, sma, label='SMA', color='#2962FF')
                plt.plot(hist_data.index, upper_band, label='Upper Band', color='#F23645')
                plt.plot(hist_data.index, lower_band, label='Lower Band', color='#089981')

                plt.fill_between(hist_data.index, lower_band, upper_band, color='skyblue', alpha=0.4,
                                 label='Band Range')

                # Get the last date and values for SMA, upper_band and lower_band
                last_date = hist_data.index[-1]
                last_sma = sma.iloc[-1]
                last_upper = upper_band.iloc[-1]
                last_lower = lower_band.iloc[-1]

                # Add text labels for SMA, upper_band and lower_band
                plt.text(last_date, last_sma, f'{last_sma:.2f}', color='#2962FF', verticalalignment='center',
                         horizontalalignment='right')
                plt.text(last_date, last_upper, f'{last_upper:.2f}', color='#F23645', verticalalignment='center',
                         horizontalalignment='right')
                plt.text(last_date, last_lower, f'{last_lower:.2f}', color='#089981', verticalalignment='center',
                         horizontalalignment='right')

                plt.title('Bollinger Bands')
                plt.legend()
                plt.show()

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
                plt.show()

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


        if __name__ == "__main__":
            logging.basicConfig(level=logging.FATAL)
            for logger_name in ['matplotlib', 'urllib3']:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.WARNING)
            pd.set_option('display.max_rows', None)
            coins = ["BTCUSDT", "ETHUSDT"]

            value = 1000
            value_3_percent = (value / 100) * 3
            itog = 1000

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

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_3_minute, n_bars)

                    plt.figure(figsize=(24, 14), clear=True)
                    fig, ax = plt.subplots(figsize=(24, 14), clear=True)
                    plt.title(f'Graph for {symbol}', fontsize=20, loc='center')

                    rejection_blocks = tv.find_rejection_blocks(opens, closes)
                    # print("Rejection blocks found at indexes:", rejection_blocks)

                    bar_width = 0.5
                    colors = ['green' if open_price < close_price else 'red' for open_price, close_price in
                              zip(opens, closes)]

                    ax.vlines(x=range(len(hist_data)), ymin=lows, ymax=highs, color='black', linewidth=0.5, zorder=0)
                    ax.bar(range(len(hist_data)), abs(np.array(opens) - np.array(closes)),
                           bottom=np.minimum(opens, closes),
                           color=colors, width=0.7, zorder=1)

                    hh_ind, hl_ind, lh_ind, ll_ind, bull_bos_ends, bear_bos_ends = tv.update_prices(highs, lows,
                                                                                                    range(len(highs)),
                                                                                                    ax)
                    # print("HH indices:", hh_ind)  # Print HH indices
                    # print("HL indices:", hl_ind)  # Print HH indices

                    midnight_indices = [i for i, timestamp in enumerate(timestamps) if
                                        timestamp.hour == 0 and timestamp.minute == 0]

                    daily_max_highs = []
                    daily_min_lows = []
                    three_minute_long = []
                    three_minute_short = []
                    three_minute_short_baz = {}
                    three_minute_long_baz = {}
                    rr_max_day = {}
                    rr_min_day = {}
                    rr_sum = []
                    all_rr_values = []

                    highs_after_hh = []
                    lows_after_ll = []

                    hl_array = []
                    hl_start_array = []
                    hl_price_array = {}
                    hh_array = []
                    hh_start_array = []
                    hh_price_array = {}
                    lh_array = []
                    lh_start_array = []
                    lh_price_array = {}
                    ll_array = []
                    ll_start_array = []
                    ll_price_array = {}

                    point_vhod_short = {}
                    point_vhod_long = {}
                    point_liqvidation_short = {}
                    point_liqvidation_long = {}
                    rr_array_short = {}
                    rr_array_long = {}

                    point_vhod_short_max = {}
                    point_vhod_long_max = {}
                    point_liqvidation_short_max = {}
                    point_liqvidation_long_max = {}
                    rr_array_short_max = {}
                    rr_array_long_max = {}

                    for hl in hl_ind:
                        for i in range(hl + 1, len(lows)):
                            if lows[i] < lows[hl]:
                                hl_array.append(i)
                                hl_price_array[i] = lows[hl]
                                hl_start_array.append(hl)
                                break

                    for lh in lh_ind:
                        for i in range(lh + 1, len(highs)):
                            if highs[i] > highs[lh]:
                                lh_array.append(i)
                                lh_price_array[i] = highs[lh]
                                lh_start_array.append(lh)
                                break

                    for hh in hh_ind:
                        for i in range(hh + 1, len(lows)):
                            if lows[i] < lows[hh]:
                                hh_array.append(i)
                                hh_price_array[i] = highs[hh]
                                hh_start_array.append(hh)
                                break
                    for ll in ll_ind:
                        for i in range(ll + 1, len(highs)):
                            if highs[i] > highs[ll]:
                                ll_array.append(i)
                                ll_price_array[i] = highs[ll]
                                ll_start_array.append(ll)
                                break

                    # Создаем список максимумов и минимумов для каждого дня
                    for start, end in zip(midnight_indices[:-1], midnight_indices[1:]):
                        daily_max_highs.append(max(highs[start:end]))
                        daily_min_lows.append(min(lows[start:end]))

                    # Проверяем, превышают ли текущие значения максимумы или минимумы предыдущего дня
                    for i in range(1, len(midnight_indices)):
                        day_start = midnight_indices[i]
                        day_end = midnight_indices[i + 1] if i + 1 < len(midnight_indices) else len(closes)

                        previous_day_max = daily_max_highs[i - 1]
                        previous_day_min = daily_min_lows[i - 1]
                        midpoint = (previous_day_max + previous_day_min) / 2
                        max_broken = False
                        min_broken = False
                        day_max = []
                        day_min = []

                        for j in range(day_start, day_end):
                            if not max_broken and highs[j] > previous_day_max:
                                ax.scatter(j, highs[j], color='blue', s=100,
                                           label='Break Above Max' if not max_broken else "")
                                day_max.append(j)
                                max_broken = True
                            if not min_broken and lows[j] < previous_day_min:
                                ax.scatter(j, lows[j], color='orange', s=100,
                                           label='Break Below Min' if not min_broken else "")
                                day_min.append(j)
                                min_broken = True

                            if max_broken and min_broken:
                                break

                        for max_idx in day_max:
                            if highs[max_idx] > daily_max_highs[i - 1]:
                                ax.scatter(max_idx, highs[max_idx], color='blue', s=100, label='Break Above Max')
                                three_minute_short.append(max_idx)
                                nearest_hh_idx = min([hh for hh in hh_start_array if hh >= max_idx], default=None)

                                # Проверяем, есть ли следующий hh после найденного nearest_hh_idx
                                if nearest_hh_idx is not None:
                                    next_hh_candidates = [hh for hh in hh_start_array if hh > nearest_hh_idx]
                                    if next_hh_candidates:
                                        next_hh_idx = next_hh_candidates[
                                            0]  # Предполагаем, что hh_start_array отсортирован по возрастанию
                                        # Сравниваем высоты текущего и следующего hh
                                        if highs[next_hh_idx] > highs[nearest_hh_idx]:
                                            nearest_hh_idx = next_hh_idx  # Обновляем, если следующий hh выше текущего

                                nearest_hl_idx = min([hl for hl in hl_array if hl > max_idx] + [lh for lh in lh_array if
                                                                                                lh > max_idx] + [ll for
                                                                                                                 ll in
                                                                                                                 ll_array
                                                                                                                 if
                                                                                                                 ll > max_idx],
                                                     default=None)
                                if nearest_hl_idx is not None:
                                    hl_price = hl_price_array[nearest_hl_idx] if nearest_hl_idx in hl_price_array else \
                                    lows[nearest_hl_idx]
                                    ax.scatter(nearest_hl_idx, hl_price, color='grey', s=300, label='Low Below HL Low')
                                    ax.plot([max_idx, nearest_hl_idx], [highs[max_idx], hl_price], color='purple',
                                            linestyle='--')
                                    highs_after_hh.append(nearest_hl_idx)
                                    if nearest_hl_idx is not None:
                                        hl_price = hl_price_array.get(nearest_hl_idx, lows[nearest_hl_idx])
                                        hh_price = hh_price_array.get(nearest_hh_idx, highs[
                                            nearest_hh_idx]) if nearest_hh_idx is not None else None

                                        max_high_value = 1
                                        max_high_index = nearest_hl_idx

                                        if nearest_hh_idx is not None:
                                            for idx in range(nearest_hl_idx + 1, len(highs)):
                                                if highs[idx] > max_high_value and highs[idx] <= highs[nearest_hh_idx]:
                                                    max_high_value = highs[idx]
                                                    max_high_index = idx

                                                # Условия остановки поиска
                                                if highs[idx] <= midpoint or highs[idx] >= hh_price:
                                                    break

                                        price_muv_1pct_short = round(hl_price / 100, 3)
                                        price_muv_liqvidation_short = round((hh_price / price_muv_1pct_short) - 100,
                                                                            3) if hh_price else None
                                        price_muv_profit_short = round(100 - (midpoint / price_muv_1pct_short), 3)
                                        RR_short = round(price_muv_profit_short / price_muv_liqvidation_short,
                                                         3) if price_muv_liqvidation_short else None
                                        point_vhod_short[nearest_hl_idx] = hl_price
                                        if nearest_hl_idx is not None and nearest_hh_idx is not None:
                                            point_liqvidation_short[nearest_hl_idx] = hh_price if hh_price else highs[
                                                nearest_hh_idx]
                                        rr_array_short[nearest_hl_idx] = RR_short if RR_short else None
                                        rr_sum.append(RR_short if RR_short else 0)

                                        price_muv_1pct_short_max = round(max_high_value / 100, 3)
                                        price_muv_liqvidation_short_max = round(
                                            (highs[nearest_hh_idx] / price_muv_1pct_short_max) - 100,
                                            3) if hh_price else None
                                        price_muv_profit_short_max = round(100 - (midpoint / price_muv_1pct_short_max),
                                                                           3)
                                        RR_short_max = round(
                                            price_muv_profit_short_max / price_muv_liqvidation_short_max,
                                            3) if price_muv_liqvidation_short_max else None
                                        point_vhod_short_max[nearest_hl_idx] = max_high_value
                                        if nearest_hh_idx is not None and nearest_hl_idx is not None:
                                            point_liqvidation_short_max[nearest_hl_idx] = hh_price if hh_price else \
                                            highs[
                                                nearest_hh_idx]
                                        rr_array_short_max[nearest_hl_idx] = RR_short_max if RR_short_max else None
                                        rr_sum.append(RR_short if RR_short else 0)

                        for min_idx in day_min:
                            if lows[min_idx] < daily_min_lows[i - 1]:
                                ax.scatter(min_idx, lows[min_idx], color='blue', s=100, label='Break Below Min')
                                three_minute_long.append(min_idx)

                                nearest_ll_idx = min([ll for ll in ll_start_array if ll >= min_idx], default=None)
                                nearest_lh_idx = min([lh for lh in lh_array if lh > min_idx] + [hl for hl in hl_array if
                                                                                                hl > min_idx] + [hh for
                                                                                                                 hh in
                                                                                                                 hh_array
                                                                                                                 if
                                                                                                                 hh > min_idx],
                                                     default=None)

                                if nearest_ll_idx is not None:
                                    next_ll_candidates = [ll for ll in ll_start_array if ll > nearest_ll_idx]
                                    if next_ll_candidates:
                                        next_ll_idx = next_ll_candidates[
                                            0]  # Предполагаем, что hh_start_array отсортирован по возрастанию
                                        # Сравниваем высоты текущего и следующего hh
                                        if lows[next_ll_idx] < lows[nearest_ll_idx]:
                                            nearest_ll_idx = next_ll_idx  # Обновляем, если следующий hh выше текущего

                                if nearest_lh_idx is not None:
                                    lh_price = lh_price_array[nearest_lh_idx] if nearest_lh_idx in lh_price_array else \
                                    highs[nearest_lh_idx]

                                    ax.scatter(nearest_lh_idx, lh_price, color='grey', s=300,
                                               label='High Above LH High')
                                    ax.plot([min_idx, nearest_lh_idx], [lows[min_idx], lh_price], color='purple',
                                            linestyle='--')

                                    lows_after_ll.append(nearest_lh_idx)

                                    lh_price = lh_price_array.get(nearest_lh_idx, highs[nearest_lh_idx])
                                    ll_price = ll_price_array.get(nearest_ll_idx, lows[
                                        nearest_ll_idx]) if nearest_ll_idx is not None else None

                                    min_low_value = lows[nearest_lh_idx]
                                    min_low_index = nearest_lh_idx

                                    # Поиск максимального highs в интервале
                                    for idx in range(nearest_lh_idx + 1, len(lows)):
                                        if lows[idx] < min_low_value and lows[idx] >= lows[nearest_ll_idx]:
                                            min_low_value = lows[idx]
                                            min_low_index = idx

                                        # Условия остановки поиска
                                        if lows[idx] <= midpoint or lows[idx] <= ll_price:
                                            break

                                    price_muv_1pct_long = round(highs[nearest_lh_idx] / 100, 3)
                                    price_muv_liqvidation_long = round(
                                        100 - (highs[nearest_ll_idx] / price_muv_1pct_long), 3)
                                    price_muv_profit_long = round((midpoint / price_muv_1pct_long) - 100, 3)
                                    RR_long = round(price_muv_profit_long / price_muv_liqvidation_long, 3)
                                    point_vhod_long[nearest_lh_idx] = highs[nearest_lh_idx]
                                    point_liqvidation_long[nearest_lh_idx] = lows[nearest_ll_idx]
                                    rr_array_long[nearest_lh_idx] = RR_long
                                    rr_sum.append(RR_long)

                                    price_muv_1pct_long_max = round(highs[nearest_lh_idx] / 100, 3)
                                    price_muv_liqvidation_long_max = round(
                                        100 - (highs[nearest_ll_idx] / price_muv_1pct_long_max), 3)
                                    price_muv_profit_long_max = round((midpoint / price_muv_1pct_long_max) - 100, 3)
                                    RR_long_max = round(price_muv_profit_long / price_muv_liqvidation_long_max, 3)
                                    point_vhod_long_max[nearest_lh_idx] = highs[nearest_lh_idx]
                                    point_liqvidation_long_max[nearest_lh_idx] = lows[nearest_ll_idx]
                                    rr_array_long_max[nearest_lh_idx] = RR_long_max
                                    rr_sum.append(RR_long)

                    for idx, (start, end) in enumerate(zip(midnight_indices[:-1], midnight_indices[1:]), 1):
                        max_high = max(highs[start:end])
                        max_high_idx = start + highs[start:end].index(max_high)

                        for i in range(max_high_idx, len(highs)):
                            if highs[i] > max_high:
                                end_idx = i - 1
                                break
                        else:
                            end_idx = len(highs) - 1

                        ax.hlines(max_high, max_high_idx, end_idx, colors='black', linestyles='dotted', linewidth=2)

                        mid_point = (max_high_idx + end_idx) // 2
                        ax.text(mid_point, max_high, str(len(midnight_indices) - idx), color='black', ha='center',
                                va='bottom')

                    for idx, (start, end) in enumerate(zip(midnight_indices[:-1], midnight_indices[1:]), 1):
                        min_low = min(lows[start:end])
                        min_low_idx = start + lows[start:end].index(min_low)

                        for i in range(min_low_idx, len(lows)):
                            if lows[i] < min_low:
                                end_idx = i - 1
                                break
                        else:
                            end_idx = len(lows) - 1

                        ax.hlines(min_low, min_low_idx, end_idx, colors='grey', linestyles='dotted', linewidth=2)

                        mid_point = (min_low_idx + end_idx) // 2
                        ax.text(mid_point, min_low, str(len(midnight_indices) - idx), color='red', ha='center',
                                va='top')

                    handles, labels = ax.get_legend_handles_labels()
                    by_label = dict(zip(labels, handles))
                    ax.legend(by_label.values(), by_label.keys())

                    ax.set_xlim([0, len(hist_data)])
                    ax.set_ylim([min(lows) * 0.95, max(highs) * 1.05])

                    # plt.scatter(hh_ind, [highs[i] for i in hh_ind], color='green', label='HH')
                    # plt.scatter(hl_ind, [lows[i] for i in hl_ind], color='blue', label='HL')
                    # plt.scatter(lh_ind, [highs[i] for i in lh_ind], color='orange', label='LH')
                    # plt.scatter(ll_ind, [lows[i] for i in ll_ind], color='red', label='LL')

                    handles, labels = ax.get_legend_handles_labels()
                    by_label = dict(zip(labels, handles))
                    ax.legend(by_label.values(), by_label.keys())

                    ax.set_xlim([0, len(hist_data)])
                    ax.set_ylim([min(lows), max(highs)])

                    results = tv.test_highs_after_hh(highs_after_hh, hh_start_array, highs, lows, daily_max_highs,
                                                     daily_min_lows)

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_4_hour, n_bars)

                    if hist_data is not None:
                        sma, upper_band, lower_band = tv.calculate_bb(hist_data)
                        tv.plot_bb(hist_data, sma, upper_band, lower_band)

                        # last_upper = upper_band[-1]
                        # last_lower = lower_band[-1]

                    if hist_data is not None:
                        k_smooth, d = tv.calculate_st(hist_data)
                        tv.plot_st(hist_data, k_smooth, d)

                    if hist_data is not None:
                        hist_data_with_mfi = TvDatafeed.calculate_mfi(hist_data)
                        tv.plot_mfi(hist_data_with_mfi)

                    if hist_data is not None:
                        macd, signal, hist = tv.calculate_macd(hist_data)
                        tv.plot_macd(hist_data, macd, signal, hist)

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

                    timeframes = [Interval.in_4_hour, Interval.in_2_hour, Interval.in_1_hour, Interval.in_30_minute, Interval.in_15_minute]
                    rsi_dictionaries = {}  # Словарь для сохранения RSI значений для каждого таймфрейма
                    colors = ['red', 'blue', 'green', 'purple']  # Цвета для различных таймфреймов

                    fig, ax = plt.subplots(figsize=(12, 8))  # Создание одной фигуры и осей

                    for timeframe, color in zip(timeframes, colors):
                        # Получение исторических данных для данного таймфрейма
                        hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                        if hist_data is not None and not hist_data.empty:
                            # Расчёт RSI
                            rsi = tv.calculate_rsi(hist_data)

                            if rsi is not None and not rsi.empty:
                                # Отрисовка RSI на общих осях, каждый в своём цвете
                                ax.plot(hist_data.index[-55:], rsi[-55:], label=f'RSI {timeframe}', color=color)

                                # Добавление текста с последним значением RSI
                                last_date = hist_data.index[-1]
                                last_rsi = rsi.iloc[-1]
                                ax.text(last_date, last_rsi, f'{last_rsi:.2f}', color=color, ha='right', va='center')

                                # Сохранение значений RSI в словарь для текущего таймфрейма
                                rsi_dict = {date: rsi_value for date, rsi_value in
                                            zip(hist_data.index[-55:], rsi[-55:])}
                                rsi_dictionaries[timeframe] = rsi_dict  # Сохраняем словарь в главный словарь
                            else:
                                print(f"RSI calculation failed for {timeframe}")
                        else:
                            print(f"No historical data available for {timeframe}")

                    ax.set_title('RSI Comparison Across Different Timeframes')
                    ax.legend()
                    plt.show()

                    for timeframe in timeframes:
                        # Получение исторических данных для данного таймфрейма
                        hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)

                        if hist_data is not None and not hist_data.empty:
                            # Расчёт RSI
                            rsi = tv.calculate_rsi(hist_data)

                            if rsi is not None and not rsi.empty:
                                # Обновление словаря с последними 5 значениями RSI
                                rsi_dictionaries[timeframe] = rsi.iloc[-5:].to_dict()

                    # Проверка условий для RSI на различных таймфреймах
                    if all(timeframe in rsi_dictionaries for timeframe in timeframes):
                        rsi_15m = rsi_dictionaries[Interval.in_15_minute]
                        rsi_30m = rsi_dictionaries[Interval.in_30_minute]
                        rsi_1h = rsi_dictionaries[Interval.in_1_hour]
                        rsi_2h = rsi_dictionaries[Interval.in_2_hour]
                        rsi_4h = rsi_dictionaries[Interval.in_4_hour]

                        # Извлечение последних значений RSI для каждого таймфрейма
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


                            def save_comparisons_to_json(comparisons, last_rsi_1h):
                                data_to_save = {
                                    "comparisons": comparisons,
                                    "last_rsi_1h": last_rsi_1h
                                }
                                with open('rsi_comparisons.json', 'w') as json_file:
                                    json.dump(data_to_save, json_file, indent=4)


                            save_comparisons_to_json(comparisons, last_rsi_1h)


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
                                        'k_values': k.iloc[-50:].to_dict(),  # Сохраняем последние 5 значений %K
                                        'd_values': d.iloc[-50:].to_dict()  # Сохраняем последние 5 значений %D
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


                    timeframes = [Interval.in_15_minute, Interval.in_30_minute, Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour]
                    n_bars = 200  # Количество баров для анализа
                    stoch_data = collect_stoch_data(tv, "BTCUSDT", "BINANCE", timeframes, n_bars)
                    stoch_comparisons = compare_stoch_values(stoch_data)
                    print(stoch_comparisons)

                    def plot_stochastic_oscillator(stoch_dictionaries, timeframes):
                        fig, ax = plt.subplots(figsize=(12, 8))
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

                                if symbol == "BTCUSDT":

                                    if timeframe == Interval.in_1_hour:  # Указываем интересующий интервал
                                        last_values['last_k'] = k_values[-1]
                                        last_values['last_d'] = d_values[-1]

                                ax.plot(dates, k_values, label=f'%K {timeframe}', color=color_k)
                                ax.plot(dates, d_values, label=f'%D {timeframe}', color=color_d)

                        ax.set_title('Stochastic Oscillator Across Different Timeframes')
                        ax.legend(loc='upper left')
                        plt.show()

                        return last_values


                    if symbol == "BTCUSDT":
                        last_stoch_values = plot_stochastic_oscillator(stoch_data, timeframes)

                        # Включение последних значений в JSON для сохранения
                        stoch_comparisons['last_values'] = last_stoch_values

                        with open('stoch_comparisons.json', 'w') as json_file:
                            json.dump(stoch_comparisons, json_file, indent=4)

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

                            # Построение графика с использованием matplotlib
                            plt.figure(figsize=(14, 7))
                            plt.plot(close.index, HULL, label='Hull MA', color='black')  # Линия тренда
                            for i in range(2, len(HULL)):
                                plt.plot(close.index[i - 2:i], HULL[i - 2:i], color=hull_color[i], linewidth=2)

                            plt.title('Hull Suite by InSilico')
                            plt.legend()
                            plt.show()

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

                    bars_limit = {
                        'in_1_hour': 30,
                        'in_2_hour': 30,
                        'in_4_hour': 30,
                        'in_daily': 30
                    }


                    def find_divergences(data, indicator, pivot_period, max_pivot_points, max_bars, limit=None):
                        divergences = []
                        start_index = max(pivot_period, len(data) - limit) if limit else pivot_period
                        for i in range(start_index, len(data) - pivot_period):
                            pivot_low = data['low'][i - pivot_period:i + pivot_period].min()
                            pivot_high = data['high'][i - pivot_period:i + pivot_period].max()
                            if data['low'][i] == pivot_low or data['high'][i] == pivot_high:
                                for j in range(1, max_pivot_points):
                                    if i - j >= 0 and i + j < len(data):
                                        if data[indicator][i] > data[indicator][i - j] and data['close'][i] < \
                                                data['close'][i - j]:
                                            divergences.append((i, 'bullish', indicator))
                                        if data[indicator][i] < data[indicator][i - j] and data['close'][i] > \
                                                data['close'][i - j]:
                                            divergences.append((i, 'bearish', indicator))
                        return divergences


                    timeframes = [Interval.in_1_hour, Interval.in_2_hour, Interval.in_4_hour, Interval.in_daily]
                    divergences_results = {}

                    for timeframe in timeframes:
                        timeframe_str = str(timeframe).split('.')[1]
                        hist_data = tv.get_hist(symbol, exchange, timeframe, n_bars)
                        data = hist_data.copy()
                        data.index = pd.to_datetime(data.index, errors='coerce')

                        limit = bars_limit.get(timeframe_str)  # Получаем лимит для текущего таймфрейма

                        # Расчет индикаторов
                        data['rsi'] = ta.rsi(data['close'], length=14)
                        macd = ta.macd(data['close'], fast=12, slow=26, signal=9)
                        data['macd'] = macd['MACD_12_26_9']
                        data['macdhist'] = macd['MACDh_12_26_9']
                        data['obv'] = ta.obv(data['close'], data['volume'])
                        stoch = ta.stoch(data['high'], data['low'], data['close'], k=14, d=3, smooth_k=3)
                        data['stoch_k'] = stoch['STOCHk_14_3_3']
                        data['stoch_d'] = stoch['STOCHd_14_3_3']

                        indicators = ['rsi', 'macd', 'macdhist', 'obv', 'stoch_k', 'stoch_d']
                        all_divergences = {
                            indicator: find_divergences(data, indicator, 5, 10, 100, limit=limit) for indicator in
                            indicators
                        }

                        divergences_dict = {}
                        for indicator, divergences in all_divergences.items():
                            for index, div_type, ind in divergences:
                                if index not in divergences_dict:
                                    divergences_dict[index] = {'bullish': set(), 'bearish': set()}
                                divergences_dict[index][div_type].add(ind)

                        max_index = max(divergences_dict.keys(), default=None)

                        if max_index is not None:
                            last_divergences = divergences_dict[max_index]
                            divergences_results[timeframe_str] = {
                                'index': max_index,
                                'divergences': {
                                    'bullish': list(last_divergences['bullish']),
                                    'bearish': list(last_divergences['bearish'])
                                }
                            }

                    if symbol == "BTCUSDT":
                        with open('divergences_per_timeframe.json', 'w', encoding='utf-8') as f:
                            json.dump(divergences_results, f, indent=4)

                    print("Дивергенции по каждому таймфрейму сохранены в 'divergences_per_timeframe.json'.")

                    hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)

                    # Plotting divergences with annotations
                    plt.figure(figsize=(14, 7))
                    plt.plot(data['close'], label='Close Price')

                    for index, divs in divergences_dict.items():
                        if divs['bullish']:
                            plt.plot(data.index[index], data['close'][index], marker='^', color='g')
                            plt.annotate(f"Bullish: {len(divs['bullish'])}\n",
                                         xy=(data.index[index], data['close'][index]),
                                         xytext=(data.index[index], data['close'][index] + 5),
                                         arrowprops=dict(facecolor='green', shrink=0.05))

                        if divs['bearish']:
                            plt.plot(data.index[index], data['close'][index], marker='v', color='r')
                            plt.annotate(f"Bearish: {len(divs['bearish'])}\n",
                                         xy=(data.index[index], data['close'][index]),
                                         xytext=(data.index[index], data['close'][index] - 5),
                                         arrowprops=dict(facecolor='red', shrink=0.05))

                    plt.title('Price with Divergences')
                    plt.legend()
                    plt.show()


                    hist_data = tv.get_hist(symbol, exchange, Interval.in_3_minute, n_bars)


                    def update_three_minute_json(symbol, exchange, highs_after_hh, lows_after_ll, highs, lows,
                                                 point_vhod_short,
                                                 point_vhod_long, point_liqvidation_short, point_liqvidation_long,
                                                 rr_array_short,
                                                 rr_array_long, rr_array_long_max, rr_array_short_max):
                        file_path = 'three_minute.json'
                        try:
                            with open(file_path, 'r') as file:
                                data = json.load(file)
                                if not isinstance(data, list):
                                    data = []
                        except (FileNotFoundError, json.JSONDecodeError):
                            data = []

                        updated = False
                        for entry in data:
                            if entry['symbol'] == symbol:
                                updated = True
                                entry['highs_after_hh'] = [
                                    {
                                        'index': point,
                                        'low': lows[point] if point < len(lows) else None,
                                        'point_vhod': point_vhod_short.get(point),
                                        'point_liqvidation': point_liqvidation_short.get(point),
                                        'rr': rr_array_short.get(point),
                                        'rr_max': rr_array_short_max.get(point),
                                    }
                                    for point in highs_after_hh if point < len(highs)
                                ]
                                entry['lows_after_ll'] = [
                                    {
                                        'index': point,
                                        'high': highs[point] if point < len(highs) else None,
                                        'point_vhod': point_vhod_long.get(point),
                                        'point_liqvidation': point_liqvidation_long.get(point),
                                        'rr': rr_array_long.get(point),
                                        'rr_max': rr_array_long_max.get(point),
                                    }
                                    for point in lows_after_ll if point < len(lows)
                                ]

                        with open(file_path, 'w', encoding='utf-8') as file:
                            json.dump(data, file, ensure_ascii=False, indent=4)

                    update_three_minute_json(symbol, exchange, highs_after_hh, lows_after_ll, highs, lows,
                                             point_vhod_short,
                                             point_vhod_long, point_liqvidation_short, point_liqvidation_long,
                                             rr_array_short,
                                             rr_array_long, rr_array_long_max, rr_array_short_max)

                    plt.ion()
                    plt.draw()  # Обновление графика
                    plt.pause(0.1)  # Пауза, важна для обновления графики
                    plt.close()  # Закрытие текущей фигуры
                    time.sleep(10)

                    del hist_data, timestamps, highs, lows, opens, closes, volume, current_price
                    del rejection_blocks, open_figures, fig, ax

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
