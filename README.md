# Vesuvius Scroll Tools

Two small, **CPU-only** tools for the [Vesuvius Challenge](https://scrollprize.org) — no GPU, no scan-volume
downloads, laptop-friendly. Each reads the public anonymous S3 data (`vesuvius-challenge-open-data`).

## `ink3d_lift/` — automated 2D→true-3D ink label lifting
Ink labels are currently made by hand, and 3D labels are often one 2D image copied across depth layers.
`ink3d_lift` automates the geometric step in seconds per segment on CPU: it places **any** 2D ink label at its real 3D depth
by extruding a thin band along the surface normal from the segment's `tifxyz`, weighted by ink probability
(ink-only). Output: labelled point cloud + sparse `zarr` label volume.

**Validated** (`validate.py`, all 488k surface points of Scroll 5 seg w067 vs the scan): labels land on bright
papyrus **51% vs 28% baseline (1.8×)**, 92% inside-scroll, mean CT 140 vs 98 — the placement is correct.
Targets wishlist #192 / #193.

## `scroll_segment_qa/` — geometry QA for sheet-jumps
Flags broken segmentations (torn / sheet-jumped) from the `tifxyz` mesh alone. Scored all 53 Scroll 5 segments
in ~3 min: 52 clean (~1×), 1 `auto_grown` torn (455× seam). A cheap quality gate for autosegmentation output.

## Install & run
```bash
pip install -r requirements.txt
python ink3d_lift/ink3d_lift.py --scroll PHerc0172 --segment <seg> --ink consensus --qa --out out/
python ink3d_lift/validate.py   --scroll PHerc0172 --segment <seg>
python scroll_segment_qa/scroll_segment_qa.py --scroll PHerc0172 --viz --out qa/
```

Each tool folder has a `SUBMISSION.md` with progress-prize form text. Data: follows the VC data agreement;
cites EduceLab-Scrolls; reveals no hidden/decoded text.
