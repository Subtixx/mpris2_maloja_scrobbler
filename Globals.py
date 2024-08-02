import time
import datetime
import logging

logging_format = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger("dbus-scrobbler")

def get_unix_timestamp():
    return int(time.mktime(datetime.datetime.now().timetuple()))