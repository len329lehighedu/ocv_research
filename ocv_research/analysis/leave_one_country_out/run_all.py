#!/usr/bin/env python3
"""Run the country-omission models and draw their coefficient plot.
Manuscript: Results 3.4; Table S10 and Figure S1."""

from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent


def main():
    """Read inputs, run this script and save its outputs."""
    for script in ("run_loco.py", "plot_loco.py"):
        print(f"\nRunning {script}", flush=True)
        subprocess.run([sys.executable, "-B", str(HERE / script)], check=True)
    print("\nCompleted: model and coefficient plots.")


if __name__ == "__main__":
    main()
