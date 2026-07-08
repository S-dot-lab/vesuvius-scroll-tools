#!/usr/bin/env python3
"""
ink3d_lift.py — lift a 2D ink label into a TRUE-3D ink label on CPU (Vesuvius Challenge).

Wishlist #192/#193: ink label generation is currently "entirely manual", and 3D labels tend to be a single 2D
image copied across depth layers. This tool automates the step: given a segment's `tifxyz` (flattened->3D map)
and any 2D ink label/prediction on that surface, it places the ink at its REAL 3D depth by extruding a thin band
along the surface NORMAL, weighted by ink probability (ink-only, not surface). No GPU, no model, ~1 s/segment.

Method
------
- normal  N(u,v) = normalize( dP/dcol x dP/drow )   from the tifxyz coordinate grid
- for depth offsets t in a thin band, 3D point = P(u,v) + t*N(u,v), weight = ink(u,v) * gaussian(t)
- keep only ink-positive points (ink-only). Optionally average multiple model renders (consensus).
- optional: skip segments whose geometry is torn (see ../scroll_segment_qa) so labels aren't built on garbage.

Output: a labelled point cloud (.npz: xyz + ink) and a production label volume (zarr) over the segment bbox.

Usage
-----
    python ink3d_lift.py --scroll PHerc0172 --segment 20251110135803-w067_20251110135803677_flatboi
    python ink3d_lift.py --scroll PHerc0172 --segment <seg> --ink consensus --qa --out out/
"""
import argparse, io, os, time
import numpy as np
import fsspec
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

BUCKET = "vesuvius-challenge-open-data"


def load_tif(buf):
    try:
        return np.array(Image.open(io.BytesIO(buf))).astype(np.float32)
    except Exception:
        import tifffile
        return tifffile.imread(io.BytesIO(buf)).astype(np.float32)


def fetch_geometry(fs, seg_path):
    txd = next(d for d in fs.ls(seg_path + "/mesh") if "tifxyz" in d.split("/")[-1])
    X, Y, Z = (load_tif(fs.cat(f"{txd}/{c}.tif")) for c in ("x", "y", "z"))
    return np.stack([X, Y, Z], -1)


def fetch_ink(fs, seg_path, which):
    """Return a 2D ink map (0..1) for the chosen model, or the consensus (mean) of all renders."""
    items = [x for x in fs.ls(seg_path + "/ink-detection") if x.endswith(".tif")]
    if which != "consensus":
        items = [x for x in items if which in x] or items
    maps = []
    for it in items[: (None if which == "consensus" else 1)]:
        maps.append(load_tif(fs.cat(it)) / 255.0)
    ref = maps[0].shape
    maps = [m if m.shape == ref else
            np.array(Image.fromarray((m * 255).astype(np.uint8)).resize(ref[::-1])) / 255.0 for m in maps]
    return np.mean(maps, axis=0)


def seam_ratio(P, mask, margin=25):
    """Coherent-seam ratio (see ../scroll_segment_qa); >=4 => torn geometry."""
    H, W, _ = P.shape
    inb = np.zeros((H, W), bool); inb[margin:H - margin, margin:W - margin] = True
    du = np.linalg.norm(P[:, 1:] - P[:, :-1], axis=2); mu = mask[:, 1:] & mask[:, :-1] & inb[:, 1:] & inb[:, :-1]
    dv = np.linalg.norm(P[1:] - P[:-1], axis=2); mv = mask[1:] & mask[:-1] & inb[1:] & inb[:-1]
    if mu.sum() < 500:
        return 0.0
    base = np.median(du[mu]) or 1.0
    col = max((np.median(du[mu[:, u], u]) if mu[:, u].sum() > 20 else 0) for u in range(du.shape[1])) / base
    row = max((np.median(dv[v, mv[v]]) if mv[v].sum() > 20 else 0) for v in range(dv.shape[0])) / base
    return float(max(col, row))


def lift_to_3d(P, ink, thickness=2.0, layers=3, ink_thresh=0.15):
    mask = ~((P[..., 0] == 0) & (P[..., 1] == 0) & (P[..., 2] == 0))
    if ink.shape != P.shape[:2]:
        ink = np.array(Image.fromarray((ink * 255).astype(np.uint8)).resize(P.shape[:2][::-1],
                                                                             Image.BILINEAR)) / 255.0
    N = np.cross(np.gradient(P, axis=1), np.gradient(P, axis=0))
    N /= np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-6)
    sel = mask & (ink > ink_thresh)
    ts = np.linspace(-thickness, thickness, layers)
    prof = np.exp(-(ts / (thickness * 0.6)) ** 2)
    xyz = np.concatenate([P[sel] + t * N[sel] for t in ts])
    val = np.concatenate([ink[sel] * w for w in prof])
    return xyz.astype(np.float32), val.astype(np.float32)


