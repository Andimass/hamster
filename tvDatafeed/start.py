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

THREE_MINUTE_PATH = os.path.join(os.path.dirname(__file__), 'three_minute.json')
LAST_COIN_INDEX_PATH = os.path.join(os.path.dirname(__file__), 'last_coin_index.txt')

username = 'masyuckevich12345@gmail.com'
password = 'LHJybrk777;'
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

    # @staticmethod
    # def find_imbalance(highs, lows):
    #     imbalance_zones_green = []
    #     imbalance_zones_red = []
    #     n = len(highs)
    #
    #     for i in range(2, n):
    #         if lows[i] > highs[i - 2]:
    #             valid = True
    #             for j in range(i + 1, n):
    #                 if highs[i - 2] > lows[j]:
    #                     valid = True
    #                     break
    #             if valid:
    #                 imbalance_zones_green.append((i - 2, i))
    #
    #     for i in range(2, n):
    #         if highs[i] < lows[i - 2]:
    #             valid = True
    #             for j in range(i + 1, n):
    #                 if lows[i - 2] < highs[j]:
    #                     valid = True
    #                     break
    #             if valid:
    #                 imbalance_zones_red.append((i - 2, i))
    #
    #     return imbalance_zones_green, imbalance_zones_red
    #
    #
    # @staticmethod
    # def get_4h_imbalance_zones(symbol, exchange, n_bars):
    #     tv = TvDatafeed()
    #     four_hour_data = tv.get_hist(symbol, exchange, Interval.in_4_hour, n_bars // 4)
    #     if four_hour_data is None:
    #         logger.error(f"Failed to retrieve 4-hour data for {symbol}")
    #         return None
    #     four_hour_highs = four_hour_data["high"].tolist()
    #     four_hour_lows = four_hour_data["low"].tolist()
    #     four_hour_opens = four_hour_data["open"].tolist()
    #     four_hour_closes = four_hour_data["close"].tolist()
    #     four_hour_timestamps = four_hour_data.index.tolist()
    #     n = len(four_hour_highs)
    #
    #
    #     hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)
    #     if hist_data is None:
    #         logger.error(f"Failed to retrieve hourly data for {symbol}")
    #         return None
    #     highest = hist_data["high"].tolist()
    #     lowest = hist_data["low"].tolist()
    #     opens = hist_data["open"].tolist()
    #     closes = hist_data["close"].tolist()
    #     hourly_timestamps = hist_data.index.tolist()


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
            if highs[i - 2] >= highs[i - 1] and highs[i - 2] >= highs[i - 3] and highs[i - 2] >= highs[i] and highs[
                i - 2] >= highs[i - 4]:
                high_prices_arr.append(highs[i - 2])
                high_indexs_arr.append(bar_indices[i - 2])
                if high_ and (low_prices_arr and min(low_prices_arr) < sw_low_price or highs[i - 2] > sw_high_price):
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

            if lows[i - 2] <= lows[i - 1] and lows[i - 2] <= lows[i - 3] and lows[i - 2] <= lows[i] and lows[i - 2] <= \
                    lows[i - 4]:
                low_prices_arr.append(lows[i - 2])
                low_indexs_arr.append(bar_indices[i - 2])
                if low_ and (high_prices_arr and max(high_prices_arr) > sw_high_price or lows[i - 2] < sw_low_price):
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
                    ax.plot([sw_high_index, bar_indices[i]], [sw_high_price, sw_high_price], color='g', linestyle='-')
                    bull_bos_ends.append(bar_indices[i])

            if sw_low_price is not None and lows[i] < sw_low_price:
                if not bear_bos:
                    bear_bos = True
                    bull_bos = False
                    ax.plot([sw_low_index, bar_indices[i]], [sw_low_price, sw_low_price], color='r', linestyle='-')
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

    # @staticmethod
    # def test_highs_after_hh(highs_after_hh, hh_start_array, highs, lows, daily_max_highs, daily_min_lows):
    #     results = []
    #
    #     for idx in highs_after_hh:
    #         previous_day_max = None
    #         previous_day_min = None
    #
    #         # Определяем предыдущие максимумы и минимумы дня для текущего индекса
    #         for i in range(len(daily_max_highs)):
    #             if i < idx:
    #                 previous_day_max = daily_max_highs[i]
    #                 previous_day_min = daily_min_lows[i]
    #             else:
    #                 break
    #
    #         midpoint = (previous_day_max + previous_day_min) / 2
    #
    #         # Проверяем, было ли пересечение midpoint или следующего hh
    #         hh_intersection = any(highs[idx] > highs[hh] for hh in hh_start_array if hh > idx)
    #         midpoint_intersection = lows[idx] <= midpoint
    #
    #         result = {
    #             "idx": idx,
    #             "hh_intersection": hh_intersection,
    #             "midpoint_intersection": midpoint_intersection,
    #             "crossed_first": "midpoint" if midpoint_intersection and not hh_intersection else "hh" if hh_intersection and not midpoint_intersection else "both" if midpoint_intersection and hh_intersection else "none"
    #         }
    #
    #         results.append(result)
    #
    #     return results

    # @staticmethod
    # def calculate_rsi(period=14):
    #     tv = TvDatafeed()
    #     hist_data = tv.get_hist(symbol, exchange, Interval.in_1_hour, n_bars)
    #     if hist_data is None:
    #         logger.error(f"Failed to retrieve hourly data for {symbol}")
    #         return None
    #     closes = hist_data["close"].tolist()
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, filename='error.log', filemode='a',
                        format='%(asctime)s - %(levelname)s - %(message)s')
    for logger_name in ['matplotlib', 'urllib3']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
    pd.set_option('display.max_rows', None)
    coins = ["BTCUSDT"]

    value = 1000
    value_3_percent = (value / 100) * 3
    itog = 1000

    while True:
        for symbol in coins:
            tv = TvDatafeed()
            exchange = "BINANCE"
            interval = Interval.in_3_minute
            n_bars = 8000

            highs = []
            lows = []
            opens = []
            closes = []
            labels = []

            CSV_FILE_PATH = '../TvDatafeed_2/BTC.csv'
            hist_data = pd.read_csv(CSV_FILE_PATH)
            hist_data['time'] = pd.to_datetime(hist_data['time'])
            hist_data.set_index('time', inplace=True)

            highs = hist_data["high"].tolist()
            lows = hist_data["low"].tolist()
            opens = hist_data["open"].tolist()
            closes = hist_data["close"].tolist()
            current_price = closes[-1]
            timestamps = hist_data.index.tolist()  # Список меток времени

            open_figures = []

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

            hh_ind, hl_ind, lh_ind, ll_ind, bull_bos_ends, bear_bos_ends = tv.update_prices(highs, lows, range(len(highs)), ax)
            print("HH indices:", hh_ind)  # Print HH indices
            print("HL indices:", hl_ind)  # Print HH indices


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
            midpoint_short = {}
            midpoint_long = {}
            point_vhod_long_rr_max = {}
            point_vhod_short_rr_max = {}
            max_high_index_array = {}
            min_low_index_array = {}

            for hl in hl_ind:
                for i in range(hl + 1, len(lows)):
                    if lows[i] < lows[hl]:
                        hl_array.append(i)
                        hl_price_array[i] = lows[hl]
                        hl_start_array.append(hl)
                        break

            print(f'Точки слома HL - {hl_array}')
            print(f'Точки слома HL - {hl_start_array}')

            for lh in lh_ind:
                for i in range(lh + 1, len(highs)):
                    if highs[i] > highs[lh]:
                        lh_array.append(i)
                        lh_price_array[i] = highs[lh]
                        lh_start_array.append(lh)
                        break

            print(f'Точки слома LH - {lh_array}')
            print(f'Точки слома LH - {lh_start_array}')

            for hh in hh_ind:
                for i in range(hh + 1, len(lows)):
                    if lows[i] < lows[hh]:
                        hh_array.append(i)
                        hh_price_array[i] = highs[hh]
                        hh_start_array.append(hh)
                        break

            print(f'Точки слома HH - {hh_array}')
            print(f'Точки слома HH - {hh_start_array}')

            for ll in ll_ind:
                for i in range(ll + 1, len(highs)):
                    if highs[i] > highs[ll]:
                        ll_array.append(i)
                        ll_price_array[i] = highs[ll]
                        ll_start_array.append(ll)
                        break

            print(f'Точки слома LL - {ll_array}')
            print(f'Точки слома LL - {ll_start_array}')

            # Создаем список максимумов и минимумов для каждого дня

            for start, end in zip(midnight_indices[:-1], midnight_indices[1:]):
                daily_max_highs.append(max(highs[start:end]))
                daily_min_lows.append(min(lows[start:end]))

            print(daily_max_highs)
            print(daily_min_lows)

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
                                next_hh_idx = next_hh_candidates[0]  # Предполагаем, что hh_start_array отсортирован по возрастанию
                                # Сравниваем высоты текущего и следующего hh
                                if highs[next_hh_idx] > highs[nearest_hh_idx]:
                                    nearest_hh_idx = next_hh_idx  # Обновляем, если следующий hh выше текущего

                        nearest_hl_idx = min([hl for hl in hl_array if hl > max_idx] + [lh for lh in lh_array if lh > max_idx] + [ll for ll in ll_array if ll > max_idx], default=None)
                        if nearest_hl_idx is not None:
                            hl_price = hl_price_array[nearest_hl_idx] if nearest_hl_idx in hl_price_array else lows[nearest_hl_idx]
                            ax.scatter(nearest_hl_idx, hl_price, color='grey', s=300, label='Low Below HL Low')
                            ax.plot([max_idx, nearest_hl_idx], [highs[max_idx], hl_price], color='purple',
                                    linestyle='--')
                            print(
                                f"Low after HH at index {max_idx} lower than HL low found at index {nearest_hl_idx}")
                            highs_after_hh.append(nearest_hl_idx)
                            if nearest_hl_idx is not None:
                                hl_price = hl_price_array.get(nearest_hl_idx, lows[nearest_hl_idx])
                                hh_price = hh_price_array.get(nearest_hh_idx, highs[nearest_hh_idx]) if nearest_hh_idx is not None else None

                                max_high_value = 1
                                max_high_index = nearest_hl_idx


                                # Поиск максимального highs в интервале
                                for idx in range(nearest_hl_idx + 1, len(highs)):
                                    if highs[idx] > max_high_value and highs[idx] <= highs[nearest_hh_idx]:
                                        max_high_index = idx
                                        max_high_value = highs[idx]
                                        max_high_index_array[nearest_hl_idx] = idx

                                    # Условия остановки поиска
                                    if highs[idx] <= midpoint or highs[idx] >= hh_price:
                                        break

                                print(f"Максимальная точка {max_high_value} найдена на индексе {max_high_index}")

                                print("\nRR\n")
                                if hl_price != 0:
                                    price_muv_1pct_short = round(hl_price / 100, 3)
                                    if price_muv_1pct_short != 0:
                                        price_muv_liqvidation_short = round(
                                            (hh_price / price_muv_1pct_short) - 100, 3) if hh_price else None
                                        if price_muv_liqvidation_short:
                                            price_muv_profit_short = round(
                                                100 - (midpoint / price_muv_1pct_short), 3)
                                            RR_short = round(
                                                price_muv_profit_short / price_muv_liqvidation_short, 3)
                                            point_vhod_short[nearest_hl_idx] = hl_price
                                            point_liqvidation_short[nearest_hl_idx] = hh_price if hh_price else \
                                            highs[nearest_hl_idx]
                                            rr_array_short[nearest_hl_idx] = RR_short if RR_short else None
                                            midpoint_short[nearest_hl_idx] = midpoint
                                            print("ШОРТ Сделка - ", price_muv_1pct_short,
                                                  price_muv_liqvidation_short, price_muv_profit_short, RR_short)

                                # Enhanced Short Trade Calculations with Max Price
                                print("\nRR-MAX\n")
                                if max_high_value != 0:
                                    price_muv_1pct_short_max = round(max_high_value / 100, 3)
                                    if price_muv_1pct_short_max != 0:
                                        price_muv_liqvidation_short_max = round((highs[nearest_hh_idx] / price_muv_1pct_short_max) - 100, 3) if hh_price else None
                                        if price_muv_liqvidation_short_max:
                                            price_muv_profit_short_max = round(100 - (midpoint / price_muv_1pct_short_max), 3)
                                            RR_short_max = round(price_muv_profit_short_max / price_muv_liqvidation_short_max, 3)
                                            point_vhod_short_max[nearest_hl_idx] = max_high_value
                                            point_liqvidation_short_max[nearest_hl_idx] = hh_price if hh_price else highs[max_high_index]
                                            rr_array_short_max[nearest_hl_idx] = RR_short_max if RR_short_max else None
                                            midpoint_short[nearest_hl_idx] = midpoint
                                            print("ШОРТ Сделка - ", point_vhod_short_max, price_muv_1pct_short_max,
                                                  price_muv_liqvidation_short_max, price_muv_profit_short_max,
                                                  RR_short_max, "\n")

                for min_idx in day_min:
                    if lows[min_idx] < daily_min_lows[i - 1]:
                        ax.scatter(min_idx, lows[min_idx], color='blue', s=100, label='Break Below Min')
                        three_minute_long.append(min_idx)

                        nearest_ll_idx = min([ll for ll in ll_start_array if ll >= min_idx], default=None)
                        nearest_lh_idx = min([lh for lh in lh_array if lh > min_idx] + [hl for hl in hl_array if hl > min_idx] + [hh for hh in hh_array if hh > min_idx], default=None)

                        if nearest_ll_idx is not None:
                            next_ll_candidates = [ll for ll in ll_start_array if ll > nearest_ll_idx]
                            if next_ll_candidates:
                                next_ll_idx = next_ll_candidates[0]  # Предполагаем, что hh_start_array отсортирован по возрастанию
                                # Сравниваем высоты текущего и следующего hh
                                if lows[next_ll_idx] < lows[nearest_ll_idx]:
                                    nearest_ll_idx = next_ll_idx  # Обновляем, если следующий hh выше текущего

                        if nearest_lh_idx is not None:
                            lh_price = lh_price_array[nearest_lh_idx] if nearest_lh_idx in lh_price_array else highs[nearest_lh_idx]


                            ax.scatter(nearest_lh_idx, lh_price, color='grey', s=300,
                                       label='High Above LH High')
                            ax.plot([min_idx, nearest_lh_idx], [lows[min_idx], lh_price], color='purple',
                                    linestyle='--')
                            print(
                                f"High after LL at index {min_idx} higher than LH high found at index {nearest_lh_idx}")
                            lows_after_ll.append(nearest_lh_idx)


                            lh_price = lh_price_array.get(nearest_lh_idx, highs[nearest_lh_idx])
                            ll_price = ll_price_array.get(nearest_ll_idx, lows[nearest_ll_idx]) if nearest_ll_idx is not None else None

                            min_low_value = lows[nearest_lh_idx]
                            min_low_index = nearest_lh_idx

                            # Поиск максимального highs в интервале
                            for idx in range(nearest_lh_idx + 1, len(lows)):
                                if lows[idx] < min_low_value and lows[idx] >= lows[nearest_ll_idx]:
                                    min_low_index = idx
                                    min_low_value = lows[idx]
                                    min_low_index_array[nearest_lh_idx] = idx


                                # Условия остановки поиска
                                if lows[idx] <= midpoint or lows[idx] <= ll_price:
                                    break

                            print(f"Мнимальная точка {min_low_value} найдена на индексе {min_low_index}")

                            print("\nRR\n")
                            if highs[nearest_lh_idx] != 0:
                                price_muv_1pct_long = round(highs[nearest_lh_idx] / 100, 3)
                                if price_muv_1pct_long != 0:
                                    price_muv_liqvidation_long = round(
                                        100 - (highs[nearest_ll_idx] / price_muv_1pct_long), 3)
                                    price_muv_profit_long = round((midpoint / price_muv_1pct_long) - 100, 3)
                                    if price_muv_profit_long and price_muv_liqvidation_long != 0:
                                        RR_long = round(price_muv_profit_long / price_muv_liqvidation_long, 3)
                                        point_vhod_long[nearest_lh_idx] = highs[nearest_lh_idx]
                                        point_liqvidation_long[nearest_lh_idx] = lows[nearest_ll_idx]
                                        rr_array_long[nearest_lh_idx] = RR_long
                                        midpoint_long[nearest_lh_idx] = midpoint
                                        print("ЛОНГ Сделка - ", price_muv_1pct_long, price_muv_liqvidation_long,
                                              price_muv_profit_long, RR_long)
                                    else:
                                        break

                            print("\nRR-MAX\n")
                            if lows[min_low_index] != 0:
                                price_muv_1pct_long_max = round(lows[min_low_index] / 100, 3)
                                if price_muv_1pct_long_max != 0:
                                    price_muv_liqvidation_long_max = round(100 - (highs[nearest_ll_idx] / price_muv_1pct_long_max), 3)
                                    price_muv_profit_long_max = round((midpoint / price_muv_1pct_long_max) - 100, 3)
                                    RR_long_max = round(price_muv_profit_long_max / price_muv_liqvidation_long_max, 3)
                                    point_vhod_long_max[nearest_lh_idx] = lows[min_low_index]
                                    point_liqvidation_long_max[nearest_lh_idx] = lows[nearest_ll_idx]
                                    rr_array_long_max[nearest_lh_idx] = RR_long_max
                                    midpoint_long[nearest_lh_idx] = midpoint
                                    print("RR-MAX ЛОНГ Сделка - ", price_muv_1pct_long_max, price_muv_liqvidation_long_max, price_muv_profit_long_max, RR_long_max)

            def test_point_vhod_reached_first():
                result_short = {}
                for point_vhod, price_vhod in point_vhod_short.items():
                    price_liqvidation = point_liqvidation_short.get(point_vhod, None)
                    midpoint = (daily_max_highs[0] + daily_min_lows[0]) / 2  # для теста берем первый день
                    if price_liqvidation:
                        reached_liqvidation = False
                        reached_midpoint = False
                        for price in highs[point_vhod:]:
                            if price >= price_liqvidation:
                                reached_liqvidation = True
                                break
                            if price <= midpoint:
                                reached_midpoint = True
                                break

                        if reached_liqvidation:
                            print(f"Point {point_vhod} reached liquidation price first.")
                            result_short[point_vhod] = 0
                        elif reached_midpoint:
                            print(f"Point {point_vhod} reached midpoint first.")
                            result_short[point_vhod] = 1
                        else:
                            print(f"Point {point_vhod} reached neither liquidation price nor midpoint.")

                print(result_short)
                return result_short

            result_short = test_point_vhod_reached_first()
            print(result_short)

            def test_point_vhod_long_reached_first():
                result_long = {}
                for point_vhod, price_vhod in point_vhod_long.items():
                    price_liqvidation = point_liqvidation_long.get(point_vhod, None)
                    midpoint = (daily_max_highs[0] + daily_min_lows[0]) / 2  # для теста берем первый день

                    if price_liqvidation:
                        reached_liqvidation = False
                        reached_midpoint = False
                        for price in lows[point_vhod:]:
                            if price <= price_liqvidation:
                                reached_liqvidation = True
                                break
                            if price >= midpoint:
                                reached_midpoint = True
                                break

                        if reached_liqvidation:
                            print(f"Point {point_vhod} reached liquidation price first.")
                            result_long[point_vhod] = 0
                        elif reached_midpoint:
                            print(f"Point {point_vhod} reached midpoint first.")
                            result_long[point_vhod] = 1
                        else:
                            print(f"Point {point_vhod} reached neither liquidation price nor midpoint.")

                return result_long

            result_long = test_point_vhod_long_reached_first()

            print(result_long)

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
                ax.text(mid_point, max_high, str(len(midnight_indices) - idx), color='black', ha='center', va='bottom')


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
                ax.text(mid_point, min_low, str(len(midnight_indices) - idx), color='red', ha='center', va='top')

            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys())

            ax.set_xlim([0, len(hist_data)])
            ax.set_ylim([min(lows) * 0.95, max(highs) * 1.05])


            def three_minute(symbol, exchange, highs_after_hh, lows_after_ll, highs, lows, point_vhod_short, point_vhod_long, point_liqvidation_short, point_liqvidation_long, rr_array_short, rr_array_long, rr_array_long_max, rr_array_short_max, midpoint_short, point_vhod_short_max, max_high_index_array, min_low_index_array, point_vhod_long_max, midpoint_long, result_short, result_long):
                file_path = 'three_minute_strat.json'
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
                        entry['highs_after_hh'] = [
                            {
                                'index': point,
                                'low': lows[point],
                                'point_vhod': point_vhod_short.get(point),
                                'point_liqvidation': point_liqvidation_short.get(point),
                                'rr': rr_array_short.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': max_high_index_array.get(point),
                                'midpoint':midpoint_short.get(point),
                                'max_point_vhod': point_vhod_short_max.get(point),
                                'result': result_short.get(point)
                            }
                            for point in highs_after_hh
                        ]
                        entry['lows_after_ll'] = [
                            {
                                'index': point,
                                'high': highs[point],
                                'point_vhod': point_vhod_long.get(point),
                                'point_liqvidation': point_liqvidation_long.get(point),
                                'rr': rr_array_long.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': min_low_index_array.get(point),
                                'midpoint': midpoint_long.get(point),
                                'max_point_vhod': point_vhod_long_max.get(point),
                                'result': result_long.get(point)
                            }
                            for point in lows_after_ll
                        ]
                        updated = True
                        break

                if not updated:
                    new_entry = {
                        "symbol": symbol,
                        "exchange": exchange,
                        "highs_after_hh": [
                            {
                                'index': point,
                                'low': lows[point],
                                'point_vhod': point_vhod_short.get(point),
                                'point_liqvidation': point_liqvidation_short.get(point),
                                'rr': rr_array_short.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': max_high_index_array.get(point),
                                'midpoint': midpoint_short.get(point),
                                'max_point_vhod': point_vhod_short_max.get(point),
                                'result': result_short.get(point)
                            }
                            for point in highs_after_hh
                        ],
                        "lows_after_ll": [
                            {
                                'index': point,
                                'high': highs[point],
                                'point_vhod': point_vhod_long.get(point),
                                'point_liqvidation': point_liqvidation_long.get(point),
                                'rr': rr_array_long.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': min_low_index_array.get(point),
                                'midpoint': midpoint_long.get(point),
                                'max_point_vhod': point_vhod_long_max.get(point),
                                'result': result_long.get(point)
                            }
                            for point in lows_after_ll
                        ]
                    }
                    data.append(new_entry)

                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)

            three_minute(symbol, exchange, highs_after_hh, lows_after_ll, highs, lows, point_vhod_short, point_vhod_long, point_liqvidation_short, point_liqvidation_long, rr_array_short, rr_array_long, rr_array_long_max, rr_array_short_max, midpoint_short, point_vhod_short_max, max_high_index_array, min_low_index_array, point_vhod_long_max, midpoint_long, result_short, result_long)

            # plt.scatter(hh_ind, [highs[i] for i in hh_ind], color='green', label='HH')
            # plt.scatter(hl_ind, [lows[i] for i in hl_ind], color='blue', label='HL')
            # plt.scatter(lh_ind, [highs[i] for i in lh_ind], color='orange', label='LH')
            # plt.scatter(ll_ind, [lows[i] for i in ll_ind], color='red', label='LL')
            print(bull_bos_ends, 'Индексы bos Long')
            print(bear_bos_ends, 'Индексы bos Short')
            print(highs_after_hh, 'Индексы bos Long')
            print(lows_after_ll, 'Индексы bos Short')

            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys())

            ax.set_xlim([0, len(hist_data)])
            ax.set_ylim([min(lows), max(highs)])

            # results = tv.test_highs_after_hh(highs_after_hh, hh_start_array, highs, lows, daily_max_highs,
            #                               daily_min_lows)

            # Вывод результатов тестирования
            # for result in results:
            #     print(
            #         f"Index: {result['idx']}, HH Intersection: {result['hh_intersection']}, Midpoint Intersection: {result['midpoint_intersection']}, Crossed First: {result['crossed_first']}")

            # rsi, rsi_timestamps = tv.calculate_rsi()
            # rsi_df = pd.DataFrame({'timestamp': rsi_timestamps, 'rsi': rsi})
            # rsi_df['hour'] = rsi_df['timestamp'].dt.floor('h')  # Group by hour
            # hourly_rsi = rsi_df.groupby('hour')['rsi'].mean()
            #
            # for hour, avg_rsi in hourly_rsi.items():
            #     print(f"{hour}: {avg_rsi}")

            plt.show()
            plt.close()
            time.sleep(10)

        coins = ["ETHUSDT"]

        for symbol in coins:
            tv = TvDatafeed()
            exchange = "BINANCE"
            interval = Interval.in_3_minute
            n_bars = 8000

            highs = []
            lows = []
            opens = []
            closes = []
            labels = []

            CSV_FILE_PATH = 'ETH.csv'
            hist_data = pd.read_csv(CSV_FILE_PATH)
            hist_data['time'] = pd.to_datetime(hist_data['time'])
            hist_data.set_index('time', inplace=True)

            highs = hist_data["high"].tolist()
            lows = hist_data["low"].tolist()
            opens = hist_data["open"].tolist()
            closes = hist_data["close"].tolist()
            current_price = closes[-1]
            timestamps = hist_data.index.tolist()  # Список меток времени

            open_figures = []

            plt.figure(figsize=(24, 14))
            fig, ax = plt.subplots(figsize=(24, 14))
            plt.title(f'Graph for {symbol}', fontsize=20, loc='center')

            rejection_blocks = tv.find_rejection_blocks(opens, closes)
            print("Rejection blocks found at indexes:", rejection_blocks)

            bar_width = 0.5
            colors = ['green' if open_price < close_price else 'red' for open_price, close_price in
                      zip(opens, closes)]

            ax.vlines(x=range(len(hist_data)), ymin=lows, ymax=highs, color='black', linewidth=0.5, zorder=0)
            ax.bar(range(len(hist_data)), abs(np.array(opens) - np.array(closes)), bottom=np.minimum(opens, closes),
                   color=colors, width=0.7, zorder=1)

            hh_ind, hl_ind, lh_ind, ll_ind, bull_bos_ends, bear_bos_ends = tv.update_prices(highs, lows,
                                                                                            range(len(highs)), ax)
            print("HH indices:", hh_ind)  # Print HH indices
            print("HL indices:", hl_ind)  # Print HH indices

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
            midpoint_short = {}
            midpoint_long = {}
            point_vhod_long_rr_max = {}
            point_vhod_short_rr_max = {}
            max_high_index_array = {}
            min_low_index_array = {}

            for hl in hl_ind:
                for i in range(hl + 1, len(lows)):
                    if lows[i] < lows[hl]:
                        hl_array.append(i)
                        hl_price_array[i] = lows[hl]
                        hl_start_array.append(hl)
                        break

            print(f'Точки слома HL - {hl_array}')
            print(f'Точки слома HL - {hl_start_array}')

            for lh in lh_ind:
                for i in range(lh + 1, len(highs)):
                    if highs[i] > highs[lh]:
                        lh_array.append(i)
                        lh_price_array[i] = highs[lh]
                        lh_start_array.append(lh)
                        break

            print(f'Точки слома LH - {lh_array}')
            print(f'Точки слома LH - {lh_start_array}')

            for hh in hh_ind:
                for i in range(hh + 1, len(lows)):
                    if lows[i] < lows[hh]:
                        hh_array.append(i)
                        hh_price_array[i] = highs[hh]
                        hh_start_array.append(hh)
                        break

            print(f'Точки слома HH - {hh_array}')
            print(f'Точки слома HH - {hh_start_array}')

            for ll in ll_ind:
                for i in range(ll + 1, len(highs)):
                    if highs[i] > highs[ll]:
                        ll_array.append(i)
                        ll_price_array[i] = highs[ll]
                        ll_start_array.append(ll)
                        break

            print(f'Точки слома LL - {ll_array}')
            print(f'Точки слома LL - {ll_start_array}')

            # Создаем список максимумов и минимумов для каждого дня

            for start, end in zip(midnight_indices[:-1], midnight_indices[1:]):
                daily_max_highs.append(max(highs[start:end]))
                daily_min_lows.append(min(lows[start:end]))

            print(daily_max_highs)
            print(daily_min_lows)

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

                        nearest_hl_idx = min(
                            [hl for hl in hl_array if hl > max_idx] + [lh for lh in lh_array if lh > max_idx] + [ll
                                                                                                                 for
                                                                                                                 ll
                                                                                                                 in
                                                                                                                 ll_array
                                                                                                                 if
                                                                                                                 ll > max_idx],
                            default=None)
                        if nearest_hl_idx is not None:
                            hl_price = hl_price_array[nearest_hl_idx] if nearest_hl_idx in hl_price_array else lows[
                                nearest_hl_idx]
                            ax.scatter(nearest_hl_idx, hl_price, color='grey', s=300, label='Low Below HL Low')
                            ax.plot([max_idx, nearest_hl_idx], [highs[max_idx], hl_price], color='purple',
                                    linestyle='--')
                            print(
                                f"Low after HH at index {max_idx} lower than HL low found at index {nearest_hl_idx}")
                            highs_after_hh.append(nearest_hl_idx)
                            if nearest_hl_idx is not None:
                                hl_price = hl_price_array.get(nearest_hl_idx, lows[nearest_hl_idx])
                                hh_price = hh_price_array.get(nearest_hh_idx, highs[
                                    nearest_hh_idx]) if nearest_hh_idx is not None else None

                                max_high_value = 1
                                max_high_index = nearest_hl_idx

                                # Поиск максимального highs в интервале
                                for idx in range(nearest_hl_idx + 1, len(highs)):
                                    if highs[idx] > max_high_value and highs[idx] <= highs[nearest_hh_idx]:
                                        max_high_index = idx
                                        max_high_value = highs[idx]
                                        max_high_index_array[nearest_hl_idx] = idx

                                    # Условия остановки поиска
                                    if highs[idx] <= midpoint or highs[idx] >= hh_price:
                                        break

                                print(f"Максимальная точка {max_high_value} найдена на индексе {max_high_index}")

                                print("\nRR\n")
                                if hl_price != 0:
                                    price_muv_1pct_short = round(hl_price / 100, 3)
                                    if price_muv_1pct_short != 0:
                                        price_muv_liqvidation_short = round(
                                            (hh_price / price_muv_1pct_short) - 100, 3) if hh_price else None
                                        if price_muv_liqvidation_short:
                                            price_muv_profit_short = round(
                                                100 - (midpoint / price_muv_1pct_short), 3)
                                            RR_short = round(
                                                price_muv_profit_short / price_muv_liqvidation_short, 3)
                                            point_vhod_short[nearest_hl_idx] = hl_price
                                            point_liqvidation_short[nearest_hl_idx] = hh_price if hh_price else \
                                                highs[nearest_hl_idx]
                                            rr_array_short[nearest_hl_idx] = RR_short if RR_short else None
                                            midpoint_short[nearest_hl_idx] = midpoint
                                            print("ШОРТ Сделка - ", price_muv_1pct_short,
                                                  price_muv_liqvidation_short, price_muv_profit_short, RR_short)

                                # Enhanced Short Trade Calculations with Max Price
                                print("\nRR-MAX\n")
                                if max_high_value != 0:
                                    price_muv_1pct_short_max = round(max_high_value / 100, 3)
                                    if price_muv_1pct_short_max != 0:
                                        price_muv_liqvidation_short_max = round(
                                            (highs[nearest_hh_idx] / price_muv_1pct_short_max) - 100,
                                            3) if hh_price else None
                                        if price_muv_liqvidation_short_max:
                                            price_muv_profit_short_max = round(
                                                100 - (midpoint / price_muv_1pct_short_max), 3)
                                            RR_short_max = round(
                                                price_muv_profit_short_max / price_muv_liqvidation_short_max, 3)
                                            point_vhod_short_max[nearest_hl_idx] = max_high_value
                                            point_liqvidation_short_max[nearest_hl_idx] = hh_price if hh_price else \
                                            highs[max_high_index]
                                            rr_array_short_max[
                                                nearest_hl_idx] = RR_short_max if RR_short_max else None
                                            midpoint_short[nearest_hl_idx] = midpoint
                                            print("ШОРТ Сделка - ", point_vhod_short_max, price_muv_1pct_short_max,
                                                  price_muv_liqvidation_short_max, price_muv_profit_short_max,
                                                  RR_short_max, "\n")

                for min_idx in day_min:
                    if lows[min_idx] < daily_min_lows[i - 1]:
                        ax.scatter(min_idx, lows[min_idx], color='blue', s=100, label='Break Below Min')
                        three_minute_long.append(min_idx)

                        nearest_ll_idx = min([ll for ll in ll_start_array if ll >= min_idx], default=None)
                        nearest_lh_idx = min(
                            [lh for lh in lh_array if lh > min_idx] + [hl for hl in hl_array if hl > min_idx] + [hh
                                                                                                                 for
                                                                                                                 hh
                                                                                                                 in
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
                            print(
                                f"High after LL at index {min_idx} higher than LH high found at index {nearest_lh_idx}")
                            lows_after_ll.append(nearest_lh_idx)

                            lh_price = lh_price_array.get(nearest_lh_idx, highs[nearest_lh_idx])
                            ll_price = ll_price_array.get(nearest_ll_idx, lows[
                                nearest_ll_idx]) if nearest_ll_idx is not None else None

                            min_low_value = lows[nearest_lh_idx]
                            min_low_index = nearest_lh_idx

                            # Поиск максимального highs в интервале
                            for idx in range(nearest_lh_idx + 1, len(lows)):
                                if lows[idx] < min_low_value and lows[idx] >= lows[nearest_ll_idx]:
                                    min_low_index = idx
                                    min_low_value = lows[idx]
                                    min_low_index_array[nearest_lh_idx] = idx

                                # Условия остановки поиска
                                if lows[idx] <= midpoint or lows[idx] <= ll_price:
                                    break

                            print(f"Мнимальная точка {min_low_value} найдена на индексе {min_low_index}")

                            print("\nRR\n")
                            if highs[nearest_lh_idx] != 0:
                                price_muv_1pct_long = round(highs[nearest_lh_idx] / 100, 3)
                                if price_muv_1pct_long != 0:
                                    price_muv_liqvidation_long = round(
                                        100 - (highs[nearest_ll_idx] / price_muv_1pct_long), 3)
                                    price_muv_profit_long = round((midpoint / price_muv_1pct_long) - 100, 3)
                                    if price_muv_profit_long and price_muv_liqvidation_long != 0:
                                        RR_long = round(price_muv_profit_long / price_muv_liqvidation_long, 3)
                                        point_vhod_long[nearest_lh_idx] = highs[nearest_lh_idx]
                                        point_liqvidation_long[nearest_lh_idx] = lows[nearest_ll_idx]
                                        rr_array_long[nearest_lh_idx] = RR_long
                                        midpoint_long[nearest_lh_idx] = midpoint
                                        print("ЛОНГ Сделка - ", price_muv_1pct_long, price_muv_liqvidation_long,
                                              price_muv_profit_long, RR_long)
                                    else:
                                        break

                            print("\nRR-MAX\n")
                            if lows[min_low_index] != 0:
                                price_muv_1pct_long_max = round(lows[min_low_index] / 100, 3)
                                if price_muv_1pct_long_max != 0:
                                    price_muv_liqvidation_long_max = round(
                                        100 - (highs[nearest_ll_idx] / price_muv_1pct_long_max), 3)
                                    price_muv_profit_long_max = round((midpoint / price_muv_1pct_long_max) - 100, 3)
                                    RR_long_max = round(price_muv_profit_long_max / price_muv_liqvidation_long_max,
                                                        3)
                                    point_vhod_long_max[nearest_lh_idx] = lows[min_low_index]
                                    point_liqvidation_long_max[nearest_lh_idx] = lows[nearest_ll_idx]
                                    rr_array_long_max[nearest_lh_idx] = RR_long_max
                                    midpoint_long[nearest_lh_idx] = midpoint
                                    print("RR-MAX ЛОНГ Сделка - ", price_muv_1pct_long_max,
                                          price_muv_liqvidation_long_max, price_muv_profit_long_max, RR_long_max)


            def test_point_vhod_reached_first():
                result_short = {}
                for point_vhod, price_vhod in point_vhod_short.items():
                    price_liqvidation = point_liqvidation_short.get(point_vhod, None)
                    midpoint = (daily_max_highs[0] + daily_min_lows[0]) / 2  # для теста берем первый день
                    if price_liqvidation:
                        reached_liqvidation = False
                        reached_midpoint = False
                        for price in highs[point_vhod:]:
                            if price >= price_liqvidation:
                                reached_liqvidation = True
                                break
                            if price <= midpoint:
                                reached_midpoint = True
                                break

                        if reached_liqvidation:
                            print(f"Point {point_vhod} reached liquidation price first.")
                            result_short[point_vhod] = 0
                        elif reached_midpoint:
                            print(f"Point {point_vhod} reached midpoint first.")
                            result_short[point_vhod] = 1
                        else:
                            print(f"Point {point_vhod} reached neither liquidation price nor midpoint.")

                print(result_short)
                return result_short


            result_short = test_point_vhod_reached_first()
            print(result_short)


            def test_point_vhod_long_reached_first():
                result_long = {}
                for point_vhod, price_vhod in point_vhod_long.items():
                    price_liqvidation = point_liqvidation_long.get(point_vhod, None)
                    midpoint = (daily_max_highs[0] + daily_min_lows[0]) / 2  # для теста берем первый день

                    if price_liqvidation:
                        reached_liqvidation = False
                        reached_midpoint = False
                        for price in lows[point_vhod:]:
                            if price <= price_liqvidation:
                                reached_liqvidation = True
                                break
                            if price >= midpoint:
                                reached_midpoint = True
                                break

                        if reached_liqvidation:
                            print(f"Point {point_vhod} reached liquidation price first.")
                            result_long[point_vhod] = 0
                        elif reached_midpoint:
                            print(f"Point {point_vhod} reached midpoint first.")
                            result_long[point_vhod] = 1
                        else:
                            print(f"Point {point_vhod} reached neither liquidation price nor midpoint.")

                return result_long


            result_long = test_point_vhod_long_reached_first()

            print(result_long)

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
                ax.text(mid_point, min_low, str(len(midnight_indices) - idx), color='red', ha='center', va='top')

            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys())

            ax.set_xlim([0, len(hist_data)])
            ax.set_ylim([min(lows) * 0.95, max(highs) * 1.05])


            def three_minute(symbol, exchange, highs_after_hh, lows_after_ll, highs, lows, point_vhod_short,
                             point_vhod_long, point_liqvidation_short, point_liqvidation_long, rr_array_short,
                             rr_array_long, rr_array_long_max, rr_array_short_max, midpoint_short,
                             point_vhod_short_max, max_high_index_array, min_low_index_array, point_vhod_long_max,
                             midpoint_long, result_short, result_long):
                file_path = 'three_minute_strat_eth.json'
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
                        entry['highs_after_hh'] = [
                            {
                                'index': point,
                                'low': lows[point],
                                'point_vhod': point_vhod_short.get(point),
                                'point_liqvidation': point_liqvidation_short.get(point),
                                'rr': rr_array_short.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': max_high_index_array.get(point),
                                'midpoint': midpoint_short.get(point),
                                'max_point_vhod': point_vhod_short_max.get(point),
                                'result': result_short.get(point)
                            }
                            for point in highs_after_hh
                        ]
                        entry['lows_after_ll'] = [
                            {
                                'index': point,
                                'high': highs[point],
                                'point_vhod': point_vhod_long.get(point),
                                'point_liqvidation': point_liqvidation_long.get(point),
                                'rr': rr_array_long.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': min_low_index_array.get(point),
                                'midpoint': midpoint_long.get(point),
                                'max_point_vhod': point_vhod_long_max.get(point),
                                'result': result_long.get(point)
                            }
                            for point in lows_after_ll
                        ]
                        updated = True
                        break

                if not updated:
                    new_entry = {
                        "symbol": symbol,
                        "exchange": exchange,
                        "highs_after_hh": [
                            {
                                'index': point,
                                'low': lows[point],
                                'point_vhod': point_vhod_short.get(point),
                                'point_liqvidation': point_liqvidation_short.get(point),
                                'rr': rr_array_short.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': max_high_index_array.get(point),
                                'midpoint': midpoint_short.get(point),
                                'max_point_vhod': point_vhod_short_max.get(point),
                                'result': result_short.get(point)
                            }
                            for point in highs_after_hh
                        ],
                        "lows_after_ll": [
                            {
                                'index': point,
                                'high': highs[point],
                                'point_vhod': point_vhod_long.get(point),
                                'point_liqvidation': point_liqvidation_long.get(point),
                                'rr': rr_array_long.get(point),
                                'rr_max': rr_array_short_max.get(point),
                                'index_rr_max': min_low_index_array.get(point),
                                'midpoint': midpoint_long.get(point),
                                'max_point_vhod': point_vhod_long_max.get(point),
                                'result': result_long.get(point)
                            }
                            for point in lows_after_ll
                        ]
                    }
                    data.append(new_entry)

                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)


            three_minute(symbol, exchange, highs_after_hh, lows_after_ll, highs, lows, point_vhod_short,
                         point_vhod_long, point_liqvidation_short, point_liqvidation_long, rr_array_short,
                         rr_array_long, rr_array_long_max, rr_array_short_max, midpoint_short, point_vhod_short_max,
                         max_high_index_array, min_low_index_array, point_vhod_long_max, midpoint_long,
                         result_short, result_long)

            # plt.scatter(hh_ind, [highs[i] for i in hh_ind], color='green', label='HH')
            # plt.scatter(hl_ind, [lows[i] for i in hl_ind], color='blue', label='HL')
            # plt.scatter(lh_ind, [highs[i] for i in lh_ind], color='orange', label='LH')
            # plt.scatter(ll_ind, [lows[i] for i in ll_ind], color='red', label='LL')
            print(bull_bos_ends, 'Индексы bos Long')
            print(bear_bos_ends, 'Индексы bos Short')
            print(highs_after_hh, 'Индексы bos Long')
            print(lows_after_ll, 'Индексы bos Short')

            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys())

            ax.set_xlim([0, len(hist_data)])
            ax.set_ylim([min(lows), max(highs)])

            # results = tv.test_highs_after_hh(highs_after_hh, hh_start_array, highs, lows, daily_max_highs,
            #                               daily_min_lows)

            # Вывод результатов тестирования
            # for result in results:
            #     print(
            #         f"Index: {result['idx']}, HH Intersection: {result['hh_intersection']}, Midpoint Intersection: {result['midpoint_intersection']}, Crossed First: {result['crossed_first']}")

            # rsi, rsi_timestamps = tv.calculate_rsi()
            # rsi_df = pd.DataFrame({'timestamp': rsi_timestamps, 'rsi': rsi})
            # rsi_df['hour'] = rsi_df['timestamp'].dt.floor('h')  # Group by hour
            # hourly_rsi = rsi_df.groupby('hour')['rsi'].mean()
            #
            # for hour, avg_rsi in hourly_rsi.items():
            #     print(f"{hour}: {avg_rsi}")

            plt.show()
            plt.close()
            time.sleep(10)
