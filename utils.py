import time
from datetime import tzinfo, timedelta

ZERO = timedelta(0)
HOUR = timedelta(hours=1)

class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

    
class LocalTimezone(tzinfo):
    """Proxy timezone information from time module. (Django implementation, sans dependencies)"""
    def __init__(self, dt):
        tzinfo.__init__(self)
        self._tzname = self.tzname(dt)

    def __repr__(self):
        return self._tzname

    def utcoffset(self, dt):
        if self._isdst(dt):
            return timedelta(seconds=-time.altzone)
        else:
            return timedelta(seconds=-time.timezone)

    def dst(self, dt):
        if self._isdst(dt):
            return timedelta(seconds=-time.altzone) - timedelta(seconds=-time.timezone)
        else:
            return timedelta(0)

    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.weekday(), 0, -1)
        try:
            stamp = time.mktime(tt)
        except (OverflowError, ValueError):
            # 32 bit systems can't handle dates after Jan 2038, and certain
            # systems can't handle dates before ~1901-12-01:
            #
            # >>> time.mktime((1900, 1, 13, 0, 0, 0, 0, 0, 0))
            # OverflowError: mktime argument out of range
            # >>> time.mktime((1850, 1, 13, 0, 0, 0, 0, 0, 0))
            # ValueError: year out of range
            #
            # In this case, we fake the date, because we only care about the
            # DST flag.
            tt = (2037,) + tt[1:]
            stamp = time.mktime(tt)
        tt = time.localtime(stamp)
        return tt.tm_isdst > 0

    