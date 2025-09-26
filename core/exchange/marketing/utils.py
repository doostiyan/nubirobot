from datetime import datetime

import pytz

from exchange.settings import TIME_ZONE


def parse_time(value: str, _format: str):
    naive_dt = datetime.strptime(value, _format)
    return pytz.timezone(TIME_ZONE).localize(naive_dt, is_dst=None)