def rasterize_zarr(xyz, val, out_path, voxel=4.0, chunk=64):
    """Rasterize points into a SPARSE label volume (max ink per cell). Writes only occupied chunks, so RAM
    stays at one chunk (~1 MB) regardless of bbox size — laptop-safe even for scroll-scale bounding boxes."""
    import zarr
    lo = xyz.min(0)
    idx = np.floor((xyz - lo) / voxel).astype(np.int64)
    shape = tuple(int(s) for s in (idx.max(0) + 1))
    z = zarr.open(out_path, mode="w", shape=shape, chunks=(chunk,) * 3, dtype="f4", fill_value=0.0)
    cidx = idx // chunk
    key = (cidx[:, 0] * 100000 + cidx[:, 1]) * 100000 + cidx[:, 2]     # unique per chunk
    order = np.argsort(key)
    idx, val, key = idx[order], val[order], key[order]
    bounds = np.r_[0, np.flatnonzero(np.diff(key)) + 1, len(key)]
    npos = 0
    for s, e in zip(bounds[:-1], bounds[1:]):
        c0 = (idx[s] // chunk) * chunk
        loc = idx[s:e] - c0
        buf = np.zeros((chunk, chunk, chunk), np.float32)
        np.maximum.at(buf, (loc[:, 0], loc[:, 1], loc[:, 2]), val[s:e])
        a0, a1, a2 = c0
        b0, b1, b2 = min(a0 + chunk, shape[0]), min(a1 + chunk, shape[1]), min(a2 + chunk, shape[2])
        z[a0:b0, a1:b1, a2:b2] = buf[:b0 - a0, :b1 - a1, :b2 - a2]
        npos += int((buf > 0.5).sum())
    z.attrs["origin_voxel"] = lo.tolist(); z.attrs["voxel_size"] = voxel
    z.attrs["note"] = "true-3D ink label (ink probability), CPU-lifted from 2D via surface normals"
    return shape, float(npos)


def process(scroll, segment, ink="november19", qa=False, out="ink3d_out",
            thickness=2.0, layers=3, voxel=4.0):
    fs = fsspec.filesystem("s3", anon=True)
    seg_path = f"{BUCKET}/{scroll}/segments/{segment}"
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    P = fetch_geometry(fs, seg_path)
    mask = ~((P[..., 0] == 0) & (P[..., 1] == 0) & (P[..., 2] == 0))
    ratio = seam_ratio(P, mask)
    if qa and ratio >= 4.0:
        print(f"SKIP {segment}: torn geometry (seam ratio {ratio:.0f}x). Use scroll_segment_qa to inspect.")
        return
    inkmap = fetch_ink(fs, seg_path, ink)
    xyz, val = lift_to_3d(P, inkmap, thickness, layers)
    stem = os.path.join(out, f"{segment[:30]}_{ink}")
    np.savez(stem + "_ink3d.npz", xyz=xyz, ink=val)
    shp, npos = rasterize_zarr(xyz, val, stem + "_ink3d.zarr", voxel)
    print(f"{segment[:34]}  seam {ratio:.1f}x  lifted {len(xyz):,} voxels  "
          f"zarr {shp} ({int(npos):,} ink>0.5)  {time.time()-t0:.1f}s")


def main():
    ap = argparse.ArgumentParser(description="Lift a 2D ink label to a true-3D ink label (CPU).")
    ap.add_argument("--scroll", default="PHerc0172")
    ap.add_argument("--segment", required=True)
    ap.add_argument("--ink", default="november19",
                    help="ink model substring, or 'consensus' to average all renders")
    ap.add_argument("--qa", action="store_true", help="skip segments with torn geometry")
    ap.add_argument("--out", default="ink3d_out")
    ap.add_argument("--thickness", type=float, default=2.0, help="depth band half-width (voxels)")
    ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--voxel", type=float, default=4.0, help="output zarr voxel size")
    a = ap.parse_args()
    process(a.scroll, a.segment, a.ink, a.qa, a.out, a.thickness, a.layers, a.voxel)


if __name__ == "__main__":
    main()
