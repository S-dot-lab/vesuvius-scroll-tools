#!/usr/bin/env python3
"""
scroll_segment_qa.py — cheap geometry QA for Vesuvius Challenge scroll segments.

Flags broken segmentations (sheet-jumps / tears) directly from the small `tifxyz` mesh
files — no GPU, no scan-volume download (~3.6 MB per segment, ~seconds each).

WHY: autosegmentation produces a flood of candidate segments. Some are clean; some
"sheet-jump" — the traced surface accidentally hops to an adjacent wrap and stitches two
non-contiguous pieces together, which scrambles the flattened text. Reading (ink
detection) those is wasted compute. This tool scores every segment's geometry so you can
gate the flood *before* inference and prioritize the clean ones.

HOW: a segment's `tifxyz` stores, per flattened grid point (u,v), its 3D coordinate
(x,y,z) in the scroll volume. In a correct flattening, grid neighbors are 3D-adjacent with
a near-constant step (the local sampling pitch). A sheet-jump tears a whole row or column:
that line's *median* 3D neighbor-step spikes far above the baseline. We report, per
segment, the largest coherent-seam ratio (median line step / baseline). ~1.0 = clean;
>=4 = a real tear, with its row/col location.

Edge pixels are excluded (a margin) because border extrapolation produces huge false
spikes. The *median* per line (not max) makes the score robust to isolated outlier pixels
and sensitive only to coherent, full-line tears.

LIMITATION: catches hard geometric tears. Subtle "soft" wrap-drift that does not tear the
mesh may still read as clean here; pair with an ink-map column-continuity check for those.

USAGE:
    python scroll_segment_qa.py --scroll PHerc0172
    python scroll_segment_qa.py --scroll PHerc0172 --limit 10 --out report/ --viz
Outputs: <out>/<scroll>_segment_qa.csv (ranked) + optional seam PNGs for flagged segments.
"""
import argparse, io, os, csv
import numpy as np
import fsspec
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

BROKEN_THRESHOLD = 4.0   # coherent-seam ratio at/above which a segment is flagged as torn


def load_tif(buf):
    """Load a (possibly LZW-compressed) coordinate TIFF as float32. PIL handles LZW natively."""
    try:
        return np.array(Image.open(io.BytesIO(buf))).astype(np.float32)
    except Exception:
        import tifffile
        return tifffile.imread(io.BytesIO(buf)).astype(np.float32)


def seam_score(P, mask, margin=25, min_valid=500):
    """Return the largest coherent-seam ratio for a segment and where it is.

    P: (H,W,3) float grid of 3D coords. mask: (H,W) bool of valid (non-zero) points.
    """
    H, W, _ = P.shape
    interior = np.zeros((H, W), bool)
    interior[margin:H - margin, margin:W - margin] = True
    du = np.linalg.norm(P[:, 1:] - P[:, :-1], axis=2)      # step to right neighbor
    dv = np.linalg.norm(P[1:] - P[:-1], axis=2)            # step to lower neighbor
    mu = mask[:, 1:] & mask[:, :-1] & interior[:, 1:] & interior[:, :-1]
    mv = mask[1:] & mask[:-1] & interior[1:] & interior[:-1]
    if mu.sum() < min_valid:
        return None
    base = float(np.median(du[mu]))
    if base <= 0:
        return None
    col = np.array([np.median(du[mu[:, u], u]) if mu[:, u].sum() > 20 else 0.0
                    for u in range(du.shape[1])]) / base
    row = np.array([np.median(dv[v, mv[v]]) if mv[v].sum() > 20 else 0.0
                    for v in range(dv.shape[0])]) / base
    cu, rv = int(np.argmax(col)), int(np.argmax(row))
    if col[cu] >= row[rv]:
        return dict(score=float(col[cu]), axis="col", index=cu, baseline=base, grid=(H, W))
    return dict(score=float(row[rv]), axis="row", index=rv, baseline=base, grid=(H, W))


