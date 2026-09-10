<!-- Target: https://github.com/ScrollPrize/villa/issues/new  |  Labels: none  |  Status: DRAFT, not filed -->

# Scroll 5 volume `20241024131838.zarr`: levels 1–5 are stored uncompressed (`compressor: null`, 389 GB) while level 0 is `blosc/zstd` — the same L0-compressed / L1+-null signature appears in 8 community pyramids

**In one sentence:** Nine multiscale pyramids on `dl.ash2txt.org` — one official Scroll 5 volume and eight `community-uploads/bruniss` masks — have a compressed level 0 and `compressor: null` at every reduced level, which for the Scroll 5 CT volume is a 389 GB policy inconsistency with only ~2 % recoverable, and for the binary masks is ~128 GB stored where ~115 GB (86–96 %) would compress away.

**I was trying to:** Audit the public OME-Zarr corpus for pyramid integrity before relying on reduced-resolution levels in a segmentation/ink-detection pipeline.

**Using:**
- Data: `https://dl.ash2txt.org/full-scrolls/Scroll5/PHerc172.volpkg/volumes_zarr/20241024131838.zarr` plus the 8 bruniss roots listed below (checked 2026-09-09, re-checked 2026-09-10)
- Tools: [`zarr-pyramid-audit`](https://github.com/sgsllc-jr/zarr-pyramid-audit) `bin/audit_pyramid.py` (finds the drift, header-only) and `bin/count_chunks.py` (counts chunks actually present, `HEAD`s 40 per level for stored size, re-encodes 6 per level locally for a real ratio) @ `b3b258b`; Python 3.12.3, zarr 3.3.0, numcodecs
- Command: `python bin/count_chunks.py --base https://dl.ash2txt.org/ --from-findings audit_pyramid.findings.csv --code COMPRESSOR_DRIFT --head-sample 40 --compress-sample 6`

**What happened:**

Scroll 5, `20241024131838.zarr`, `0/.zarray`:
```json
"compressor": {"id": "blosc", "cname": "zstd", "clevel": 3, "shuffle": 2, "blocksize": 0}
```
`1/.zarray` … `5/.zarray`:
```json
"compressor": null
```
Same dtype `<u2`, same `128³` chunks, same `dimension_separator: "/"`. Every one of the 92,839 chunks at L1–5 is present and every sampled chunk is exactly 4,194,304 bytes (the full padded size), so stored size is exact, not extrapolated:

| level | shape | grid chunks | present | stored | zstd-3 ratio on 6-chunk sample |
|---|---|---|---|---|---|
| 1 | `[10500,3350,4550]` | 80,676 | 80,676 | 338.4 GB | 1.014 |
| 2–5 | | 12,163 | 12,163 | 51.0 GB | ≈1.0 |
| **L1–5** | | **92,839** | **92,839** | **389.4 GB** | **→ 8.1 GB recoverable (2 %)** |

So for the CT volume this is **not** a storage bug in any meaningful sense — dense noisy 16-bit CT barely compresses (the samples came out at 1.4 % smaller). It is a *consistency* defect: L0 says "zstd", L1–5 say "raw", and anything that infers pipeline provenance or expected byte counts from the L0 header is wrong for 5/6 of the pyramid.

The identical signature — L0 compressed, L1–5 `null` — appears in **eight** `community-uploads/bruniss` OME pyramids, all binary/mask-like `|u1` volumes with `blosc/lz4/l5` at L0:

| root (under `community-uploads/bruniss/`) | present chunks L1–5 | stored | recoverable @ zstd-3 |
|---|---|---|---|
| `scrolls/s1/surfaces/full_scroll/mask-2ext-surface-evenmore_ome.zarr` | 8,580 | 18.0 GB | 15.5 GB (86 %) |
| `scrolls/s1/surfaces/full_scroll/mask-2ext-surface_erode_evenmore_ome.zarr` | 8,531 | 17.9 GB | 15.8 GB (88 %) |
| `scrolls/s1/fibers_3d/gp_only/old/mask-fiber-only_ome.zarr` | 8,888 | 18.6 GB | 17.1 GB (92 %) |
| `scrolls/s1/fibers_3d/gp_only/old/mask-hz-only_ome.zarr` | 8,806 | 18.5 GB | 17.7 GB (96 %) |
| `scrolls/s1/surfaces/gp_only/old/mask-2ext-surface-erode_ome.zarr` | 8,679 | 18.2 GB | 17.3 GB (95 %) |
| `scrolls/s1/surfaces/gp_only/old/mask-2ext-surface_ome.zarr` | 8,871 | 18.6 GB | 16.0 GB (86 %) |
| `scrolls/s1/surfaces/gp_only/old/surface2xt-updated_ome.zarr` | 8,603 | 18.0 GB | 15.7 GB (87 %) |
| `labels/surfaces/archive/1-voxel-sheet_slices-closed.zarr` | 0 (header-only; see separate issue) | 0 | 0 |
| **total** | | **127.8 GB** | **≈115 GB** |

Here the storage cost *is* real: masks are mostly zeros and compress 7–25×. Caveat on the recoverable figures: the ratio is measured on 6 chunks per level and the spread between sibling volumes is ~3.5×, so treat "≈115 GB" as order-of-magnitude, not a quote.

**What I expected or needed:** Reduced levels written with the same codec as level 0 (or a deliberately chosen one), by whatever generates them. Two uploaders, two codecs, one identical failure shape points at a shared downsampling path that creates reduced-level arrays without propagating the base compressor — that's a hypothesis, not something I've confirmed in code.

**Evidence / reproduction:**
```
for l in 0 1; do printf "L$l compressor: "; curl -s https://dl.ash2txt.org/full-scrolls/Scroll5/PHerc172.volpkg/volumes_zarr/20241024131838.zarr/$l/.zarray | python3 -c "import json,sys; print(json.load(sys.stdin)['compressor'])"; done
```
Output: a blosc dict, then `None`. Levels 2–5 also `None`.

Artifacts: 9 × `COMPRESSOR_DRIFT` in [`audit_pyramid.findings.csv`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/audit_pyramid.findings.csv); measured sizes and ratios per level in [`count_chunks.levels.jsonl`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/count_chunks.levels.jsonl) and per root in [`count_chunks.roots.csv`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/count_chunks.roots.csv).

- [x] I personally encountered or reproduced this using the version and data stated above.

## Details

- This is the zarr-corpus counterpart of #1643 (Kaggle release ships 487 uncompressed label volumes): same class of defect — uncompressed data that was meant to be compressed — different surface and, I think, different mechanism (there, whole TIFF volumes; here, only the *derived* levels of otherwise-compressed pyramids).
- Recompression tooling is being actively fixed in #1669 / #1670 / #1682 / #1711. If `recompress` is going to be run over the corpus anyway, these 9 roots (really the 8 populated ones) are the concrete worklist, and the Scroll 5 case argues for **codec consistency** as the goal rather than byte savings, since it saves almost nothing there.
- I have deliberately *not* estimated bandwidth impact on readers: the reduced levels of Scroll 5 are read far more often than L0, and an uncompressed 4 MB chunk vs a ~4 MB zstd chunk is a wash; for the masks it is a 7–25× difference per read.
