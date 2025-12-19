# core/engine/sort.py
import re
from typing import Any, Tuple, Union

_SPLIT_RE = re.compile(r"(\d+)")

def natural_sort_key(value: Any) -> Tuple[Union[int, str], ...]:
    s = "" if value is None else str(value)
    parts = _SPLIT_RE.split(s)
    key = []
    for p in parts:
        if p.isdigit():
            key.append(int(p))
        else:
            key.append(p.lower())
    return tuple(key)   # ✅ IMPORTANTE: tuple, no list
