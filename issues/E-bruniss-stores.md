<!-- Target: https://github.com/ScrollPrize/villa/issues/new  |  Labels: none  |  Status: DRAFT, not filed  |  @mention: @bruniss -->

# `community-uploads/bruniss`: one undecodable store (48k chunks, no `.zarray`), one pyramid whose levels 1–5 are header-only, and a stray partial copy of `s5/surfaces/090.zarr` at the parent level

**In one sentence:** Three things under `community-uploads/bruniss/` on `dl.ash2txt.org` will silently mislead a reader — a chunk store with no array header, a 6-level pyramid whose reduced levels return only `fill_value`, and a `surfaces/` directory that carries `090.zarr`'s multiscale metadata plus a partial copy of its levels 3–5 — and only the uploader can say which are meant to exist.

@bruniss — these are your uploads, so tagging you directly; the core team is on the issue because the data is hosted on ScrollPrize infrastructure.

**I was trying to:** Audit the public OME-Zarr corpus for pyramid integrity before relying on reduced-resolution levels in a segmentation/ink-detection pipeline.

**Using:**
- Data: `https://dl.ash2txt.org/community-uploads/bruniss/…` (three roots below; checked 2026-09-09, re-checked 2026-09-10)
- Tool: [`zarr-pyramid-audit`](https://github.com/sgsllc-jr/zarr-pyramid-audit) `bin/audit_pyramid.py` @ `b3b258b`, Python 3.12.3, zarr 3.3.0

**What happened:**

**1. `scrolls/s1/surfaces/gp_only/old/1122_preds/newst-sfc-regular-sm.zarr` — undecodable.**
The directory holds **48,042** dot-separated chunk keys (e.g. `105.40.19`) and no `.zarray`, `.zgroup` or `zarr.json`. Without a header there is no shape, dtype, chunk grid or codec, so the bytes cannot be decoded by any client. Its three siblings in `1122_preds/` — `newst-sfc-regular-thresh.zarr`, `skeleton-sm.zarr`, `skeleton-thresh.zarr` — are bare arrays with a `.zarray` (200) and open fine. Audit code: `HEADERLESS_CHUNK_STORE` (high).

**2. `labels/surfaces/archive/1-voxel-sheet_slices-closed.zarr` — reduced levels are empty.**
Valid `.zattrs` declaring levels 0–5; level 0 is populated (25 top-level chunk dirs); levels 1–5 each have a valid `.zarray` and **no chunk keys at all**. Reads at L1–5 return `fill_value` (0) with no error. L0 is `blosc/lz4/l5`; L1–5 headers say `compressor: null`. Audit codes: 5 × `LEVEL_NO_CHUNKS` (high), 1 × `COMPRESSOR_DRIFT`.

**3. `scrolls/s5/surfaces/` — stray partial duplicate of `090.zarr`.**
The `surfaces/` directory itself has a `.zgroup` and a `.zattrs` that is **byte-identical** to `surfaces/090.zarr/.zattrs` (declares levels 0–5), plus directories `3/`, `4/`, `5/` whose `.zarray` files are identical to `090.zarr/{3,4,5}/.zarray`. Levels `0/`, `1/`, `2/` do not exist at that location. `090.zarr` itself is complete (L0–5 all present).

| location | `.zattrs` | L0 | L1 | L2 | L3 top-level keys | L4 | L5 |
|---|---|---|---|---|---|---|---|
| `s5/surfaces/090.zarr/` | declares 0–5 | 200 | 200 | 200 | 19 | 10 | 6 |
| `s5/surfaces/` (stray) | identical | 404 | 404 | 404 | **2** | 10 | 6 |

So `surfaces/{.zgroup,.zattrs,3,4,5}` look like the remnant of an aborted copy or move into `090.zarr/`: L4 and L5 completed, L3 stopped after two chunk dirs, L0–2 never started. Harmless to `090.zarr`, but the auditor — and any client — sees `surfaces/` as a multiscale group with three missing levels and one partially-populated one. Audit code: 3 × `LEVEL_MISSING` (high).

**What I expected or needed:**
1. `newst-sfc-regular-sm.zarr`: either its `.zarray` restored (if the original still exists) or the directory removed. If the grid matches `newst-sfc-regular-thresh.zarr` — plausible, same prefix — a `.zarray` could be reconstructed from that sibling's with the dtype changed, but only the uploader can say what the dtype and codec were.
2. `1-voxel-sheet_slices-closed.zarr`: levels 1–5 either populated or dropped from `.zattrs` (leaving a single-level pyramid), so reads stop returning silent zeros.
3. `s5/surfaces/{.zgroup,.zattrs,3,4,5}`: deleted, leaving `090.zarr` (and the non-Zarr items `055_grids/`, `059_medial/`, `old/`, `meta.json`, `s5_055_surfaces.7z`) in a plain directory.

**Evidence / reproduction:**

1:
```
curl -s -o /dev/null -w "%{http_code}\n" https://dl.ash2txt.org/community-uploads/bruniss/scrolls/s1/surfaces/gp_only/old/1122_preds/newst-sfc-regular-sm.zarr/.zarray
```
→ `404` (and `…-thresh.zarr/.zarray` → `200`).

2:
```
B=https://dl.ash2txt.org/community-uploads/bruniss/labels/surfaces/archive/1-voxel-sheet_slices-closed.zarr; for l in 0 1 2 3 4 5; do printf "L$l chunks="; curl -s $B/$l/ | grep -c 'href="[^.]'; done
```
→ `25` then five `0`.

3:
```
B=https://dl.ash2txt.org/community-uploads/bruniss/scrolls/s5/surfaces; for l in 0 1 2 3 4 5; do printf "L$l stray="; curl -s -o /dev/null -w "%{http_code}" $B/$l/.zarray; printf " 090="; curl -s -o /dev/null -w "%{http_code}\n" $B/090.zarr/$l/.zarray; done
```
→ `stray=404 090=200` for L0–2, `stray=200 090=200` for L3–5.

Artifacts: all rows with `root` under `community-uploads/bruniss/` in [`audit_pyramid.findings.csv`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/audit_pyramid.findings.csv).

- [x] I personally encountered or reproduced this using the version and data stated above.

## Details

- These are the only three roots under `community-uploads/` (122 of the 241 Zarr roots on the host) with a `high`-severity structural finding; the rest of the bruniss uploads audit clean apart from the reduced-level codec point raised separately.
- Item 3 is housekeeping, not data loss — `090.zarr` is intact. It's included because the stray metadata makes `surfaces/` *look* like a broken pyramid to any tool that walks the tree.
- Item 1 is the only finding in the corpus where data may be genuinely unrecoverable from what's on the server; hence the direct ping.
