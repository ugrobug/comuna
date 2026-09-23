"""Memoization confined to one read operation, never shared across requests."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps


_values = ContextVar("read_context_values", default=None)


@contextmanager
def read_context():
    token = _values.set({})
    try:
        yield
    finally:
        _values.reset(token)


def memoize_read(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        values = _values.get()
        if values is None:
            return function(*args, **kwargs)
        key = (function, args, tuple(sorted(kwargs.items())))
        if key not in values:
            values[key] = function(*args, **kwargs)
        return values[key]

    return wrapped


def with_read_context(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method not in {"GET", "HEAD"}:
            return view(request, *args, **kwargs)
        with read_context():
            return view(request, *args, **kwargs)

    return wrapped