def save_seam_png(P, mask, res, path):
    """Save a heatmap of 3D neighbor-step (bright = tear) with the detected seam marked red."""
    H, W, _ = P.shape
    du = np.linalg.norm(P[:, 1:] - P[:, :-1], axis=2)
    step = np.clip(du / (res["baseline"] * 8), 0, 1)
    img = (step * 255).astype(np.uint8)
    rgb = np.stack([img, img, img], -1)
    i = res["index"]
    if res["axis"] == "col":
        rgb[:, max(0, i - 1):i + 2] = (255, 60, 60)
    else:
        rgb[max(0, i - 1):i + 2, :] = (255, 60, 60)
    sy, sx = max(1, H // 700), max(1, W // 1600)
    Image.fromarray(rgb[::sy, ::sx]).save(path)


def find_tifxyz(fs, seg_path):
    for d in fs.ls(seg_path + "/mesh"):
        if "tifxyz" in d.split("/")[-1]:
            return d
    return None


def analyze_scroll(scroll, out, limit=None, viz=False,
                   bucket="vesuvius-challenge-open-data"):
    fs = fsspec.filesystem("s3", anon=True)
    base = f"{bucket}/{scroll}/segments"
    segs = [p.split("/")[-1] for p in fs.ls(base)]
    if limit:
        segs = segs[:limit]
    os.makedirs(out, exist_ok=True)
    rows = []
    for i, s in enumerate(segs):
        txd = None
        try:
            txd = find_tifxyz(fs, f"{base}/{s}")
        except Exception:
            pass
        if txd is None:
            continue
        try:
            X, Y, Z = (load_tif(fs.cat(f"{txd}/{c}.tif")) for c in ("x", "y", "z"))
        except Exception:
            continue
        P = np.stack([X, Y, Z], -1)
        mask = ~((X == 0) & (Y == 0) & (Z == 0))
        res = seam_score(P, mask)
        if res is None:
            continue
        res["segment"] = s
        res["verdict"] = "BROKEN" if res["score"] >= BROKEN_THRESHOLD else "clean"
        rows.append(res)
        print(f"[{i + 1}/{len(segs)}] {s[:34]:34s} {res['score']:8.1f}x  "
              f"{res['axis']}@{res['index']:<5d} {res['verdict']}")
        if viz and res["score"] >= BROKEN_THRESHOLD:
            save_seam_png(P, mask, res, os.path.join(out, f"{s[:30]}_seam.png"))
    rows.sort(key=lambda r: -r["score"])
    csv_path = os.path.join(out, f"{scroll}_segment_qa.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["segment", "seam_score", "verdict", "seam_axis", "seam_index",
                    "grid_h", "grid_w", "baseline_step"])
        for r in rows:
            w.writerow([r["segment"], f"{r['score']:.2f}", r["verdict"], r["axis"],
                        r["index"], r["grid"][0], r["grid"][1], f"{r['baseline']:.2f}"])
    broken = [r for r in rows if r["verdict"] == "BROKEN"]
    print(f"\nScanned {len(rows)} segments -> {len(broken)} BROKEN (>= {BROKEN_THRESHOLD}x), "
          f"{len(rows) - len(broken)} clean.  Report: {csv_path}")
    for r in broken[:10]:
        print(f"  BROKEN {r['score']:8.1f}x  {r['axis']}@{r['index']}  {r['segment']}")
    return rows


def main():
    ap = argparse.ArgumentParser(description="Geometry QA for Vesuvius scroll segments (tifxyz).")
    ap.add_argument("--scroll", default="PHerc0172", help="scroll id, e.g. PHerc0172")
    ap.add_argument("--out", default="segment_qa_out", help="output directory")
    ap.add_argument("--limit", type=int, default=None, help="only scan first N segments")
    ap.add_argument("--viz", action="store_true", help="save seam PNGs for flagged segments")
    ap.add_argument("--bucket", default="vesuvius-challenge-open-data")
    a = ap.parse_args()
    analyze_scroll(a.scroll, a.out, a.limit, a.viz, a.bucket)


if __name__ == "__main__":
    main()
