import datetime

FORMAT_DATE_TIME = "%d/%m/%Y %H:%M"
FORMAT_DAY_MONTH_YEAR = "%d/%m/%Y"
FORMAT_DATE_MONTH_YEAR = "%m/%Y"
FORMAT_DATE_DAY_HOUR = "Dia: %d Hora: %H:%M "

def subtract_one_month(t):
    one_day = datetime.timedelta(days=1)
    one_month_earlier = t - one_day
    while one_month_earlier.month == t.month or one_month_earlier.day > t.day:
        one_month_earlier -= one_day
    return one_month_earlier