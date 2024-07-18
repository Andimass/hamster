import json
import telebot
from telebot import types
import time
import os
import logging
import schedule
import threading
from datetime import datetime
from threading import Timer

# bot = telebot.TeleBot("6331788018:AAGFRq3ScUv3OCw5TQPxCI_15K2vy-wnTL8")
bot = telebot.TeleBot("7379631512:AAE-k1Cy_lctHWhxnLQZFc3rV4d6RspzSlY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data():
    try:
        with open('tvDatafeed/super_tochka.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        return []

def load_color_data():
    # Загружаем данные из JSON файла
    with open('TvDatafeed_2/current_colors.json', 'r') as file:
        return json.load(file)
def load_rsi_data():
    try:
        with open('TvDatafeed_2/rsi_comparisons.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла RSI: {e}")
        return {}

def load_macd_data():
    try:
        with open('TvDatafeed_2/macd_comparisons.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла RSI: {e}")
        return {}

def load_nw_data():
    try:
        with open('TvDatafeed_2/nw_conditions.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла RSI: {e}")
        return {}

def load_bb_data():
    try:
        with open('TvDatafeed_2/band_conditions.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла RSI: {e}")
        return {}

def load_stoch_data():
    try:
        with open('TvDatafeed_2/stoch_comparisons.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла RSI: {e}")
        return {}

def load_gauss_data():
    try:
        with open('TvDatafeed_2/gauss.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки файла RSI: {e}")
        return {}

subscribers = set()

super_tochka_data = load_data()
current_data = super_tochka_data

def save_subscribers():
    try:
        with open('subscribers.txt', 'w') as file:
            for subscriber in subscribers:
                file.write(f"{subscriber}\n")
    except Exception as e:
        logger.error(f"Ошибка сохранения файла подписчиков: {e}")

def load_subscribers():
    try:
        with open('subscribers.txt', 'r') as file:
            for line in file:
                subscribers.add(int(line.strip()))
    except FileNotFoundError:
        logger.info("Файл подписчиков не найден. Создаём новый.")
    except Exception as e:
        logger.error(f"Ошибка загрузки файла подписчиков: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    subscribers.add(message.chat.id)
    save_subscribers()
    bot.send_message(message.chat.id,
                     "Вы подписаны на уведомления о новых данных.\nКак только мы найдем новую точку, вы сразу узнаете об этом.\nЧтобы получить все данные введите команду /getdata")
    bot.send_message(message.chat.id, f"Ваш ID: {message.chat.id}")
    bot.send_message(message.chat.id, "Добро пожаловать! Используйте команду /check_rsi для проверки RSI.")

@bot.message_handler(commands=['stop'])
def stop(message):
    subscribers.discard(message.chat.id)
    save_subscribers()
    bot.send_message(message.chat.id, "Вы отписаны от уведомлений.")
    bot.send_message(message.chat.id, f"Текущие подписчики: {subscribers}")

@bot.message_handler(commands=['getdata'])
def send_data(message):
    data = load_data()  # Загрузка данных
    for coin_data in data:
        symbol = coin_data.get('symbol', 'Unknown symbol')
        exchange = coin_data.get('exchange', 'Unknown exchange')
        process_data_entries(coin_data.get('data', []), message.chat.id, symbol, exchange, "Шорт")
        process_data_entries(coin_data.get('data_ll', []), message.chat.id, symbol, exchange, "Лонг")

@bot.message_handler(commands=['getdata2'])
def send_data_2(message):
    try:
        with open('tvDatafeed_2/three_minute.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
    except Exception as e:
        bot.send_message(message.chat.id, f"Error loading data: {e}")
        return

    response = ""
    for coin_data in data:
        symbol = coin_data.get('symbol', 'Unknown symbol')

        # Check highs_after_hh
        highs_after_hh = coin_data.get('highs_after_hh', [])
        for item in highs_after_hh:
            if item['index'] > 1000:
                response += f"{symbol} - SHORT at index {item['index']}\n"

        # Check lows_after_ll
        lows_after_ll = coin_data.get('lows_after_ll', [])
        for item in lows_after_ll:
            if item['index'] > 1000:
                response += f"{symbol} - LONG at index {item['index']}\n"

    if not response:
        response = "No data available."

    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['check_rsi'])
def check_rsi(message):
    rsi_data = load_rsi_data()
    result = ""
    comparisons = rsi_data.get("comparisons", {})
    last_rsi_1h = rsi_data.get("last_rsi_1h", "N/A")

    result = ""
    result += "✅" if comparisons.get("2h < 4h") else "❌"
    result += "✅" if comparisons.get("1h < 2h") else "❌"
    result += "✅" if comparisons.get("30m < 1h") else "❌"
    result += "✅" if comparisons.get("15m < 30m") else "❌"

    bot.send_message(message.chat.id, f"RSI {result} - {last_rsi_1h}")

def process_data_entries(data_entries, chat_id, symbol, exchange, direction):
    if not data_entries:
        caption = f"Монета: {symbol}\nНа данный момент данных нет."
        send_coin_image_with_caption(chat_id, symbol, caption, send_image=False)
    else:
        direction_text = "SHORT" if direction == "Шорт" else "LONG"
        for entry in data_entries:
            value = entry.get('value')
            timestamp = entry.get('time')
            point_vhod = entry.get('point_vhod', 'Н/Д')
            plecho = entry.get('plecho', 'x1')
            point_vhod_formatted = f"{float(point_vhod):.3f}" if point_vhod is not None else 'Н/Д'
            liqvid = entry.get('liqvid', 'Н/Д')
            caption = f"{symbol} {direction_text} 4h FVG\nТВ {point_vhod_formatted}\nx{plecho}\nSL {liqvid}"
            send_coin_image_with_caption(chat_id, symbol, caption)

def send_coin_image_with_caption(chat_id, symbol, caption, send_image=True):
    image_path = os.path.join('photo', f'{symbol}.jpg')
    if send_image and os.path.exists(image_path):
        with open(image_path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption=caption)
    else:
        bot.send_message(chat_id, caption)

def notify_subscribers_about_target_value(data, subscribers):
    for coin_data in data:
        symbol = coin_data['symbol']
        exchange = coin_data.get('exchange', 'Unknown exchange')  # Добавлено получение биржи
        data_points = coin_data.get('data', []) + coin_data.get('data_ll', [])  # Объединяем данные для SHORT и LONG

        for data_point in data_points:
            if data_point['value'] >= 499:  # Условие для значений 499 и выше
                direction = "Шорт" if 'll' in data_point else "Лонг"
                # Подготавливаем данные как единичный список для использования в process_data_entries
                prepared_data = [data_point]

                for chat_id in subscribers:
                    process_data_entries(prepared_data, chat_id, symbol, exchange, direction)

def check_updates():
    global current_data
    new_data = load_data()
    notify_subscribers_about_target_value(new_data, subscribers)
    current_data = new_data
    logger.info(f"Текущие подписчики: {subscribers}")


def continuous_rsi_check():
    previous_short_result = ""
    previous_long_result = ""

    while True:
        rsi_data = load_rsi_data()
        comparisons = rsi_data.get("comparisons", {})
        last_rsi_1h = rsi_data.get("last_rsi_1h", "N/A")

        long_result = ""
        long_result += "✅" if comparisons.get("2h < 4h") else "❌"
        long_result += "✅" if comparisons.get("1h < 2h") else "❌"
        long_result += "✅" if comparisons.get("30m < 1h") else "❌"
        long_result += "✅" if comparisons.get("15m < 30m") else "❌"

        if long_result == "✅✅✅✅" and long_result != previous_long_result:
            for chat_id in subscribers:
                bot.send_message(chat_id, f"RSI {long_result} - {last_rsi_1h}")
            previous_long_result = long_result

        time.sleep(1)


@bot.message_handler(commands=['check_indicator'])
def check_gauss(message):
    hull_data = load_color_data()
    result = ""

    # Итерация по данным для каждого таймфрейма
    for timeframe, values in hull_data.items():
        last_close = values["last_close_price"]
        last_hull = values["last_hull_value"]

        # Сравниваем закрытие с Hull MA
        if last_close > last_hull:
            result += "✅"
        else:
            result += "❌"

    # Отправка результатов
    bot.send_message(message.chat.id, f"TREND: {result}")

    gauss_data = load_gauss_data()
    result = ""

    # Итерируем через каждое значение в данных Гаусса
    for key, value in gauss_data.items():
        if value == 1:
            result += "✅"
        else:
            result += "❌"

    # Формируем ответное сообщение
    bot.send_message(message.chat.id, f"GAUSS: {result}")
    macd_data = load_macd_data()
    result = ""

    # Итерируем через каждое значение в данных Гаусса
    for key, value in macd_data.items():
        if value == 1:
            result += "✅"
        else:
            result += "❌"

    # Формируем ответное сообщение
    bot.send_message(message.chat.id, f"MACD: {result}")
    stoch_data = load_stoch_data()
    result = ""
    result_1h_k = round(
        stoch_data.get('last_values', {}).get('last_k', 0))  # Округляем и обрабатываем отсутствие данных
    result_1h_d = round(stoch_data.get('last_values', {}).get('last_d', 0))  # Так же, как и для K

    # Итерируем через каждое значение в данных Гаусса
    for key, value in stoch_data.items():
        if key != 'last_values':
            if value == 1:
                result += "✅"
            else:
                result += "❌"

    # Формируем ответное сообщение
    bot.send_message(message.chat.id, f"STOCH: {result}, K - {result_1h_k}, D - {result_1h_d}")
    rsi_data = load_rsi_data()
    result = ""
    comparisons = rsi_data.get("comparisons", {})
    last_rsi_1h = rsi_data.get("last_rsi_1h", "N/A")


    result += "❌" if comparisons.get("15m < 30m") else "✅"
    result += "❌" if comparisons.get("30m < 1h") else "✅"
    result += "❌" if comparisons.get("1h < 2h") else "✅"
    result += "❌" if comparisons.get("2h < 4h") else "✅"


    bot.send_message(message.chat.id, f"RSI: {result} - {last_rsi_1h}")


    nw_data = load_nw_data()  # Функция загружает данные из JSON-файла
    nw_long_result = "NW ⬇️ -"
    nw_short_result = "NW ⬆️ -"

    # Список таймфреймов в порядке от меньшего к большему
    timeframes = ["Interval.in_1_hour", "Interval.in_2_hour", "Interval.in_4_hour", "Interval.in_daily"]

    # Итерация по каждому таймфрейму и проверка условий
    for timeframe in timeframes:
        values = nw_data.get(timeframe, {})

        # Добавление символов для Long
        if values.get("is_below_lower_close", False):
            nw_long_result += " ✅"
        elif values.get("is_below_lower_low", False):
            nw_long_result += " ⤴️"
        else:
            nw_long_result += " ❌"

        # Добавление символов для Short
        if values.get("is_above_upper_close", False):
            nw_short_result += " ✅"
        elif values.get("is_above_upper_high", False):
            nw_short_result += " ⤵️"
        else:
            nw_short_result += " ❌"

    # Отправка итогового сообщения пользователю
    result = f"{nw_short_result}\n{nw_long_result}"
    bot.send_message(message.chat.id, result)


    bb_data = load_bb_data()  # Функция загружает данные из JSON-файла
    bb_long_result = "BOLLINGER ⬇️ -"
    bb_short_result = "BOLLINGER ⬆️ -"

    # Список таймфреймов в порядке от меньшего к большему
    timeframes = ["Interval.in_1_hour", "Interval.in_2_hour", "Interval.in_4_hour", "Interval.in_daily"]

    # Итерация по каждому таймфрейму и проверка условий
    for timeframe in timeframes:
        values = bb_data.get(timeframe, {})

        # Добавление символов для Long
        if values.get("is_below_lower_close", False):
            bb_long_result += " ✅"
        elif values.get("is_below_lower_low", False):
            bb_long_result += " ⤴️"
        else:
            bb_long_result += " ❌"

        # Добавление символов для Short
        if values.get("is_above_upper_close", False):
            bb_short_result += " ✅"
        elif values.get("is_above_upper_high", False):
            bb_short_result += " ⤵️"
        else:
            bb_short_result += " ❌"

    # Отправка итогового сообщения пользователю
    result = f"{bb_short_result}\n{bb_long_result}"
    bot.send_message(message.chat.id, result)

    try:
        with open('TvDatafeed_2/divergences_per_timeframe.json', 'r', encoding='utf-8') as file:
            divergence_data = json.load(file)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка загрузки данных: {e}")
        return

    # Список таймфреймов в порядке от меньшего к большему
    timeframes = ["in_1_hour", "in_2_hour", "in_4_hour", "in_daily"]

    # Сопоставление количества с эмодзи
    emoji_map = {
        0: '0️⃣',
        1: '1️⃣',
        2: '2️⃣',
        3: '3️⃣',
        4: '4️⃣',
        5: '5️⃣',
        6: '6️⃣'
    }

    # Строим результаты для bullish и bearish
    bullish_result = []
    bearish_result = []

    for timeframe in timeframes:
        timeframe_data = divergence_data.get(timeframe, {})
        bullish_count = len(timeframe_data.get('divergences', {}).get('bullish', []))
        bearish_count = len(timeframe_data.get('divergences', {}).get('bearish', []))

        # Добавляем результат с соответствующим эмодзи
        bullish_result.append(emoji_map.get(bullish_count, '6️⃣+'))
        bearish_result.append(emoji_map.get(bearish_count, '6️⃣+'))

    # Объединяем результаты и отправляем пользователю
    bullish_message = "Divergences ⬆️: " + ''.join(bullish_result)
    bearish_message = "Divergences ⬇️: " + ''.join(bearish_result)

    bot.send_message(message.chat.id, f'{bullish_message}\n{bearish_message}')

@bot.message_handler(commands=['check_gauss'])
def check_gauss(message):
    stoch_data = load_stoch_data()
    result = ""

    # Итерируем через каждое значение в данных Гаусса
    for key, value in stoch_data.items():
        if value == 1:
            result += "✅"
        else:
            result += "❌"

    # Формируем ответное сообщение
    bot.send_message(message.chat.id, f"STOCH CHECK: {result}")

@bot.message_handler(commands=['check_gauss'])
def check_macd(message):
    macd_data = load_macd_data()
    result = ""

    # Итерируем через каждое значение в данных Гаусса
    for key, value in macd_data.items():
        if value == 1:
            result += "✅"
        else:
            result += "❌"

    # Формируем ответное сообщение
    bot.send_message(message.chat.id, f"MACD CHECK: {result}")

@bot.message_handler(commands=['check_divergences'])
def check_divergences(message):
    # Загружаем данные дивергенций
    try:
        with open('TvDatafeed_2/divergences_per_timeframe.json', 'r', encoding='utf-8') as file:
            divergence_data = json.load(file)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка загрузки данных: {e}")
        return

    # Список таймфреймов в порядке от меньшего к большему
    timeframes = ["in_1_hour", "in_2_hour", "in_4_hour", "in_daily"]

    # Сопоставление количества с эмодзи
    emoji_map = {
        0: '0️⃣',
        1: '1️⃣',
        2: '2️⃣',
        3: '3️⃣',
        4: '4️⃣',
        5: '5️⃣',
        6: '6️⃣'
    }

    # Строим результаты для bullish и bearish
    bullish_result = []
    bearish_result = []

    for timeframe in timeframes:
        timeframe_data = divergence_data.get(timeframe, {})
        bullish_count = len(timeframe_data.get('divergences', {}).get('bullish', []))
        bearish_count = len(timeframe_data.get('divergences', {}).get('bearish', []))

        # Добавляем результат с соответствующим эмодзи
        bullish_result.append(emoji_map.get(bullish_count, '6️⃣+'))
        bearish_result.append(emoji_map.get(bearish_count, '6️⃣+'))

    # Объединяем результаты и отправляем пользователю
    bullish_message = "Divergences ✅: " + ''.join(bullish_result)
    bearish_message = "Divergences ❌: " + ''.join(bearish_result)

    bot.send_message(message.chat.id, bullish_message)

def continuous_gauss_check():
    while True:
        try:
            gauss_data = load_gauss_data()
            result = ("✅✅✅✅✅" if all(value == 1 for value in gauss_data.values()) else
                      "❌❌❌❌❌" if all(value == 0 for value in gauss_data.values()) else
                      None)  # Изменено на None для случаев смешанных значений

            if result != None:  # Проверяем, есть ли результат, иначе пропускаем отправку
                for chat_id in subscribers:
                    try:
                        bot.send_message(chat_id, f"GAUSS CHECK {result}")
                    except telebot.apihelper.ApiTelegramException as e:
                        if e.error_code == 403:
                            logger.info(f"Bot was blocked by the user {chat_id}")
                            # Здесь можно добавить код для удаления этого пользователя из списка подписчиков, если нужно
                    except Exception as e:
                        logger.error(f"Failed to send message to {chat_id}. Error: {e}")
        except Exception as e:
            logger.error(f"Error during GAUSS check: {e}")
        time.sleep(300)  # пауза между проверками


# @bot.message_handler(commands=['instruction'])
# def send_instruction(message):
#     instruction_text = """
#     📄 Инструкция по использованию бота:
#     ➡️ /start - подписаться на уведомления.
#     ➡️ /stop - отписаться от уведомлений.
#     ➡️ /check_indicator - проверить индикаторы.
#     ➡️ /instruction - получить эту инструкцию.
#
#     Инструкция по Индикаторам:
#
# Trend
# Таймфреймы - Час / 2 Часа / 4 Часа / День.
# Логика - Что, над чем? - трендовая над ценой или цена над трендовой.
#
# Gauss
# Таймфреймы - 5 Минут / 15 Минут / 30 Минут / Час / 4 Часа.
# Логика - Направление линии гаусса - Вверх/Вниз.
#
# MACD
# Таймфреймы - 15 Минут / 30 Минут / Час / 2 Часа / 4 Часа.
# Логика - Что, над чем? - MACD над сигнальной или сигнальная над MACD.
#
# STOCH
# Таймфреймы - 15 Минут / 30 Минут / Час / 2 Часа / 4 Часа.
# Логика - Что, над чем? - K над D или D над K.
#
# RSI
# Таймфреймы - 15 Минут / 30 Минут / Час / 2 Часа / 4 Часа.
# Логика - Положение младших таймфреймов относительно старших.
#
# Nadaraya-Watson
# Таймфреймы - Час / 2 Часа / 4 Часа / День.
# Логика - Пересечение или закрепление на канальных линиях.
#
# BOLLINGER
# Таймфреймы - Час / 2 Часа / 4 Часа / День.
# Логика - Пересечение или закрепление на канальных линиях.
#
# Divergences
# Таймфреймы - Час / 2 Часа / 4 Часа / День.
# Логика - Кол-во диверов на заданных таймфреймах и промежутках.
#
# Используйте команды для управления ботом и получения информации в реальном времени!
#     """
#     bot.send_message(message.chat.id, instruction_text)

def save_results():
    hull_data = load_color_data()
    result = ""

    for timeframe, values in hull_data.items():
        last_close = values["last_close_price"]
        last_hull = values["last_hull_value"]

        if last_close > last_hull:
            result += "✅"
        else:
            result += "❌"

    trend_result = f"TREND: {result}"

    gauss_data = load_gauss_data()
    result = ""

    for key, value in gauss_data.items():
        if value == 1:
            result += "✅"
        else:
            result += "❌"

    gauss_result = f"GAUSS: {result}"

    macd_data = load_macd_data()
    result = ""

    for key, value in macd_data.items():
        if value == 1:
            result += "✅"
        else:
            result += "❌"

    macd_result = f"MACD: {result}"

    stoch_data = load_stoch_data()
    result = ""
    result_1h_k = round(stoch_data.get('last_values', {}).get('last_k', 0))
    result_1h_d = round(stoch_data.get('last_values', {}).get('last_d', 0))

    for key, value in stoch_data.items():
        if key != 'last_values':
            if value == 1:
                result += "✅"
            else:
                result += "❌"

    stoch_result = f"STOCH: {result}, K - {result_1h_k}, D - {result_1h_d}"

    rsi_data = load_rsi_data()
    result = ""
    comparisons = rsi_data.get("comparisons", {})
    last_rsi_1h = rsi_data.get("last_rsi_1h", "N/A")

    result += "❌" if comparisons.get("15m < 30m") else "✅"
    result += "❌" if comparisons.get("30m < 1h") else "✅"
    result += "❌" if comparisons.get("1h < 2h") else "✅"
    result += "❌" if comparisons.get("2h < 4h") else "✅"

    rsi_result = f"RSI: {result} - {last_rsi_1h}"

    nw_data = load_nw_data()
    nw_long_result = "NW ⬇️ -"
    nw_short_result = "NW ⬆️ -"

    timeframes = ["Interval.in_1_hour", "Interval.in_2_hour", "Interval.in_4_hour", "Interval.in_daily"]

    for timeframe in timeframes:
        values = nw_data.get(timeframe, {})

        if values.get("is_below_lower_close", False):
            nw_long_result += " ✅"
        elif values.get("is_below_lower_low", False):
            nw_long_result += " ⤴️"
        else:
            nw_long_result += " ❌"

        if values.get("is_above_upper_close", False):
            nw_short_result += " ✅"
        elif values.get("is_above_upper_high", False):
            nw_short_result += " ⤵️"
        else:
            nw_short_result += " ❌"

    nw_result = f"{nw_short_result}\n{nw_long_result}"

    bb_data = load_bb_data()
    bb_long_result = "BOLLINGER ⬇️ -"
    bb_short_result = "BOLLINGER ⬆️ -"

    for timeframe in timeframes:
        values = bb_data.get(timeframe, {})

        if values.get("is_below_lower_close", False):
            bb_long_result += " ✅"
        elif values.get("is_below_lower_low", False):
            bb_long_result += " ⤴️"
        else:
            bb_long_result += " ❌"

        if values.get("is_above_upper_close", False):
            bb_short_result += " ✅"
        elif values.get("is_above_upper_high", False):
            bb_short_result += " ⤵️"
        else:
            bb_short_result += " ❌"

    bb_result = f"{bb_short_result}\n{bb_long_result}"

    try:
        with open('TvDatafeed_2/divergences_per_timeframe.json', 'r', encoding='utf-8') as file:
            divergence_data = json.load(file)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return

    timeframes = ["in_1_hour", "in_2_hour", "in_4_hour", "in_daily"]

    emoji_map = {
        0: '0️⃣',
        1: '1️⃣',
        2: '2️⃣',
        3: '3️⃣',
        4: '4️⃣',
        5: '5️⃣',
        6: '6️⃣'
    }

    bullish_result = []
    bearish_result = []

    for timeframe in timeframes:
        timeframe_data = divergence_data.get(timeframe, {})
        bullish_count = len(timeframe_data.get('divergences', {}).get('bullish', []))
        bearish_count = len(timeframe_data.get('divergences', {}).get('bearish', []))

        bullish_result.append(emoji_map.get(bullish_count, '6️⃣+'))
        bearish_result.append(emoji_map.get(bearish_count, '6️⃣+'))

    bullish_message = "Divergences ⬆️: " + ''.join(bullish_result)
    bearish_message = "Divergences ⬇️: " + ''.join(bearish_result)

    final_result = {
        "timestamp": datetime.now().isoformat(),
        "TREND": trend_result,
        "GAUSS": gauss_result,
        "MACD": macd_result,
        "STOCH": stoch_result,
        "RSI": rsi_result,
        "NW": nw_result,
        "BOLLINGER": bb_result,
        "DIVERGENCES": f'{bullish_message}\n{bearish_message}'
    }

    try:
        with open('data_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    data.append(final_result)

    with open('data_results.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    Timer(300, save_results).start()


save_results()

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, 'Неизвестная команда. Попробуйте /start или /getdata.')



def read_sent_values():
    try:
        with open('sent_values.json', 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def update_sent_values(symbol, point_vhod):
    sent_values = read_sent_values()
    sent_values[symbol] = point_vhod
    with open('sent_values.json', 'w') as file:
        json.dump(sent_values, file, indent=4)

def check_three_minute_data_continuously():
    def send_photo_to_subscribers(symbol, caption):
        photo_path = os.path.join('photo', f'{symbol}.jpg')
        if os.path.exists(photo_path):
            for chat_id in subscribers:
                try:
                    with open(photo_path, 'rb') as photo:
                        bot.send_photo(chat_id, photo, caption=caption)
                except Exception as e:
                    logger.error(f"Failed to send photo to {chat_id}. Error: {e}")
        else:
            logger.error(f"Image file not found: {photo_path}")
            for chat_id in subscribers:
                bot.send_message(chat_id, caption)

    def check_three_minute_data():
        last_index_path = 'last_notified_index.txt'
        try:
            with open(last_index_path, 'r') as f:
                last_notified_index = int(f.read().strip())
        except FileNotFoundError:
            last_notified_index = 0

        try:
            with open('tvDatafeed_2/three_minute.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            logger.error(f"Error loading three_minute data: {e}")
            return

        sent_values = read_sent_values()
        max_notified_index = last_notified_index
        for coin_data in data:
            symbol = coin_data['symbol']

            # Check highs_after_hh
            for item in coin_data.get('highs_after_hh', []):
                if item['index'] > 1498 and item.get('point_vhod') != sent_values.get(symbol):
                    logger.info(f"Found qualifying index in highs_after_hh: {item['index']}")
                    caption = (f"{symbol}\nPDH перебит\n"
                               f"Вход - {item.get('point_vhod', 'Не указан')}\n"
                               f"Ликвидация - {item.get('point_liqvidation', 'Не указан')}\n"
                               f"RR - {item.get('rr', 'Не указан')}\n")
                    send_photo_to_subscribers(symbol, caption)
                    update_sent_values(symbol, item.get('point_vhod'))
                    max_notified_index = max(max_notified_index, item['index'])

            # Check lows_after_ll
            for item in coin_data.get('lows_after_ll', []):
                if item['index'] > 1498 and item.get('point_vhod') != sent_values.get(symbol):
                    logger.info(f"Found qualifying index in lows_after_ll: {item['index']}")
                    caption = (f"{symbol}\nPDL перебит\n"
                               f"Вход - {item.get('point_vhod', 'Не указан')}\n"
                               f"Ликвидация - {item.get('point_liqvidation', 'Не указан')}\n"
                               f"RR - {item.get('rr', 'Не указан')}\n")
                    send_photo_to_subscribers(symbol, caption)
                    update_sent_values(symbol, item.get('point_vhod'))
                    max_notified_index = max(max_notified_index, item['index'])

        if max_notified_index > last_notified_index:
            with open(last_index_path, 'w') as f:
                f.write(str(max_notified_index))

    def send_message_to_subscribers(caption):
        faulty_subscribers = []
        for chat_id in subscribers:
            try:
                logger.info(f"Sending message to subscriber {chat_id}.")
                bot.send_message(chat_id, caption)
            except telebot.apihelper.ApiTelegramException as e:
                logger.error(f"Failed to send message to {chat_id}. Error: {e}")
                faulty_subscribers.append(chat_id)

        # Optional: Remove faulty subscribers
        for chat_id in faulty_subscribers:
            subscribers.discard(chat_id)
            logger.info(f"Removed faulty subscriber: {chat_id}")
            save_subscribers()

    def run_continuously():
        while True:
            check_three_minute_data()
            time.sleep(10)

    thread = threading.Thread(target=run_continuously)
    thread.daemon = True
    thread.start()

def clear_console():

    os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == '__main__':

    while True:
        try:
            load_subscribers()
            schedule.every(1).minute.do(check_updates)
            check_three_minute_data_continuously()
            continuous_rsi_check_thread = threading.Thread(target=continuous_rsi_check)
            continuous_rsi_check_thread.daemon = True
            continuous_rsi_check_thread.start()
            thread = threading.Thread(target=continuous_gauss_check)
            thread.start()
            bot.polling(none_stop=True, timeout=123)
        except Exception as e:
            logger.error(f"Ошибка при поллинге: {e}")
            time.sleep(10)
        schedule.run_pending()
        schedule.every(1).minutes.do(clear_console)
        time.sleep(1)

