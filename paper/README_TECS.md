# HMS ACM TECS manuscript

This directory contains the ACM `acmsmall` manuscript. The paper is explicitly a
design and deterministic-simulation study. It does not claim an Android deployment
or commercial-device measurements.

## Build

Install a TeX distribution containing `acmart.cls`, BibTeX, and the packages used
by `main.tex`, then run:

```bash
latexmk -pdf main.tex
```

An old PDF is not proof of a clean build.

## Submission boundary

- Author: Geunsik Lim, Sungkyunkwan University, `leemgs@g.skku.edu`
- All result figures are synthetic simulation outputs.
- No AOSP, ART, kernel, SELinux, or device patch is included.
- No raw Perfetto trace or repeated physical-device dataset is included.
- `MEASUREMENT_GUIDE.md` is a future validation protocol, not completed evidence.

Do not restore claims of measured latency, energy, compatibility, production
overhead, or statistical significance without committing the raw evidence and
generation pipeline.
