import pytz
from django.conf import settings


def datetime2str(datetime):
    return datetime.astimezone(pytz.timezone(settings.TIME_ZONE)).strftime("%m/%d/%Y, %H:%M:%S")
