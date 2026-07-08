# Progress Prize submission — ink3d-lift

Ready-to-paste content for the Vesuvius Challenge progress-prize form
(https://forms.gle/Sy6mW5cfJS2U7E9F7). **You** submit under your own name/email.
Deadline: end of month, 11:59pm Pacific (monthly cycle — submit early, it's weighted).

---

**Title:** ink3d-lift — automated 2D→true-3D ink label lifting (CPU, no training)

**Summary:**
Ink label generation for the scrolls is currently done entirely by hand, and 3D ink labels are often a
single 2D image copied across depth layers. `ink3d-lift` automates the geometric step on a laptop
(~1 s/segment, no GPU): given a segment's `tifxyz` and **any** 2D ink label on that surface (a human
label or a model prediction), it places the ink at its real 3D depth by extruding a thin band along the
surface **normal** (`N = normalize(dP/dcol × dP/drow)`), weighted by ink probability so only detectable
ink is labelled (blank papyrus ≈ 0). Output is a labelled point cloud plus a sparse **zarr** label
volume; an optional `--qa` flag skips segments with torn geometry, and `--ink consensus` averages
multiple model renders.

**Validation (PHerc0172 / Scroll 5, segment `…-w067…`, all 488,151 surface points vs the level-4 scan;
reproduce with `validate.py`):**
- inside scroll: **92.3%** vs 66.2% baseline
- on bright papyrus: **51.3%** vs 28.5% baseline (**1.8×**)
- mean CT value at labels: **140** vs 98 background (1.43×)

i.e. the lifted labels land on real papyrus far more than chance — the placement is geometrically correct.

**Honest scope/limits:** this *lifts an existing 2D label* to true 3D (it does not create labels for
unsegmented regions, nor improve the source label). Placement is correct but coarse — the released
`tifxyz` is downsampled ~20×, so labels are accurate to a few voxels. Output fidelity tracks input label
quality (crisp human label → crisp 3D label).

**Relation to wishlist:** directly targets #192 (accurate, ink-only, true-3D labels — not "a single image
across layers") and #193 (label-generation methods beyond simple voxelization).

**Code + docs:** <PUBLIC REPO URL — push tools/ink3d_lift to a public GitHub repo and paste the link>

**How to run:**
```
pip install numpy fsspec s3fs pillow zarr
python ink3d_lift.py --scroll PHerc0172 --segment <segment> --ink consensus --qa --out out/
python validate.py   --scroll PHerc0172 --segment <segment>
```

**License/data:** reads public anonymous S3 (`vesuvius-challenge-open-data`); follows the VC data
agreement; cites EduceLab-Scrolls; reveals no hidden/decoded text.

---
### Before you submit
1. Push `tools/ink3d_lift/` (and optionally `tools/scroll_segment_qa/`, which `--qa` uses) to a **public
   GitHub repo** under your account; paste the URL above.
2. Skim the README + this text — every number here is reproducible via `validate.py`; make sure you're
   comfortable standing behind it.
3. Submit early. You can submit *both* tools (multiple submissions/month are allowed).
