#!/usr/bin/env python
"""
Run script for Blocket Bot v2.
Use: python run.py
Or: streamlit run v2/ui/app.py
"""
import sys
import subprocess


def main():
    """Run the Streamlit app."""
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "v2/ui/app.py",
        "--server.port=8502",
        "--browser.gatherUsageStats=false",
    ])


if __name__ == "__main__":
    main()
