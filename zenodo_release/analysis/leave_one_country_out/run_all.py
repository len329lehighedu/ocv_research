#!/usr/bin/env python3
"""One-command local reproduction using this folder's prepared inputs."""

from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent


def main():
    for script in ("run_loco.py", "plot_loco.py"):
        print(f"\nRunning {script}", flush=True)
        subprocess.run([sys.executable, "-B", str(HERE / script)], check=True)
    print("\nCompleted: model and coefficient plots.")


if __name__ == "__main__":
    main()
