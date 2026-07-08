# Ideas: toward a label-free "Scroll Segment Quality Suite"

The polished tool (`scroll_segment_qa.py`) does **geometry** QA. The strongest *submission*
is a cohesive, label-free suite that triages the autosegmentation flood on a laptop. Ranked
by honest odds of a monthly open-source prize, with build sketches.

## 1. No-reference legibility score for ink-detection outputs  (RECOMMENDED, ~4–8%)
For **unread** scrolls there is no ground truth, so people rank ink maps by eye. A single
automatic 0–1 "how much real, legible text is here" score would let anyone auto-rank
segments and compare model versions without labels.
- **Build:** on a 2D ink map compute (a) horizontal line periodicity (autocorr/FFT of the
  row-ink profile — text has rhythmic lines), (b) stroke-scale connected-component fraction
  (letters are ~8–200 px blobs, not noise speckle or big smudges), (c) column periodicity.
  Combine into one score.
- **Why it can win:** broadly useful, and **validatable** — on a *solved* scroll we know
  which regions are legible, so we can show the score correlates with real readability
  (AUC vs. known text). Judges can see it works. It's "no-reference image quality
  assessment," a recognized idea, applied to scrolls.

## 2. Ink-map column-continuity detector (complements geometry QA, ~4–7%)
Geometry QA catches *hard* tears; the scholars' actual complaint is *disconnected columns*.
Detect where text columns break/shift in an ink map (track line continuity across width;
a sheet-jump breaks many lines at one x). Cross-reference with geometry seams → a segment
flagged clean by geometry but broken by ink = a soft wrap-drift.
- **Build:** row-ink profile → detect text lines → per-line continuity; or band-wise
  column-profile cross-correlation vs. lateral shift (prototype in `sheetjump_detect.py`).

## 3. Segment auto-splitter / repair (~4–7%)
Turn detection into repair: cut a torn segment at its seam into clean sub-segments and
write new `tifxyz` ready for ink detection. Actionable, on the segmentation frontier.
- **Build:** run seam detection → cut the grid at the seam → re-score each piece → export.

## 4. Multi-model consensus + uncertainty ink map (~3–6%)
Segments ship multiple ink-model renders (e.g. july/november). Merge into a consensus map
(often cleaner) plus a disagreement/uncertainty map (flags unreliable regions).
- **Build:** align + combine the 2 renders; show consensus reads better than either alone.

## Recommended path
Build **#1** (validated on a solved scroll), then package it *with* the geometry QA tool as
one "Scroll Segment Quality Suite": **cheap, label-free triage of segments by geometry AND
ink legibility.** Cohesive + validated + broadly useful = the best odds for a small prize.
