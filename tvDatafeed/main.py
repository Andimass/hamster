import datetime
import enum
import json
import logging
import random
import re
import string

import numpy as np
import pandas as pd
from websocket import create_connection
import requests
import time
import matplotlib.pyplot as plt
import os

logger = logging.getLogger(__name__)

SUPER_TOCHKA_PATH = os.path.join(os.path.dirname(__file__), 'super_tochka.json')
LAST_COIN_INDEX_PATH = os.path.join(os.path.dirname(__file__), 'last_coin_index.txt')

username = 'masyuckevich12345@gmail.com'
password = 'LHJybrk777;'

def save_last_coin_index(index):
    with open(LAST_COIN_INDEX_PATH, 'w') as f:
        f.write(str(index))

def load_last_coin_index():
    if os.path.exists(LAST_COIN_INDEX_PATH):
        with open(LAST_COIN_INDEX_PATH, 'r') as f:
            return int(f.read())
    return 0

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
                    logger.warning("you are using nologin method, data you access may be limited")
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
                self.ws = create_connection("wss://data.tradingview.com/socket.io/websocket", headers=self.__ws_headers, timeout=self.__ws_timeout)

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
                    data = pd.DataFrame(data, columns=["datetime", "open", "high", "low", "close", "volume"]).set_index("datetime")
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

            def get_hist(self, symbol: str, exchange: str = "NSE", interval: Interval = Interval.in_daily, n_bars: int = 10, fut_contract: int = None, extended_session: bool = False) -> pd.DataFrame:
                symbol = self.__format_symbol(symbol=symbol, exchange=exchange, contract=fut_contract)
                interval = interval.value
                self.__create_connection()
                self.__send_message("set_auth_token", [self.token])
                self.__send_message("chart_create_session", [self.chart_session, ""])
                self.__send_message("quote_create_session", [self.session])
                self.__send_message("quote_set_fields", [
                    self.session, "ch", "chp", "current_session", "description", "local_description", "language", "exchange", "fractional", "is_tradable", "lp", "lp_time", "minmov", "minmove2", "original_name", "pricescale", "pro_name", "short_name", "type", "update_mode", "volume", "currency_code", "rchp", "rtc",
                ])
                self.__send_message("quote_add_symbols", [self.session, symbol, {"flags": ["force_permission"]}])
                self.__send_message("quote_fast_symbols", [self.session, symbol])
                self.__send_message("resolve_symbol", [self.chart_session, "symbol_1", '={"symbol":"' + symbol + '","adjustment":"splits","session":' + ('"regular"' if not extended_session else '"extended"') + "}",])
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


                fifteen_data = tv.get_hist(symbol, exchange, Interval.in_15_minute, n_bars * 4)
                if fifteen_data is None:
                    logger.error(f"Failed to retrieve 15-minute data for {symbol}")
                    return None
                fifteen_highs = fifteen_data["high"].tolist()
                fifteen_lows = fifteen_data["low"].tolist()
                fifteen_opens = fifteen_data["open"].tolist()
                fifteen_closes = fifteen_data["close"].tolist()

                imbalance_zones_green_15_min = []
                imbalance_zones_red_15_min = []
                m = len(fifteen_highs)

                for i in range(2, m):
                    if fifteen_lows[i] > fifteen_highs[i - 2]:
                        valid = True
                        for j in range(i + 1, m):
                            if fifteen_highs[i - 2] > fifteen_lows[j]:
                                valid = True
                                break
                        if valid:
                            imbalance_zones_green_15_min.append((i - 2, i))

                for i in range(2, m):
                    if fifteen_highs[i] < fifteen_lows[i - 2]:
                        valid = True
                        for j in range(i + 1, m):
                            if fifteen_lows[i - 2] < fifteen_highs[j]:
                                valid = True
                                break
                        if valid:
                            imbalance_zones_red_15_min.append((i - 2, i))

                imbalance_zones_red_4h = []
                imbalance_zones_green_4h = []
                green_zones_ranges = []
                red_zones_ranges = []
                green_zones_50pct = []
                red_zones_50pct = []
                rb = []
                rb_ranges = []

                for i in range(len(four_hour_opens) - 1):
                    if four_hour_opens[i] < four_hour_closes[i] and four_hour_opens[i + 1] > four_hour_closes[i + 1]:
                        if four_hour_closes[i + 1] < four_hour_opens[i]:
                            rb.append(i)
                            rb_ranges.append((four_hour_highs[i], four_hour_lows[i]))

                for i in range(2, n):
                    if four_hour_lows[i] > four_hour_highs[i - 2]:
                        valid = True
                        for j in range(i + 1, n):
                            if four_hour_highs[i - 2] > four_hour_lows[j]:
                                valid = True
                                break
                        if valid:
                            imbalance_zones_green_4h.append((i - 2, i))
                            green_range = (four_hour_highs[i - 2], four_hour_lows[i])
                            green_zones_ranges.append(green_range)

                            green_zones_50pct.append((green_range[0] + green_range[1]) / 2)

                for i in range(2, n):
                    if four_hour_highs[i] < four_hour_lows[i - 2]:
                        valid = True
                        for j in range(i + 1, n):
                            if four_hour_lows[i - 2] < four_hour_highs[j]:
                                valid = True
                                break
                        if valid:
                            imbalance_zones_red_4h.append((i - 2, i))
                            red_range = (four_hour_lows[i - 2], four_hour_highs[i])
                            red_zones_ranges.append(red_range)

                            red_zones_50pct.append((red_range[0] + red_range[1]) / 2)

                green_crossings = []
                red_crossings = []

                green_crossing_imbalances = {}  # To store indices of imbalances crossed by green crossings
                red_crossing_imbalances = {}  # To store indices of imbalances crossed by red crossings

                for zone, pct_value in zip(imbalance_zones_green_4h, green_zones_50pct):
                    start_idx, end_idx = zone
                    end_time = four_hour_timestamps[end_idx]

                    for i, time in enumerate(hourly_timestamps):
                        if time > end_time and lowest[i] < pct_value:
                            green_crossings.append(i)
                            green_crossing_imbalances[i] = {
                                'imbalance_index': (start_idx, end_idx),
                                'high': four_hour_highs[start_idx],
                                'low': four_hour_lows[end_idx]
                            }
                            break

                # Поиск пересечений для красных зон
                for zone, pct_value in zip(imbalance_zones_red_4h, red_zones_50pct):
                    start_idx, end_idx = zone
                    end_time = four_hour_timestamps[end_idx]
                    for i, time in enumerate(hourly_timestamps):
                        if time > end_time and highest[i] > pct_value:
                            red_crossings.append(i)
                            red_crossing_imbalances[i] = {
                                'imbalance_index': (start_idx, end_idx),
                                'high': four_hour_highs[end_idx],
                                'low': four_hour_lows[start_idx]
                            }
                            break

                return (imbalance_zones_green_4h, imbalance_zones_red_4h, green_zones_ranges,
                        red_zones_ranges, green_zones_50pct, red_zones_50pct, rb, rb_ranges, green_crossings, red_crossings, green_crossing_imbalances, red_crossing_imbalances)


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

            # @staticmethod
            # def update_prices(highs, lows, bar_indices, ax):
            #     high_prices_arr = [highs[0]] * 10
            #     high_indexs_arr = [bar_indices[0]] * 10
            #     low_prices_arr = [lows[0]] * 10
            #     low_indexs_arr = [bar_indices[0]] * 10
            #     high_ = False
            #     low_ = False
            #     sw_high_price = None
            #     sw_high_index = None
            #     sw_low_price = None
            #     sw_low_index = None
            #     prew_high_price = None
            #     prew_high_index = None
            #     prew_low_price = None
            #     prew_low_index = None
            #     bull_bos = False
            #     bear_bos = False
            #     l_h_line = None
            #     h_l_line = None
            #     hh = []
            #     hl = []
            #     ll = []
            #     lh = []
            #
            #     def plot_label(x, y, text, color):
            #         ax.text(x, y, text, fontsize=8, color='white', ha='center', va='center',
            #                 bbox=dict(facecolor=color, alpha=0.5))
            #
            #     def plot_line(start_idx, start_price, end_idx, end_price, color):
            #         return ax.plot([start_idx, end_idx], [start_price, end_price], color=color, linestyle='-')
            #
            #     def delete_line(line):
            #         if line:
            #             line[0].remove()
            #
            #     for i in range(4, len(highs)):
            #         if highs[i - 2] >= highs[i - 1] and highs[i - 2] >= highs[i - 3] and highs[i - 2] >= highs[i] and highs[
            #             i - 2] >= highs[i - 4]:
            #             high_prices_arr.append(highs[i - 2])
            #             high_indexs_arr.append(bar_indices[i - 2])
            #             if high_ and (low_prices_arr and min(low_prices_arr) < sw_low_price or highs[i - 2] > sw_high_price):
            #                 if low_prices_arr:
            #                     prew_low_price = sw_low_price
            #                     prew_low_index = sw_low_index
            #                     u = 0
            #                     for r in range(len(low_prices_arr)):
            #                         if sw_high_index > low_indexs_arr[r]:
            #                             u += 1
            #                     slice_low_indexs_arr = low_indexs_arr[u:]
            #                     slice_low_prices_arr = low_prices_arr[u:]
            #                     for j in range(len(slice_low_prices_arr)):
            #                         if slice_low_prices_arr[j] == min(slice_low_prices_arr) and sw_high_price > min(
            #                                 slice_low_prices_arr):
            #                             sw_low_index = slice_low_indexs_arr[j]
            #                     if sw_high_price > min(slice_low_prices_arr):
            #                         sw_low_price = min(slice_low_prices_arr)
            #                         low_prices_arr.clear()
            #                         low_indexs_arr.clear()
            #                     h_l_line = plot_line(sw_high_index, sw_high_price, sw_low_index, sw_low_price, 'purple')
            #                     high_ = False
            #                     low_ = True
            #                     if sw_high_price >= prew_high_price:
            #                         # plot_label(sw_high_index, sw_high_price, "HH", 'blue')
            #                         hh.append(sw_high_index)  # Append HH index
            #                     if sw_high_price <= prew_high_price:
            #                         # plot_label(sw_high_index, sw_high_price, "LH", 'blue')
            #                         lh.append(sw_high_index)
            #             if sw_high_price is None:
            #                 sw_high_price = highs[i - 2]
            #                 sw_high_index = bar_indices[i - 2]
            #                 prew_high_price = sw_high_price
            #                 prew_high_index = sw_high_index
            #                 low_prices_arr.clear()
            #                 low_indexs_arr.clear()
            #                 high_ = True
            #
            #         if lows[i - 2] <= lows[i - 1] and lows[i - 2] <= lows[i - 3] and lows[i - 2] <= lows[i] and lows[i - 2] <= \
            #                 lows[i - 4]:
            #             low_prices_arr.append(lows[i - 2])
            #             low_indexs_arr.append(bar_indices[i - 2])
            #             if low_ and (high_prices_arr and max(high_prices_arr) > sw_high_price or lows[i - 2] < sw_low_price):
            #                 if high_prices_arr:
            #                     prew_high_price = sw_high_price
            #                     prew_high_index = sw_high_index
            #                     u = 0
            #                     for r in range(len(high_indexs_arr)):
            #                         if sw_low_index > high_indexs_arr[r]:
            #                             u += 1
            #                     slice_high_indexs_arr = high_indexs_arr[u:]
            #                     slice_high_prices_arr = high_prices_arr[u:]
            #                     for j in range(len(slice_high_prices_arr)):
            #                         if slice_high_prices_arr[j] == max(slice_high_prices_arr) and sw_low_price < max(
            #                                 slice_high_prices_arr):
            #                             sw_high_index = slice_high_indexs_arr[j]
            #                     if sw_low_price < max(slice_high_prices_arr):
            #                         sw_high_price = max(slice_high_prices_arr)
            #                         high_prices_arr.clear()
            #                         high_indexs_arr.clear()
            #                     if l_h_line and sw_high_price > prew_high_price:
            #                         delete_line(l_h_line)
            #                     l_h_line = plot_line(sw_low_index, sw_low_price, sw_high_index, sw_high_price, 'purple')
            #                     low_ = False
            #                     high_ = True
            #                     if sw_low_price >= prew_low_price:
            #                         # plot_label(sw_low_index, sw_low_price, "HL", 'red')
            #                         hl.append(sw_low_index)  # Append HL index
            #                     if sw_low_price <= prew_low_price:
            #                         # plot_label(sw_low_index, sw_low_price, "LL", 'red')
            #                         ll.append(sw_low_index)  # Append HL index
            #             if sw_low_price is None:
            #                 sw_low_price = lows[i - 2]
            #                 sw_low_index = bar_indices[i - 2]
            #                 prew_low_price = sw_low_price
            #                 prew_low_index = sw_low_index
            #                 high_prices_arr.clear()
            #                 high_indexs_arr.clear()
            #                 low_ = True
            #
            #         if sw_high_price is not None and highs[i] > sw_high_price:
            #             if not bull_bos:
            #                 bull_bos = True
            #                 bear_bos = False
            #                 ax.plot([sw_high_index, bar_indices[i]], [sw_high_price, sw_high_price], color='g', linestyle='-')
            #
            #         if sw_low_price is not None and lows[i] < sw_low_price:
            #             if not bear_bos:
            #                 bear_bos = True
            #                 bull_bos = False
            #                 ax.plot([sw_low_index, bar_indices[i]], [sw_low_price, sw_low_price], color='r', linestyle='-')
            #
            #     return hh, hl, ll, lh

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
            def test_price_behavior(highs, lows, closes, next_hh_after_crossing):
                tests = []  # Изменил results на tests
                value = 1000
                for crossing_index, indices in next_hh_after_crossing.items():

                    if indices and len(indices) == 2 and None not in indices:
                        hh, hl = indices
                        if hh + 10 < len(closes):
                            average_price = tv.calculate_average(highs, lows, hh, hl)
                            if isinstance(average_price, float):
                                future_close = closes[hh + 10]
                                percentage_difference = ((future_close - average_price) / average_price) * 100
                                if future_close < hh:
                                    test = "успех"  # Изменил result на test
                                    value += value * ((abs(percentage_difference) / 100))
                                else:
                                    test = "не удача"
                                    value -= value * ((abs(percentage_difference) / 100))
                                tests.append((crossing_index, hh, hl, average_price, future_close, test))
                            else:
                                tests.append((crossing_index, hh, hl, "Ошибка в расчете средней цены", None, "не применимо"))
                        else:
                            tests.append((crossing_index, hh, hl, "Выход за пределы данных", None, "не применимо"))
                    else:
                        tests.append(
                            (crossing_index, "Ошибка данных", None, "Недостаточно данных для индексов", None, "не применимо"))
                success_count = sum(1 for _, _, _, _, _, result in tests if result == "успех")
                failure_count = sum(1 for _, _, _, _, _, result in tests if result == "не удача")

                return tests, success_count, failure_count, value

            @staticmethod
            def find_pivots(data, period=2, is_high=True):
                length = len(data)
                pivots = np.full(length, np.nan)
                for i in range(period, length - period):
                    window = data[i - period:i + period + 1]
                    if is_high:
                        if data[i] == max(window):
                            pivots[i] = data[i]
                    else:
                        if data[i] == min(window):
                            pivots[i] = data[i]
                return pivots

            @staticmethod
            def classify_pivots(highs, lows, period=2):
                high_pivots = tv.find_pivots(highs, period, is_high=True)
                low_pivots = tv.find_pivots(lows, period, is_high=False)
                hh, hl, lh, ll = [], [], [], []
                previous_high = previous_low = None

                for i in range(len(highs)):
                    if not np.isnan(high_pivots[i]):
                        if previous_high is not None and highs[i] > previous_high:
                            hh.append(i)
                        elif previous_high is not None:
                            lh.append(i)
                        previous_high = highs[i]

                    if not np.isnan(low_pivots[i]):
                        if previous_low is not None and lows[i] < previous_low:
                            ll.append(i)
                        elif previous_low is not None:
                            hl.append(i)
                        previous_low = lows[i]

                return hh, hl, lh, ll

            @staticmethod
            def classify_pivots_4h(highs, lows, period=2):
                high_pivots = tv.find_pivots(highs, period, is_high=True)
                low_pivots = tv.find_pivots(lows, period, is_high=False)
                hh, hl, lh, ll = [], [], [], []
                previous_high = previous_low = None

                for i in range(len(highs)):
                    if not np.isnan(high_pivots[i]):
                        if previous_high is not None and highs[i] > previous_high:
                            hh.append(i)
                        elif previous_high is not None:
                            lh.append(i)
                        previous_high = highs[i]

                    if not np.isnan(low_pivots[i]):
                        if previous_low is not None and lows[i] < previous_low:
                            ll.append(i)
                        elif previous_low is not None:
                            hl.append(i)
                        previous_low = lows[i]

                return hh, hl, lh, ll


        if __name__ == "__main__":
            logging.basicConfig(level=logging.FATAL)
            for logger_name in ['matplotlib', 'urllib3']:
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.WARNING)
            pd.set_option('display.max_rows', None)
            coins = ["DYDXUSDT", "APTUSDT", "EOSUSDT", "LDOUSDT", "BTCUSDT", "OPUSDT", "ETHUSDT", "ARUSDT", "KAVAUSDT", "YGGUSDT", "KNCUSDT", "STORJUSDT", "MINAUSDT", "API3USDT", "EGLDUSDT", "AXSUSDT", "CHZUSDT", "FLOWUSDT", "STRKUSDT", "ALGOUSDT", "FTMUSDT", "INJUSDT", "SUIUSDT", "XMRUSDT.P", "BNBUSDT", "SOLUSDT", "XRPUSDT", "TONUSDT.P", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "MATICUSDT", "UNIUSDT", "LTCUSDT", "ICPUSDT", "DAIUSDT", "RNDRUSDT", "HBARUSDT", "ATOMUSDT", "ARBUSDT", "IMXUSDT", "FILUSDT", "XLMUSDT"]

            value = 1000
            value_3_percent = (value / 100) * 3
            itog = 1000

            start_index = load_last_coin_index()

            while True:
                for symbol in coins:
                    tv = TvDatafeed()
                    exchange = "BINANCE"
                    interval = Interval.in_1_hour
                    n_bars = 500

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
                    current_price = closes[-1]

                    four_hour_data = tv.get_hist(symbol, exchange, Interval.in_4_hour, n_bars)
                    four_hour_highs = four_hour_data["high"].tolist()
                    four_hour_lows = four_hour_data["low"].tolist()
                    four_hour_timestamps = four_hour_data.index.tolist()

                    hist_data_15m = tv.get_hist(symbol, exchange, Interval.in_15_minute, n_bars * 4)
                    highs_15m = hist_data_15m["high"].tolist()
                    lows_15m = hist_data_15m["low"].tolist()
                    timestamps_15m = hist_data_15m.index.tolist()

                    hh_15m, hl_15m, lh_15m, ll_15m = tv.classify_pivots(highs_15m, lows_15m)

                    # Находим HH и LL на 4-часовом графике
                    hh_4h, hl_4h, lh_4h, ll_4h = tv.classify_pivots(four_hour_highs, four_hour_lows, period=2)
                    hh_1h, hl_1h, lh_1h, ll_1h = tv.classify_pivots(highs, lows, period=2)

                    # Сопоставляем HH и LL на часовом графике
                    hourly_pivots = {'HH': [], 'LL': []}
                    for i, four_hour_time in enumerate(four_hour_timestamps):
                        if i < len(four_hour_timestamps) - 1:
                            next_four_hour_time = four_hour_timestamps[i + 1]
                            for j, one_hour_time in enumerate(timestamps):
                                if four_hour_time <= one_hour_time < next_four_hour_time:
                                    if i in hh_4h and highs[j] == four_hour_highs[i]:
                                        hourly_pivots['HH'].append(j)
                                    if i in ll_4h and lows[j] == four_hour_lows[i]:
                                        hourly_pivots['LL'].append(j)

                    matched_highs = []
                    for i in hh_4h:
                        for j in hh_1h:
                            if timestamps[j] >= four_hour_timestamps[i] and highs[j] == four_hour_highs[i]:
                                matched_highs.append(j)

                    matched_lows = []
                    for i in ll_4h:
                        for j in ll_1h:
                            if timestamps[j] >= four_hour_timestamps[i] and lows[j] == four_hour_lows[i]:
                                matched_lows.append(j)

                    matched_lls = []
                    for hh_idx in matched_highs:
                        hh_time = timestamps[hh_idx]
                        subsequent_lls = [(i, ts) for i, ts in enumerate(timestamps_15m) if
                                          ts > hh_time and i in ll_15m]
                        if subsequent_lls:
                            closest_ll = min(subsequent_lls, key=lambda x: x[1])
                            matched_lls.append(closest_ll[0])

                    three_am_indices = [i for i, timestamp in enumerate(timestamps) if
                                        timestamp.hour == 3 and timestamp.minute == 0]

                    imbalance_zones_green, imbalance_zones_red = tv.find_imbalance(highs, lows)
                    if imbalance_zones_green:
                        print("Найдены Часовые имбалансные зоны:")
                        for zone in imbalance_zones_green:
                            print(f"Индексы: {zone}, Максимумы: {highs[zone[0]]}, Минимумы: {lows[zone[1]]}")
                    else:
                        print("Имбалансные зоны не найдены.")
                    if imbalance_zones_red:
                        print("Найдены Часовые имбалансные зоны:")
                        for zone in imbalance_zones_red:
                            print(f"Индексы: {zone}, Максимумы: {highs[zone[0]]}, Минимумы: {lows[zone[1]]}")
                    else:
                        print("Имбалансные зоны не найдены.")

                    (green_zones, red_zones, green_ranges, red_ranges, green_50pct, red_50pct,
                     rb, rb_ranges, green_crossings, red_crossings, green_crossing_imbalances, red_crossing_imbalances) = tv.get_4h_imbalance_zones(
                        symbol, exchange, n_bars)
                    print(green_crossing_imbalances)
                    print(red_crossing_imbalances)
                    hh_ind, hl_ind, lh_ind, ll_ind = tv.classify_pivots(highs, lows)

                    plt.figure(figsize=(24, 14))
                    fig, ax = plt.subplots(figsize=(24, 14))
                    plt.title(f'Graph for {symbol}', fontsize=20, loc='center')

                    rejection_blocks = tv.find_rejection_blocks(opens, closes)
                    print("Rejection blocks found at indexes:", rejection_blocks)

                    bar_width = 0.5
                    colors = ['green' if open_price < close_price else 'red' for open_price, close_price in zip(opens, closes)]

                    ax.vlines(x=range(len(hist_data)), ymin=lows, ymax=highs, color='black', linewidth=0.5, zorder=0)
                    ax.bar(range(len(hist_data)), abs(np.array(opens) - np.array(closes)), bottom=np.minimum(opens, closes),
                           color=colors, width=0.7, zorder=1)

                    # hh_indices, hl_indices, ll_indices, lh_indices = tv.update_prices(highs, lows, range(len(highs)), ax)
                    # print("HH indices:", hh_indices)  # Print HH indices
                    # print("HL indices:", hl_indices)  # Print HH indices

                    result = []
                    result_ll = []
                    for hh in hh_ind:
                        nearest_hl = min([hl for hl in hl_ind if hl > hh], default=None)
                        result.append((hh, nearest_hl))

                    for ll in ll_ind:
                        nearest_lh = min([lh for lh in lh_ind if lh < ll], default=None)
                        result.append((ll, nearest_lh))

                    matching_values = []
                    matching_values_ll = []
                    mid_matching_values = []
                    mid_matching_values_ll = []
                    special_crossing_indices = []
                    special_crossing_indices_ll = []
                    next_hh_after_crossing = {}
                    next_ll_after_crossing = {}
                    breakdown_structures = {}
                    breakdown_structures_ll = {}
                    average_prices = {}
                    average_prices_ll = {}
                    touch_bar_indices = {}
                    touch_bar_indices_ll = {}
                    super_tochka = []
                    super_tochka_ll = []
                    super_tochka_times = []
                    super_tochka_times_ll = []
                    successful = 0
                    unsuccessful = 0
                    super_plecho_baz = {}
                    super_plecho_baz_ll = {}
                    point_vhod = {}
                    point_vhod_ll = {}
                    liqvid = {}
                    liqvid_ll ={}

                    for hh, hl in result:
                        if hl is not None:
                            matching_values.append((highs[hh], lows[hl]))
                            mid_matching_values.append((highs[hh] + lows[hl]) / 2)

                    for ll, lh in result_ll:
                        if lh is not None:
                            matching_values_ll.append((lows[ll], highs[lh]))
                            mid_matching_values_ll.append((lows[ll] + highs[lh]) / 2)

                    for crossing in red_crossings:
                        ax.scatter(crossing, lows[crossing] if crossing in red_crossings else highs[crossing], color='purple',
                                   marker='o', label='Special Crossing Match')
                        special_crossing_indices.append(crossing)

                        if crossing in red_crossing_imbalances:
                            imbalance_high = red_crossing_imbalances[crossing]['high']

                        following_lls = [ll for ll in ll_ind if ll > crossing]
                        if following_lls:
                            first_ll_after = min(following_lls)

                            if lows[first_ll_after] > (lows[crossing] if crossing in red_crossings else highs[crossing]):
                                continue

                            breakdown_structures[crossing] = first_ll_after
                            ax.scatter(first_ll_after,
                                       lows[first_ll_after] if crossing in red_crossings else highs[first_ll_after],
                                       color='black', marker='x', label='Breakdown Structure')

                            previous_hhs = [hh for hh in hh_ind if hh < first_ll_after]
                            if previous_hhs:
                                last_hh_before_ll = max(previous_hhs)
                                if crossing < last_hh_before_ll < first_ll_after:
                                    continue

                                if crossing in red_crossing_imbalances and last_hh_before_ll > imbalance_high:
                                    continue

                                average_price = (highs[last_hh_before_ll] + lows[first_ll_after]) / 2
                                average_prices[(last_hh_before_ll, first_ll_after)] = average_price
                                average_price_one_percent = (highs[last_hh_before_ll] - lows[first_ll_after]) / 100
                                target_price = lows[first_ll_after] - (average_price_one_percent * 61.8)
                                failure_price = highs[last_hh_before_ll]
                                plecho_procent = average_price / 100
                                plecho_1 = highs[last_hh_before_ll] / plecho_procent
                                plecho_2 = plecho_1 - 100
                                plecho_baz = 100 // plecho_2
                                average_prices_percent = target_price / plecho_procent
                                target_price_percent = 100 - average_prices_percent
                                vigoda = plecho_baz * target_price_percent
                                ax.text(first_ll_after, average_price, f'Avg: {average_price:.2f}', va='bottom', ha='center',
                                        color='blue')

                                for i in range(first_ll_after + 1, len(highs)):
                                    if lows[i] <= average_price <= highs[i]:
                                        touch_bar_indices[first_ll_after] = i
                                        super_tochka.append(i)
                                        super_plecho_baz[i] = plecho_baz
                                        point_vhod[i] = average_price
                                        liqvid[i] = failure_price
                                        super_tochka_times.append(timestamps[i])
                                        ax.scatter(i, average_price, color='red', marker='*', label='Price Touch')

                                        for j in range(i, len(highs)):
                                            if highs[j] > failure_price:
                                                unsuccessful += 1
                                                value = value - value_3_percent
                                                itog = itog + (value - 1000)
                                                break
                                            elif lows[j] < target_price:
                                                successful += 1
                                                value_plus = value_3_percent + ((value_3_percent / 100) * vigoda)
                                                value = value + value_plus
                                                itog = itog + (value - 1000)
                                                break
                                        break

                    for crossing in green_crossings:
                        ax.scatter(crossing, highs[crossing] if crossing in green_crossings else lows[crossing],
                                   color='purple', marker='o', label='Special Crossing Match')
                        special_crossing_indices_ll.append(crossing)

                        if crossing in green_crossing_imbalances:
                            imbalance_low = green_crossing_imbalances[crossing]['low']

                        following_hhs = [hh for hh in hh_ind if hh > crossing]
                        if following_hhs:
                            first_hh_after = min(following_hhs)

                            if highs[first_hh_after] < (highs[crossing] if crossing in green_crossings else lows[crossing]):
                                continue

                            breakdown_structures_ll[crossing] = first_hh_after
                            ax.scatter(first_hh_after,
                                       highs[first_hh_after] if crossing in green_crossings else lows[first_hh_after],
                                       color='black', marker='x', label='Breakdown Structure')

                            previous_lls = [ll for ll in ll_ind if ll < first_hh_after and ll > crossing]
                            if previous_lls:
                                last_ll_before_hh = max(previous_lls)

                                if crossing in green_crossing_imbalances and last_ll_before_hh < imbalance_low:
                                    continue

                                average_price = (lows[last_ll_before_hh] + highs[first_hh_after]) / 2
                                average_price_one_percent = (highs[first_hh_after] - lows[last_ll_before_hh]) / 100
                                target_price = highs[first_hh_after] + (average_price_one_percent * 61.8)
                                failure_price = lows[last_ll_before_hh]
                                plecho_procent = average_price / 100
                                plecho_1 = lows[last_ll_before_hh] / plecho_procent
                                plecho_2 = 100 - plecho_1
                                plecho_baz_ll = 100 // plecho_2
                                average_prices_percent = target_price / plecho_procent
                                target_price_percent = average_prices_percent - 100
                                vigoda = plecho_baz_ll * target_price_percent

                                ax.text(first_hh_after, average_price, f'Avg: {average_price:.2f}', va='bottom', ha='center',
                                        color='blue')

                                for i in range(first_hh_after + 1, len(lows)):
                                    if highs[i] >= average_price >= lows[i]:
                                        touch_bar_indices_ll[first_hh_after] = i
                                        super_tochka_ll.append(i)
                                        super_plecho_baz_ll[i] = plecho_baz_ll
                                        point_vhod_ll[i] = average_price
                                        liqvid_ll[i] = failure_price
                                        super_tochka_times_ll.append(timestamps[i])
                                        ax.scatter(i, average_price, color='green', marker='*', label='Price Touch')

                                        for j in range(i, len(highs)):
                                            if lows[j] < failure_price:
                                                unsuccessful += 1
                                                value = value - value_3_percent
                                                itog = itog + (value - 1000)
                                                break
                                            elif highs[j] > target_price:
                                                successful += 1
                                                value_plus = value_3_percent + ((value_3_percent / 100) * vigoda)
                                                value = value + value_plus
                                                itog = itog + (value - 1000)
                                                break
                                        break

                    print(f"Successful: {successful}")
                    print(f"Unsuccessful: {unsuccessful}")
                    print(f"Value: {value}")
                    print(f"Itog: {itog}")

                    for crossing_index, indices in next_hh_after_crossing.items():
                        hh_index, hl_index = indices
                        average_price = tv.calculate_average(highs, lows, hh_index, hl_index)
                        print(
                            f"Для crossing {crossing_index} со следующим hh {hh_index} и hl {hl_index}, среднее значение: {average_price}")

                    test_results, successes, failures, value = tv.test_price_behavior(highs, lows, closes, next_hh_after_crossing)
                    for test in test_results:
                        print(test)
                    print(f"Количество удачных сценариев: {successes}")
                    print(f"Количество неудачных сценариев: {failures}")
                    print(f"Итоговое значение value после всех тестов: {value:.2f}")
                    # hh_rb_combinations, below_rb_after_combination, above_rb_after_combination = tv.test_hh_rejection_blocks(
                    #     hh_indices, rejection_blocks, lows, closes)
                    #
                    # print(f"Комбинации HH и rejection block: {hh_rb_combinations}")
                    # print(f"Цена закрылась ниже уровня rejection block в течение 5 баров: {below_rb_after_combination} раз")
                    # print(f"Цена закрылась выше уровня rejection block в течение 5 баров: {above_rb_after_combination} раз")

                    # results = tv.test_hh_rejection_blocks(hh_indices, rejection_blocks, lows, closes)
                    # print("HH-RB Combinations:", results[0])
                    # print("Below RB after Combination:", results[1])
                    # print("Above RB after Combination:", results[2])
                    # print("Percent Changes Below RB:", results[3])
                    # print("Percent Changes Above RB:", results[4])
                    # print("Final Value:", results[5])

                    # for zone in imbalance_zones_green:
                    #     ax.scatter(zone[0], lows[zone[0]], color='black', marker='o', label='Imbalance')
                    # for zone in imbalance_zones_red:
                    #     ax.scatter(zone[0], lows[zone[0]], color='black', marker='o', label='Imbalance')

                    # for block in rejection_blocks:
                    #     ax.scatter(block, highs[block], color='blue', marker='o', label='Rejection Block')

                    for idx in three_am_indices:
                        ax.scatter(idx, lows[idx], color='black', marker='o', label='3 AM')


                    for idx, (start, end) in enumerate(zip(three_am_indices[:-1], three_am_indices[1:]), 1):
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
                        ax.text(mid_point, max_high, str(len(three_am_indices) - idx), color='black', ha='center', va='bottom')


                    for idx, (start, end) in enumerate(zip(three_am_indices[:-1], three_am_indices[1:]), 1):
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
                        ax.text(mid_point, min_low, str(len(three_am_indices) - idx), color='red', ha='center', va='top')

                    handles, labels = ax.get_legend_handles_labels()
                    by_label = dict(zip(labels, handles))
                    ax.legend(by_label.values(), by_label.keys())

                    ax.set_xlim([0, len(hist_data)])
                    ax.set_ylim([min(lows) * 0.95, max(highs) * 1.05])

                    print(super_tochka)
                    print(super_plecho_baz)
                    print(super_tochka_ll)
                    print(super_plecho_baz_ll)

                    def save_super_tochka(super_tochka, symbol, exchange, super_tochka_times, super_tochka_ll,
                                          super_tochka_times_ll, super_plecho_baz, super_plecho_baz_ll, point_vhod,
                                          point_vhod_ll, liqvid, liqvid_ll):
                        file_path = 'super_tochka.json'
                        try:
                            with open(file_path, 'r') as file:
                                data = json.load(file)
                                if not isinstance(data, list):
                                    data = []
                        except (FileNotFoundError, json.JSONDecodeError):
                            data = []

                        updated = False
                        for entry in data:
                            if entry.get('symbol') == symbol:
                                entry['data'] = [
                                    {'value': point, 'time': time.isoformat() if hasattr(time, 'isoformat') else time,
                                     'plecho': super_plecho_baz.get(point), 'point_vhod': point_vhod.get(point), 'liqvid': liqvid.get(point)}
                                    for point, time in zip(super_tochka, super_tochka_times)
                                ]
                                entry['data_ll'] = [
                                    {'value': point, 'time': time.isoformat() if hasattr(time, 'isoformat') else time,
                                     'plecho': super_plecho_baz_ll.get(point), 'point_vhod': point_vhod_ll.get(point), 'liqvid': liqvid_ll.get(point)}
                                    for point, time in zip(super_tochka_ll, super_tochka_times_ll)
                                ]
                                updated = True
                                break

                        if not updated:
                            new_entry = {
                                "symbol": symbol,
                                "data": [
                                    {'value': point, 'time': time.isoformat() if hasattr(time, 'isoformat') else time,
                                     'plecho': super_plecho_baz.get(point), 'point_vhod': point_vhod.get(point), 'liqvid': liqvid.get(point)}
                                    for point, time in zip(super_tochka, super_tochka_times)
                                ],
                                "data_ll": [
                                    {'value': point, 'time': time.isoformat() if hasattr(time, 'isoformat') else time,
                                     'plecho': super_plecho_baz_ll.get(point), 'point_vhod': point_vhod_ll.get(point), 'liqvid': liqvid_ll.get(point)}
                                    for point, time in zip(super_tochka_ll, super_tochka_times_ll)
                                ],
                                "exchange": exchange
                            }
                            data.append(new_entry)

                        with open(file_path, 'w', encoding='utf-8') as file:
                            json.dump(data, file, ensure_ascii=False, indent=4)

                    save_super_tochka(super_tochka, symbol, exchange, super_tochka_times, super_tochka_ll, super_tochka_times_ll, super_plecho_baz, super_plecho_baz_ll, point_vhod, point_vhod_ll, liqvid, liqvid_ll)

                    plt.scatter(hh_ind, [highs[i] for i in hh_ind], color='green', label='HH')
                    plt.scatter(hl_ind, [lows[i] for i in hl_ind], color='blue', label='HL')
                    plt.scatter(lh_ind, [highs[i] for i in lh_ind], color='orange', label='LH')
                    plt.scatter(ll_ind, [lows[i] for i in ll_ind], color='red', label='LL')

                    for idx in matched_highs:
                        ax.scatter(idx, highs[idx], color='brown', marker='o', label='Matched Hourly HH')

                    for idx in matched_lows:
                        ax.scatter(idx, lows[idx], color='brown', marker='o', label='Matched Hourly LL')

                    for ll_idx in matched_lls:
                        ax.scatter(ll_idx, lows_15m[ll_idx], color='pink', marker='x', label='Matched LL 15m')
                        print(ll_idx)

                    handles, labels = ax.get_legend_handles_labels()
                    by_label = dict(zip(labels, handles))
                    ax.legend(by_label.values(), by_label.keys())

                    ax.set_xlim([0, len(hist_data)])
                    ax.set_ylim([min(lows) * 0.95, max(highs) * 1.05])

                    plt.show()
                    plt.close()
                    time.sleep(3)

                start_index = 0

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        print("Перезапуск кода...")
        time.sleep(5)