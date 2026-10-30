#!/usr/bin/env python3
"""diskusage — terminal visualisation of disk usage.

Part of the server-disk-cleanup skill. Stdlib only (no third-party deps).

Shows two things as colour-coded bar charts:
  1. Filesystem overview (df) with a use% bar per mount.
  2. Largest directories under a path (du), scaled so the biggest is full width.

Usage:
    diskusage                      # overview + top dirs under /
    diskusage /var                 # overview + top dirs under /var
    diskusage /var --depth 2 --top 15
    diskusage --no-color          # plain output (logs, cron, non-tty)
"""
import argparse
import os
import subprocess
import sys


class C:
    RED = "\033[31m"; YEL = "\033[33m"; GRN = "\033[32m"; BLU = "\033[34m"
    CYN = "\033[36m"; BOLD = "\033[1m"; DIM = "\033[2m"; RST = "\033[0m"


COLOR = sys.stdout.isatty()


def c(code, text):
    return f"{code}{text}{C.RST}" if COLOR else text


def bar(pct, width=28):
    """Return a text bar; pct is 0..100. Colour follows usage severity."""
    fill = max(0, min(width, round(pct * width / 100)))
    if COLOR:
        col = C.GRN if pct < 70 else (C.YEL if pct < 90 else C.RED)
        return f"{col}{'\u2588' * fill}{C.DIM}{'\u2591' * (width - fill)}{C.RST}"
    return "#" * fill + "." * (width - fill)


def human(nbytes):
    val = float(nbytes)
    for unit in ("B", "K", "M", "G", "T", "P"):
        if val < 1024 or unit == "P":
            if unit == "B":
                return f"{int(val)}{unit}"
            return f"{val:.1f}{unit}"
        val /= 1024
    return f"{val:.1f}P"


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout
    except Exception as e:
        print(f"error running {' '.join(cmd)}: {e}", file=sys.stderr)
        return ""


def filesystems():
    """df -P, one row per local filesystem with a use% bar."""
    out = run(["df", "-P"])
    rows = []
    for line in out.splitlines():
        if not line or line.startswith("Filesystem"):
            continue
        f = line.split()
        if len(f) < 6:
            continue
        fs, size, used, avail, pct, mount = f[0], f[1], f[2], f[3], f[4], f[5]
        p = int(pct.rstrip("%"))
        if size in ("0", "-") or not fs.startswith("/dev"):
            # skip pseudo filesystems and zero-size mounts to reduce noise
            if not (mount == "/" or fs.startswith("/dev")):
                continue
        rows.append((p, fs, size, used, avail, mount))
    rows.sort(reverse=True)
    return rows


def top_dirs(path, depth, top):
    """du -xk, scaled so the biggest directory is full width."""
    out = run(["du", "-xk", "--max-depth", str(depth), path])
    rows = []
    for line in out.splitlines():
        if not line or "\t" not in line:
            continue
        kb, p = line.split("\t", 1)
        try:
            kb = int(kb)
        except ValueError:
            continue
        rows.append((kb * 1024, p))
    rows.sort(reverse=True)
    rows = rows[:top]
    if not rows:
        return rows
    max_bytes = rows[0][0] or 1
    return [(b, p, b * 100 // max_bytes) for b, p in rows]


def main():
    ap = argparse.ArgumentParser(description="Terminal disk-usage visualisation")
    ap.add_argument("path", nargs="?", default="/", help="directory to break down (default /)")
    ap.add_argument("--depth", type=int, default=1, help="du depth (default 1)")
    ap.add_argument("--top", type=int, default=15, help="max directories shown (default 15)")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colour")
    args = ap.parse_args()
    global COLOR
    if args.no_color:
        COLOR = False

    print(c(C.BOLD + C.CYN, "DISK OVERVIEW (df)") + c(C.DIM, "  — used% per filesystem"))
    for p, fs, size, used, avail, mount in filesystems():
        size_b, used_b, avail_b = int(size) * 1024, int(used) * 1024, int(avail) * 1024
        print(f"  {c(C.BOLD, mount):<14} {bar(p):<30} {p:>3}%  "
              f"({human(used_b)} used of {human(size_b)}, {human(avail_b)} free)")

    print()
    print(c(C.BOLD + C.CYN, f"LARGEST DIRS UNDER {args.path}")
          + c(C.DIM, f"  — depth {args.depth}, top {args.top}"))
    rows = top_dirs(args.path, args.depth, args.top)
    if not rows:
        print(c(C.DIM, "  (nothing readable here — run with sudo if needed)"))
    for b, p, pct in rows:
        print(f"  {c(C.BOLD, human(b)):>9}  {bar(pct):<30}  {p}")
    print()
    print(c(C.DIM, "Tip: drill in with `diskusage /var/lib/docker` or --depth 2 for the heavy containers."))


if __name__ == "__main__":
    main()
