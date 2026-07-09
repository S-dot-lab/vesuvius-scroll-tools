# Progress Prize submission — scroll-segment-qa

Ready-to-paste content for the Vesuvius Challenge progress-prize form
(https://forms.gle/Sy6mW5cfJS2U7E9F7). **You** submit this under your own name/email.
Submit through the current official progress-prize form/page; submit early because monthly review favors early, usable releases.

---

**Title:** scroll-segment-qa — cheap geometry QA to flag sheet-jumps in segments (no GPU)

**Summary:**
A small, laptop-only tool that flags broken segmentations (sheet-jumps / tears) directly from the
`tifxyz` mesh files — no GPU, no scan-volume download (~3.6 MB and a few seconds per segment). It
scores each segment's flattening geometry: grid neighbours should be 3D-adjacent with a near-constant
step; a sheet-jump tears a whole row/column, spiking that line's median 3D step. Output is a ranked
CSV (worst-first) plus seam-heatmap PNGs, so the flood of autosegmentation candidates can be triaged
*before* spending inference on torn segments.

**Result (PHerc0172 / Scroll 5, all 53 segments, ~3 min on a laptop):**
52 segments scored ~1.0–1.2× (clean); one `auto_grown` segment scored **455×** with a full-height
seam at column 1605 — a 71.5 mm 3D jump (larger than the scroll's diameter), i.e. two non-contiguous
surface pieces stitched together. The hand-curated wraps were clean; the tear was in autosegmentation
output — exactly where a cheap QA gate helps.

**Relation to wishlist:** complements autosegmentation work (#191/#201/#203) by providing a
compute-light quality gate. It catches *hard* geometric tears; subtle soft wrap-drift that doesn't
tear the mesh is out of scope (would need an ink-column-continuity check — noted in IDEAS.md).

**Code + docs:** https://github.com/S-dot-lab/vesuvius-scroll-tools (tool in `scroll_segment_qa/`)

**How to run:**
```
pip install numpy fsspec s3fs pillow
python scroll_segment_qa.py --scroll PHerc0172 --viz --out report/
```

**License/data:** reads public anonymous S3 (`vesuvius-challenge-open-data`); follows the VC data
agreement; cites EduceLab-Scrolls; reveals no hidden/decoded text.

---
### Before you submit
1. Repo is already public at the URL above — nothing to push.
2. Skim the README + this text — make sure you're comfortable with every claim.
3. Fill the form early. Multiple submissions/month are allowed, so this can go in now.
