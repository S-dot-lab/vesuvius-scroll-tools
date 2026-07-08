# scroll-segment-qa

Cheap geometry QA for Vesuvius Challenge scroll segments. Flags **sheet-jumps / tears** in
segmentations directly from the small `tifxyz` mesh files — **no GPU, no scan-volume
download** (~3.6 MB and a few seconds per segment).

## The problem it solves

Autosegmentation produces a flood of candidate segments. Some are clean; some *sheet-jump* —
the traced surface accidentally hops to an adjacent wrap and stitches two non-contiguous
pieces together, scrambling the flattened text ("disconnected columns"). Running ink
detection on those is wasted compute, and they pollute downstream results. This tool scores
every segment's geometry so you can **gate the flood before inference** and prioritize the
clean ones.

## How it works

A segment's `tifxyz` stores, for each flattened grid point `(u,v)`, its 3D coordinate
`(x,y,z)` in the scroll volume. In a correct flattening, grid neighbors are 3D-adjacent with
a near-constant step (the local sampling pitch). A sheet-jump tears a whole row or column, so
that line's **median** 3D neighbor-step spikes far above the baseline.

Per segment we report the largest **coherent-seam ratio** = `median(line step) / baseline`:

- `~1.0` → clean flattening
- `>= 4`  → a real tear, with its row/column location

Design choices that keep it honest:
- **Median per line, not max** → robust to isolated outlier pixels; fires only on coherent,
  full-line tears.
- **Interior-only** (edge margin excluded) → border extrapolation otherwise produces ~700×
  false spikes.

## Usage

```bash
pip install numpy fsspec s3fs pillow
python scroll_segment_qa.py --scroll PHerc0172            # scan a whole scroll
python scroll_segment_qa.py --scroll PHerc0172 --limit 10 --viz --out report/
```

Outputs `report/<scroll>_segment_qa.csv` ranked worst-first, plus (with `--viz`) a
step-heatmap PNG per flagged segment with the seam marked.

## Example result (PHerc0172 / Scroll 5, 53 segments)

52 segments scored ~1.0–1.2× (clean). One `auto_grown` segment scored **455×** with a
full-height seam at column 1605 — a 71.5 mm 3D jump (larger than the scroll's diameter),
i.e. two non-contiguous surface pieces stitched together. The hand-curated wraps were clean;
the tear was in auto-segmentation output — exactly where this gate is useful.

## Limitations & next step

Catches **hard geometric tears**. A subtle "soft" wrap-drift that does not tear the mesh can
still read as clean here. Pairing this with an ink-map column-continuity check (does a text
column break where geometry looks fine?) would catch those too — see `IDEAS.md`.

## License / data

Reads public anonymous S3 (`vesuvius-challenge-open-data`). Follows the Vesuvius Challenge
data agreement; cite EduceLab-Scrolls. Does not reveal or redistribute hidden/decoded text.
