"""Canonical JSON (RFC 8785 subset), SHA-256 content hashing and integer-microsecond instants.

Design rule (fixes old defect "ISO strings compared lexicographically"): every instant inside
the engine is an ``int`` of microseconds since the Unix epoch (UTC). Strings are parsed once at
the boundary and only formatted again for output/hashing.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
US_PER_S = 1_000_000
NEG_INF = -(1 << 62)
POS_INF = 1 << 62
_MAX_SAFE_INT = 2 ** 53
_FRAC = re.compile(r"\.(\d+)")


# --------------------------------------------------------------------------- instants
def parse_instant(x: Any) -> int:
    """Parse ISO-8601 (timezone REQUIRED), tz-aware datetime, or int microseconds."""
    if isinstance(x, bool):
        raise TypeError("bool is not an instant")
    if isinstance(x, int):
        return x
    if isinstance(x, datetime):
        if x.tzinfo is None:
            raise ValueError("naive datetime rejected: a timezone is required")
        return (x.astimezone(timezone.utc) - EPOCH) // timedelta(microseconds=1)
    if isinstance(x, str):
        s = x.strip()
        if s.endswith(("Z", "z")):
            s = s[:-1] + "+00:00"
        s = _FRAC.sub(lambda m: "." + (m.group(1) + "000000")[:6], s, count=1)
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            raise ValueError(f"naive timestamp rejected (no timezone): {x!r}")
        return parse_instant(dt)
    raise TypeError(f"cannot parse instant from {type(x)}")


def fmt_instant(us: int) -> str:
    dt = EPOCH + timedelta(microseconds=int(us))
    return f"{dt:%Y-%m-%dT%H:%M:%S}.{dt.microsecond:06d}Z"


def sec_to_us(x: Any) -> int:
    return int((Decimal(str(x)) * US_PER_S).to_integral_value(rounding=ROUND_HALF_EVEN))


def us_to_sec(us: int) -> Decimal:
    return Decimal(int(us)) / Decimal(US_PER_S)


# --------------------------------------------------------------------------- quantisation
PRECISION = {
    "s": "0.0001", "ms": "0.1", "kph": "0.01", "mps": "0.01", "celsius": "0.01",
    "bar": "0.01", "psi": "0.05", "hpa": "0.01", "percentage": "0.01", "pct": "0.01",
    "ratio": "0.000001", "rpm": "1", "deg": "0.01", "m": "0.0001", "cm": "0.01",
}


def quantize_value(val: Any, unit: str = "s") -> Any:
    """Banker's rounding to the declared unit precision (floats/Decimals only)."""
    if isinstance(val, bool) or isinstance(val, int):
        return val
    if isinstance(val, (float, Decimal)):
        d = Decimal(str(val)).quantize(Decimal(PRECISION.get(unit.lower(), "0.0001")), rounding=ROUND_HALF_EVEN)
        return float(d)
    return val


# --------------------------------------------------------------------------- RFC 8785 (JCS)
def es6_format_float(val: float) -> str:
    """ECMAScript Number::toString for finite doubles (RFC 8785 §3.2.2.3)."""
    if math.isnan(val) or math.isinf(val):
        raise ValueError("RFC 8785 forbids NaN/Infinity")
    if val == 0.0:
        return "0"
    sign = "-" if val < 0 else ""
    r = repr(abs(val))
    mant, exp = (r.split("e") + ["0"])[:2] if "e" in r else (r, "0")
    exp = int(exp)
    ip, fp = mant.split(".") if "." in mant else (mant, "")
    raw = ip + fp
    stripped = len(raw) - len(raw.lstrip("0"))
    n = len(ip) + exp - stripped
    digits = raw.lstrip("0").rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    es = ("+" if e >= 0 else "-") + str(abs(e))
    return sign + (digits if k == 1 else digits[0] + "." + digits[1:]) + "e" + es


def _jstr(s: str) -> str:
    out = ['"']
    for c in s:
        o = ord(c)
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif c == "\b":
            out.append("\\b")
        elif c == "\t":
            out.append("\\t")
        elif c == "\n":
            out.append("\\n")
        elif c == "\f":
            out.append("\\f")
        elif c == "\r":
            out.append("\\r")
        elif o < 0x20:
            out.append(f"\\u{o:04x}")
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def _jstr(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def jcs(data: Any) -> str:
    """Serialise to RFC 8785 canonical JSON text (fast ASCII/C-escaped path)."""
    if data is None:
        return "null"
    if isinstance(data, bool):
        return "true" if data else "false"
    if isinstance(data, int):
        if abs(data) > _MAX_SAFE_INT:
            raise ValueError("integer outside IEEE-754 safe range; encode as string")
        return str(data)
    if isinstance(data, float):
        return es6_format_float(data)
    if isinstance(data, str):
        return json.dumps(data, ensure_ascii=False)
    if isinstance(data, (list, tuple)):
        return "[" + ",".join(jcs(x) for x in data) + "]"
    if isinstance(data, dict):
        if all(type(k) is str and k.isascii() for k in data):
            keys = sorted(data.keys())
            return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + jcs(data[k]) for k in keys) + "}"
        keys = sorted(data.keys(), key=lambda k: str(k).encode("utf-16-be"))
        return "{" + ",".join(json.dumps(str(k), ensure_ascii=False) + ":" + jcs(data[k]) for k in keys) + "}"
    raise TypeError(f"unsupported type for canonicalisation: {type(data)}")


def sha256_hex(data: Any) -> str:
    return hashlib.sha256(jcs(data).encode("utf-8")).hexdigest()


def sha256_tagged(data: Any) -> str:
    """Return canonical algorithm-tagged SHA-256 digest compatible with UI hash badges."""
    return f"sha256:{sha256_hex(data)}"


def normalize_hash_hex(digest: str) -> str:
    """Strip optional algorithm tag ('sha256:') cleanly when comparing digests."""
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest[7:]
    return digest
