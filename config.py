
from decouple import config
import logging

DEBUG = config('DEBUG', cast=bool, default=False)

BOT_API_TOKEN = config("BOT_API_TOKEN", cast=str)

_LOGLEVEL = config("LOGLEVEL", default="INFO", cast=str)
LOGLEVEL = getattr(logging, _LOGLEVEL)

GET_UPDATES_TIMEOUT = config('GET_UPDATES_TIMEOUT', cast=int, default=60)

REPORT_CHAT_ID = config('REPORT_ERRORS_CHAT_ID', cast=int, default=507902673)
