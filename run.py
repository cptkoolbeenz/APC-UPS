#!/usr/bin/env python3
"""APC UPS Manager — Entry point."""

import sys
import os

# Ensure the package is importable when running from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apc_ups.ui.app import main

if __name__ == "__main__":
    main()
