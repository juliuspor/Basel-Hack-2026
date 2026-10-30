"""Export the low-poly bike that the app places on occupied slots.

Usage:
  blender -b --factory-startup -P generate_bike.py -- OUT_DIR
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenegen as sg  # noqa: E402


def main():
    out_dir = os.path.abspath(sg.script_args()[0])
    os.makedirs(out_dir, exist_ok=True)
    sg.reset_scene()
    sg.build_bike()
    sg.export_usdz(os.path.join(out_dir, "bike.usdz"))
    print(f"wrote {out_dir}/bike.usdz")


if __name__ == "__main__":
    main()
