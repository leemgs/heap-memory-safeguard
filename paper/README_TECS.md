# HMS — ACM TECS (acmart) submission package

This is the manuscript converted from the original IEEE `IEEEtran` sources to the
**ACM `acmart` class in Small Standard Format (`acmsmall`)**, which is the format
ACM Transactions on Embedded Computing Systems (TECS) requires.

## How to build

The document builds with **pdfLaTeX** (no Korean/`kotex` needed anymore):

```
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

On Overleaf, set the compiler to **pdfLaTeX** and the main document to `main.tex`.
It also builds unchanged on the ACM Overleaf "acmart" template.

## What was changed from the IEEE version

- **Document class**: `\documentclass[acmsmall,review]{acmart}` with `\acmJournal{TECS}`.
  The `review` option turns on line numbers for reviewers; remove it for the camera-ready.
- **Front matter** rewritten to ACM conventions: `\title`, `\author`+`\affiliation`+
  `\orcid`+`\email`, `\begin{abstract}`, a **CCS Concepts** block, and `\keywords`
  (all placed before `\maketitle`, as `acmart` requires).
- **Bibliography** switched to `\bibliographystyle{ACM-Reference-Format}` (ships with
  `acmart`); all 21 citations resolve.
- **Removed IEEE-only constructs**: `\IEEEPARstart`, `\IEEEkeywords`, `\markboth`,
  `\thanks`, the ORCID/TikZ hack (replaced by native `\orcid`), and the
  `IEEEbiography` block (ACM journal articles do not carry author photos/bios).
- **Figures**: the parameter-sensitivity sub-figures were converted from `subfig`
  (`\subfloat`) to `subcaption` (`\begin{subfigure}`), which is the package `acmart`
  supports.
- **Dropped unused packages** (`siunitx`, `tabu`, `listings`, `algorithm2e`, `titlesec`,
  `datetime`, `cite`, `hyperref`, `caption`) — `acmart` already provides what is needed;
  only `pifont`, `makecell`, and `subcaption` are loaded on top.

## Before you submit — action items

1. **Corresponding author / affiliation.** The template lists **Sungkyunkwan University**
   with the **leemgs@g.skku.edu** address as the corresponding author. Keep it this way:
   this is what makes the article eligible for **APC-free** publication under SKKU's
   ACM Open participation. (If you also want Samsung shown, add it as a *secondary*
   affiliation only — the SKKU affiliation + institutional email must remain primary.)
2. **CCS concepts.** The included concepts are reasonable defaults. Regenerate the exact
   XML with the official ACM CCS tool (https://dl.acm.org/ccs) and paste it over the
   `CCSXML` block for the camera-ready.
3. **Red `[AUTHOR ACTION]` notes.** Five items in `065_evaluation.tex` still require real
   measurements (static-aggressive baseline, four-signal ablation, misprediction rate,
   post-reclaim faults during GC, low-pressure workload W5). These are the substantive
   experiments the previous reviewers asked for. Fill in the numbers/tables and delete
   the notes before submitting. To hide all notes at once, redefine in `main.tex`:
   `\renewcommand{\authoraction}[1]{}`.
4. **One incomplete reference.** BibTeX warns that entry `TC_10045641` has no volume/number.
   Add those fields in `reference-data.bib` for a clean camera-ready.

## Notes on length

In `acmsmall` (single-column) the paper renders at ~20 pages including the red notes and
the review-mode line spacing. TECS has **no page limit and no page charges**, so length is
not a problem; the count will change once the notes are replaced by result tables.
