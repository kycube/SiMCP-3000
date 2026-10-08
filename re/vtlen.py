"""STATIC: vtable lengths, bounded by the next vtable that a constructor stores (or a non-code entry).

    python re/vtlen.py SIMCITY.DLL 0x10013260 [0x...]
"""
import bisect
import sys
from functools import lru_cache

from pe import Image


@lru_cache(None)
def _starts(name):
    im = Image(name)
    return im, sorted(im.vtable_starts())


def vtable_len(name, va):
    im, starts = _starts(name)
    n = len(im.vtable(va))
    i = bisect.bisect_right(starts, va)
    if i < len(starts):
        n = min(n, (starts[i] - va) // 4)
    return n


if __name__ == "__main__":
    for a in sys.argv[2:]:
        print(a, vtable_len(sys.argv[1], int(a, 16)))
