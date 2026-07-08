# ink3d-lift

Lift a **2D ink label into a true-3D ink label** — on a laptop, in about a second per segment.
No GPU, no model, no training.

## Why

Vesuvius Challenge wishlist [#192 / #193](https://github.com/ScrollPrize/villa/issues):
- Ink label generation is currently **"entirely manual."**
- Existing 3D labels tend to be *"a single image projected across multiple layers"* — the ink is
  smeared through the depth instead of sitting where it actually is.

This tool automates that step and fixes the depth: it takes a segment's `tifxyz` (the flattened→3D
map that already exists for any segment) and **any** 2D ink label on that surface — a human label or a
model prediction — and places the ink at its **real 3D depth**, ink-only.

> Note: this **lifts an existing 2D label** to 3D; it does not create labels for *unsegmented*
> regions (the harder catch-22 in #193). It automates the currently-manual 2D→3D ink step.

## How it works

For each flattened grid point `(u,v)`:
- surface **normal** `N = normalize( dP/dcol × dP/drow )` from the coordinate grid,
- place the ink in a thin **depth band**: `point = P(u,v) + t·N`, weight `= ink(u,v) · gaussian(t)`,
- keep only ink-positive points → **ink-only** labels (blank papyrus ≈ 0, not labelled).

Options:
- `--ink consensus` averages all released model renders (e.g. july + november) for robustness.
- `--qa` skips segments whose geometry is torn (a sheet-jump) so labels aren't built on garbage — it
  reuses the coherent-seam check from [`../scroll_segment_qa`](../scroll_segment_qa).

## Usage

```bash
pip install numpy fsspec s3fs pillow zarr
python ink3d_lift.py --scroll PHerc0172 --segment <segment_name> --ink consensus --qa --out out/
```

Outputs, per segment:
- `<seg>_<model>_ink3d.npz` — labelled point cloud (`xyz` + `ink` probability)
- `<seg>_<model>_ink3d.zarr` — a dense **true-3D ink label volume** (max ink per voxel) over the
  segment bbox, with `origin_voxel` / `voxel_size` attrs for placement back into the scan frame.

## Validation

Run `validate.py` to check any segment against the scan volume. On PHerc0172 (Scroll 5) segment
`…-w067…`, sampling **all 488,151 surface points** against the level-4 scan:

| metric | our labels | baseline | ratio |
|---|---|---|---|
| inside scroll | 92.3% | 66.2% | 1.4× |
| on bright papyrus | 51.3% | 28.5% | **1.8×** |
| mean CT value | 140 | 98 (background) | 1.43× |

So the labels land on real papyrus far more than chance — the 3D placement is correct. Lift itself is
**~1 s (CPU)**; the ink sits on the 3D wrap in a thin depth band, not smeared across layers (`docs/`).

**Across 7 Scroll 5 segments** the on-papyrus ratio is consistently above chance — **mean 1.43×**, range
1.16–1.8× (w062 1.65, w067 1.80, w078 1.60, w079 1.16, w080 1.34, w082 1.33, w083 1.46). Segments with a low
ratio (e.g. w079, which also has only 57% of points inside the scroll) tend to have less accurate released
geometry — so `validate.py`'s ratio doubles as a cheap per-segment geometry sanity check.

**Honest limits:** placement is *correct but coarse* — the released `tifxyz` is downsampled ~20×, so
labels are accurate to a handful of voxels, not sub-voxel. Output quality is also bounded by the input
2D label: lifting a crisp human label gives a crisp 3D label; lifting a soft model prediction gives a
soft one. This tool automates the *lift*; it does not improve the source label.

## License / data

Reads public anonymous S3 (`vesuvius-challenge-open-data`). Follows the Vesuvius Challenge data
agreement; cite EduceLab-Scrolls. Does not reveal or redistribute hidden/decoded text.
