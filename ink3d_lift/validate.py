#!/usr/bin/env python3
"""
validate.py — check that lifted labels land on real papyrus.

Samples ALL of a segment's surface points against a coarse (level-4) view of the scan volume and reports how
often they land inside the scroll and on bright papyrus, vs the volume's own base rates. A hit-rate well above
baseline (and a higher mean CT value at the labels than the background) means the 3D placement is correct.

Usage:  python validate.py --scroll PHerc0172 --segment <segment_name>
"""
import argparse, numpy as np, fsspec, zarr
from ink3d_lift import fetch_geometry, BUCKET

L = 16  # level-4 downsample factor


def find_volume(fs, scroll):
    vols = [v for v in fs.ls(f"{BUCKET}/{scroll}/volumes") if v.endswith(".zarr")]
    masked = [v for v in vols if "masked" in v]
    return (masked or vols)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scroll", default="PHerc0172")
    ap.add_argument("--segment", required=True)
    ap.add_argument("--volume", default=None, help="scan zarr S3 path (default: auto-find masked volume)")
    a = ap.parse_args()
    fs = fsspec.filesystem("s3", anon=True)
    P = fetch_geometry(fs, f"{BUCKET}/{a.scroll}/segments/{a.segment}")
    valid = ~((P[..., 0] == 0) & (P[..., 1] == 0) & (P[..., 2] == 0))
    S = P[valid]
    vol = a.volume or ("s3://" + find_volume(fs, a.scroll))
    z = zarr.open(fsspec.get_mapper(vol, anon=True), mode="r")
    a4 = z["4"]
    lo = (S.min(0) / L).astype(int) - 1
    hi = (S.max(0) / L).astype(int) + 2
    lo = np.maximum(lo, 0)
    sub = np.asarray(a4[lo[2]:hi[2], lo[1]:hi[1], lo[0]:hi[0]]).astype(np.float32)
    T = np.percentile(sub[sub > 0], 55) if (sub > 0).any() else 0
    zi = np.clip((S[:, 2] / L).astype(int) - lo[2], 0, sub.shape[0] - 1)
    yi = np.clip((S[:, 1] / L).astype(int) - lo[1], 0, sub.shape[1] - 1)
    xi = np.clip((S[:, 0] / L).astype(int) - lo[0], 0, sub.shape[2] - 1)
    v = sub[zi, yi, xi]
    print(f"{len(S):,} surface points vs level-4 scan {sub.shape}")
    print(f"  inside scroll : {np.mean(v > 0) * 100:5.1f}%  (baseline {np.mean(sub > 0) * 100:.1f}%)")
    print(f"  on papyrus>{T:>3.0f}: {np.mean(v > T) * 100:5.1f}%  (baseline {np.mean(sub > T) * 100:.1f}%)")
    print(f"  mean CT at labels {v.mean():.0f} vs background {sub.mean():.0f}  "
          f"({v.mean() / max(sub.mean(), 1):.2f}x)")


if __name__ == "__main__":
    main()
