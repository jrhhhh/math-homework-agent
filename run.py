#!/usr/bin/env python3
"""Run from any working directory; use only Python's standard library."""
import os
from pathlib import Path
from app.server import main

if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parent)
    main()
