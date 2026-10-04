#!/usr/bin/env python3
"""Keep desktop setup compatibility while supporting normal Python builds."""

import sys


if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1:] == ["--no-autostart"]:
        from gwolves.install import main

        raise SystemExit(main(sys.argv[1:]))
    else:
        from setuptools import setup

        setup()
