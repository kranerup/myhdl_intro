"""
Get Python module dependecies
"""

import sys
from os.path import abspath, dirname
from functools import cache

base = abspath(f"{dirname(__file__)}/../..")


@cache
def get():
    deps = []
    for k, v in sys.modules.items():
        try:
            f = v.__file__
            if f.endswith(".pyc"):
                f = f[0:-1]
            if ".egg/" in f:
                f = f[: f.find(".egg/") + 4]
            p = abspath(f)
            if p.startswith(base):
                deps.append(p)
        except:  # noqa
            pass
    return deps
