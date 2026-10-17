"""``num2words`` replacement for misaki (D15): English only, backed by ``inflect`` (MIT).

Implements the call shapes ``misaki.en`` 0.9.4 uses: ``num2words(int)``,
``num2words(int, to="ordinal" | "year" | "cardinal")`` and ``num2words(float)``.
"""

from __future__ import annotations

import functools

import inflect

__all__ = ["num2words"]


@functools.cache
def _engine() -> inflect.engine:
    return inflect.engine()


def _cardinal(n: int) -> str:
    if n < 0:
        return "minus " + _cardinal(-n)
    return str(_engine().number_to_words(n))


def _ordinal(n: int) -> str:
    if n < 0:
        return "minus " + _ordinal(-n)
    return str(_engine().number_to_words(_engine().ordinal(n)))


def _year(n: int) -> str:
    """1984 -> nineteen eighty-four, 1905 -> nineteen oh five, 1900 -> nineteen hundred,
    2005 -> two thousand and five, 2010 -> twenty ten; outside 1000..9999 -> cardinal."""
    if not 1000 <= n <= 9999 or 2000 <= n <= 2009 or n % 1000 == 0:
        return _cardinal(n)
    hi, lo = divmod(n, 100)
    if lo == 0:
        return _cardinal(hi) + " hundred"
    if lo < 10:
        return _cardinal(hi) + " oh " + _cardinal(lo)
    return _cardinal(hi) + " " + _cardinal(lo)


def _decimal(x: float) -> str:
    s = repr(x)
    if "e" in s or "E" in s:
        s = f"{x:f}".rstrip("0").rstrip(".")
    neg = s.startswith("-")
    ip, _, fp = s.lstrip("-").partition(".")
    out = _cardinal(int(ip))
    if fp and fp.strip("0"):
        out += " point " + " ".join(_cardinal(int(d)) for d in fp)
    return ("minus " if neg else "") + out


def num2words(number: float | str, to: str = "cardinal", lang: str = "en", **_: object) -> str:
    if lang != "en":
        raise NotImplementedError(f"compat num2words: lang={lang!r} (English only)")
    if isinstance(number, str):
        number = float(number) if "." in number else int(number)
    if isinstance(number, float) and to == "cardinal":
        return _decimal(number)
    n = int(number)
    if to == "cardinal":
        return _cardinal(n)
    if to == "ordinal":
        return _ordinal(n)
    if to == "year":
        return _year(n)
    raise NotImplementedError(f"compat num2words: to={to!r}")
