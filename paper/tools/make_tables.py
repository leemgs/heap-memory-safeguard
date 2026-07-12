#!/usr/bin/env python3
r"""make_tables.py — turn a results CSV into a complete LaTeX `tabular` for the paper.

Reads a CSV whose first column is the row label and whose remaining columns are
metric values (numbers, or blank if not yet measured). Emits a COMPLETE
booktabs `tabular` (colspec, header, rules, rows) that you \\input inside your
existing `table` float, keeping your own \\caption and \\label. Blank cells
render as \\tbd (the red placeholder). Optionally bold the best value per column.

The CSV's header row supplies the column headers; its first cell is the label
column header (e.g., "System"). Header cells may contain LaTeX, including
\\makecell{...} for multi-line headers.

Usage:
  python3 make_tables.py results/isolate.csv --out results/tab_isolate.tex \
      --bold-min "Peak RSS (MB),L_r (ms),T_gc (ms),Major flt. (/min),p99 frame (ms),Reclaimed (K pages)"
  python3 make_tables.py results/altsignals.csv --out results/tab_altsignals.tex \
      --bold-min "L_r (ms),T_gc (ms),Reclaim vol. (MB),Mispred. rate (%)" --bold-max "S_h (0-1)"

Then in 065_evaluation.tex replace the skeleton `\begin{tabular}...\end{tabular}`
with:  \input{results/tab_isolate.tex}
"""
import argparse, csv, sys

def fmt(v):
    v = (v or "").strip()
    return r"\tbd" if v == "" else v

def to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default=None, help="output .tex (default: stdout)")
    ap.add_argument("--colspec", default=None, help="e.g. lcccccc (default: l + c*(n-1))")
    ap.add_argument("--bold-min", default="", help="data-column indices (1-based) or header texts to bold the min of, comma-separated")
    ap.add_argument("--bold-max", default="", help="data-column indices (1-based) or header texts to bold the max of, comma-separated")
    ap.add_argument("--no-header", action="store_true", help="omit the header row")
    a = ap.parse_args()

    with open(a.csv, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [r for r in reader if any(c.strip() for c in r)]

    ncol = len(header)
    colspec = a.colspec or ("l" + "c" * (ncol - 1))
    data_cols = header[1:]

    def parse_cols(spec):
        """Return a set of 1-based data-column indices from a spec of indices or header names."""
        out = set()
        for tok in spec.split(","):
            tok = tok.strip()
            if not tok:
                continue
            if tok.isdigit():
                out.add(int(tok))
            elif tok in data_cols:
                out.add(data_cols.index(tok) + 1)
        return out

    bmin = parse_cols(a.bold_min)
    bmax = parse_cols(a.bold_max)

    best = {}
    for j in range(1, ncol):
        nums = [to_float(r[j]) for r in rows if j < len(r)]
        nums = [x for x in nums if x is not None]
        if not nums:
            continue
        if j in bmin:
            best[j] = min(nums)
        elif j in bmax:
            best[j] = max(nums)

    out = [r"\begin{tabular}{%s}" % colspec, r"\toprule"]
    if not a.no_header:
        out.append(" & ".join(h.strip() for h in header) + r" \\")
        out.append(r"\midrule")
    for r in rows:
        cells = [r[0].strip()]
        for j in range(1, ncol):
            raw = r[j] if j < len(r) else ""
            val = fmt(raw)
            fv = to_float(raw)
            if j in best and fv is not None and abs(fv - best[j]) < 1e-9:
                val = r"\textbf{%s}" % raw.strip()
            cells.append(val)
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]

    body = "\n".join(out) + "\n"
    if a.out:
        with open(a.out, "w") as f:
            f.write(body)
        print(f"wrote {a.out} ({len(rows)} rows, colspec={colspec})", file=sys.stderr)
    sys.stdout.write(body)

if __name__ == "__main__":
    main()
