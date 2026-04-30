#!/usr/bin/env python3
"""
Quick Launcher for Telegram Bot UI

Run this to immediately launch the GUI application.
"""

import subprocess
import sys

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TELEGRAM BOT - UI LAUNCHER")
    print("=" * 60 + "\n")
    
    # Run main.py
    result = subprocess.run([sys.executable, "main.py"], cwd=".")
    
    sys.exit(result.returncode)
