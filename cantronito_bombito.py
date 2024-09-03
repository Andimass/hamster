import json
import telebot
from telebot import types
import time
import os
import logging
import schedule
import threading
from datetime import datetime, timedelta
from threading import Timer
from collections import defaultdict

bot = telebot.TeleBot("6636610101:AAEfXg6a1IWBguFpCvvN81Cp_NqlmAWsDgU")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_color_data():
    with open('TvDatafeed_2/signals.json', 'r') as file:
        return json.load(file)

def load_signal_data():
    with open('TvDatafeed_2/signals_nw.json', 'r') as file:
        return json.load(file)

subscribers = set()

def save_subscribers():
    try:
        with open('our_subscribers.txt', 'w') as file:
            for subscriber in subscribers:
                file.write(f"{subscriber}\n")
        logger.info(f"Подписчики сохранены: {subscribers}")
    except Exception as e:
        logger.error(f"Ошибка сохранения файла подписчиков: {e}")

def load_subscribers():
    try:
        with open('our_subscribers.txt', 'r') as file:
            for line in file:
                subscribers.add(int(line.strip()))
    except FileNotFoundError:
        logger.info("Файл подписчиков не найден. Создаём новый.")
    except Exception as e:
        logger.error(f"Ошибка загрузки файла подписчиков: {e}")

# Сохраняем время последней отправки сообщения
def save_last_sent_time(last_sent_time):
    try:
        with open('last_sent_time.txt', 'w') as file:
            file.write(last_sent_time.isoformat())
    except Exception as e:
        logger.error(f"Ошибка при сохранении времени последней отправки: {e}")

# Загружаем время последней отправки сообщения
def load_last_sent_time():
    try:
        if os.path.exists('last_sent_time.txt'):
            with open('last_sent_time.txt', 'r') as file:
                last_sent_time_str = file.read().strip()
                return datetime.fromisoformat(last_sent_time_str)
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке времени последней отправки: {e}")
        return None

def load_last_sent_time_nw():
    try:
        if os.path.exists('last_sent_time_nw.txt'):
            with open('last_sent_time_nw.txt', 'r') as file:
                last_sent_time_str = file.read().strip()
                return datetime.fromisoformat(last_sent_time_str)
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке времени последней отправки: {e}")
        return None

last_sent_signal = None
last_signal_sent = None
last_sent_time = load_last_sent_time()
last_sent_time_nw = load_last_sent_time_nw()

@bot.message_handler(commands=['start'])
def start(message):
    subscribers.add(message.chat.id)
    save_subscribers()
    bot.send_message(message.chat.id,
                     "Добро пожаловать!\nВы подписаны на уведомления о новых данных.\nКак только мы найдем новую точку, вы сразу узнаете об этом.")
    bot.send_message(message.chat.id, f"Ваш ID: {message.chat.id}")


@bot.message_handler(commands=['stop'])
def stop(message):
    subscribers.discard(message.chat.id)
    save_subscribers()
    bot.send_message(message.chat.id, "Вы отписаны от уведомлений.")
    bot.send_message(message.chat.id, f"Текущие подписчики: {subscribers}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, 'Неизвестная команда. Попробуйте /start или /getdata.')

def send_signal_to_bot(signal_type):
    message = f"BTC - Dangerous! Возможно {signal_type} манипуляция"
    for subscriber in list(subscribers):
        try:
            bot.send_message(subscriber, message)
            logger.info(f"Отправлено сообщение пользователю {subscriber}: {message}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {subscriber}: {e}")
            # Если произошла ошибка, удаляем подписчика
            subscribers.discard(subscriber)
            save_subscribers()


def check_for_new_signal_nw():
    global last_signal_sent
    signals = load_signal_data()

    if not signals:
        logger.info("Нет сигналов в файле.")
        return

    latest_signal = signals[-1]  # Берем последний сигнал из списка
    current_time = datetime.now()
    # Проверяем, не был ли уже отправлен этот сигнал
    if last_signal_sent is None or latest_signal != last_signal_sent:
        if last_sent_time_nw is None or (current_time - last_sent_time_nw) >= timedelta(days=2):
            signal_type = latest_signal.get("signal_type")
            if signal_type in ["long", "short"]:
                send_signal_to_bot(signal_type)
                last_signal_sent = latest_signal

def check_for_new_signal():
    global last_sent_signal
    global last_sent_time

    signals = load_color_data()

    if not signals:
        logger.info("Сигналы отсутствуют.")
        return

    latest_signal = signals[-1]

    # Проверяем, прошло ли 24 часа с момента последней отправки
    current_time = datetime.now()
    if last_sent_time is None or (current_time - last_sent_time) >= timedelta(days=2):
        if last_sent_signal is None or latest_signal != last_sent_signal:
            message = f"BTC - {latest_signal['signal_type']}"
            for subscriber in subscribers:
                try:
                    bot.send_message(subscriber, message)
                    logger.info(f"Сообщение отправлено пользователю: {subscriber}")
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {subscriber}: {e}")

            # Обновляем время последней отправки и сохраняем его
            last_sent_signal = latest_signal
            last_sent_time = current_time
            save_last_sent_time(last_sent_time)

if __name__ == '__main__':
    while True:
        try:
            load_subscribers()
            check_for_new_signal()
            check_for_new_signal_nw()
            bot.polling(none_stop=True, timeout=123)
        except Exception as e:
            logger.error(f"Ошибка при поллинге: {e}")
            time.sleep(10)

