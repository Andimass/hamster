from datetime import datetime


def timedelta_days(datetime_str_1, datetime_str_2):
    # Преобразуем строки в объекты datetime
    date1 = datetime.strptime(datetime_str_1, '%Y/%m/%d %H:%M:%S')
    date2 = datetime.strptime(datetime_str_2, '%Y/%m/%d %H:%M:%S')

    # Вычисляем разницу в днях
    delta = abs(date2 - date1)
    return delta.days


# Пример вызова функции
difference = timedelta_days('2019/05/10 00:00:00', '2019/10/04 00:00:00')

print('От начала посевной до начала сбора урожая прошло', difference, 'дней.')