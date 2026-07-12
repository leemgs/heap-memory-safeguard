\
"""
User-space bridge to /dev/hmp_ctl: get stats (JSON) and set params.
"""
from __future__ import annotations
import os, json, time, argparse, sys

DEV = "/dev/hmp_ctl"

def set_param(name: str, value: int, dev: str = DEV):
    line = f"{name}={value}\n".encode("ascii")
    with open(dev, "wb", buffering=0) as f:
        n = f.write(line)
        if n != len(line):
            raise IOError("short write")

def get_snapshot(dev: str = DEV) -> dict:
    with open(dev, "rb", buffering=0) as f:
        data = f.read()
    # Expect a single JSON line
    return json.loads(data.decode("utf-8"))

def main():
    ap = argparse.ArgumentParser(description="HMS user-space bridge to /dev/hmp_ctl")
    ap.add_argument("--dev", default=DEV, help="device path (default: /dev/hmp_ctl)")
    ap.add_argument("--set", nargs=2, action="append", metavar=("KEY","VAL"),
                    help="Set a parameter (alpha_milli|theta1_milli|theta2_milli|rss_limit_mb)")
    ap.add_argument("--watch", action="store_true", help="Continuously print snapshots")
    ap.add_argument("--interval", type=float, default=0.5, help="Watch interval seconds")
    args = ap.parse_args()

    if args.set:
        for k, v in args.set:
            set_param(k, int(v), dev=args.dev)

    if args.watch:
        try:
            while True:
                snap = get_snapshot(dev=args.dev)
                print(json.dumps(snap, separators=(',',':')))
                sys.stdout.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return
    else:
        snap = get_snapshot(dev=args.dev)
        print(json.dumps(snap, indent=2))

if __name__ == "__main__":
    main()
