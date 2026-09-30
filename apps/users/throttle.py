# path: apps/users/throttle.py

"""Brute-force protection for the sign-in page.

Failed sign-ins are counted per submitted phone number and per client IP in
Django's cache. Too many failures lock further attempts (correct password
included) until WINDOW passes without a new failure. Keyed on what was TYPED,
not on whether an account exists, so the lock cannot be used to find out which
phone numbers have accounts.

The cache is per process (Django's default local-memory cache): with several
server processes each keeps its own counters, and a restart clears them. That is
enough to stop guessing from a browser; swap CACHES for a shared cache if the
app ever runs as several processes.
"""

from django.core.cache import cache

MAX_FAILS_PER_PHONE = 5
MAX_FAILS_PER_IP = 30
WINDOW_SECONDS = 15 * 60


def _phone_key(phone):
    return f"login-fails:phone:{phone}"


def _ip_key(ip):
    return f"login-fails:ip:{ip}"


def client_ip(request):
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def is_locked(phone, ip):
    return (
        cache.get(_phone_key(phone), 0) >= MAX_FAILS_PER_PHONE
        or cache.get(_ip_key(ip), 0) >= MAX_FAILS_PER_IP
    )


def record_failure(phone, ip):
    for key in (_phone_key(phone), _ip_key(ip)):
        cache.set(key, cache.get(key, 0) + 1, WINDOW_SECONDS)


def reset(phone):
    cache.delete(_phone_key(phone))
