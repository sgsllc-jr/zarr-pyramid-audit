<!-- Filed: https://github.com/ScrollPrize/villa/issues/1756  |  Labels: none  |  Status: FILED 2026-09-10 as #1756 -->

# `other/dev/inked_zarrs`: `3336_predictions.zarr` has headers at all 6 levels but zero chunks; `3336_predictions{9,10,11}.zarr` declare `scale` vectors that contradict their own shapes

**In one sentence:** In `other/dev/inked_zarrs/`, one published predictions volume (`3336_predictions.zarr`) is an empty shell that reads as all-zeros with no error at every level, and three siblings (`…9`, `…10`, `…11`) carry stale multiscale `scale` metadata that is wrong on the z axis — while `…2` and `…12` in the same directory show what correct looks like.

**I was trying to:** Audit the public OME-Zarr corpus for pyramid integrity before relying on reduced-resolution levels in a segmentation/ink-detection pipeline.

**Using:**
- Data: `https://dl.ash2txt.org/other/dev/inked_zarrs/3336_predictions*.zarr` (7 roots; checked 2026-09-09, re-checked 2026-09-10)
- Tool: [`zarr-pyramid-audit`](https://github.com/sgsllc-jr/zarr-pyramid-audit) `bin/audit_pyramid.py` @ `b3b258b`, Python 3.12.3, zarr 3.3.0
- Command: `python bin/audit_pyramid.py --base https://dl.ash2txt.org/ --root other/dev/inked_zarrs/3336_predictions.zarr` (and each sibling)

**What happened:**

*Part 1 — an empty volume that never errors.* `3336_predictions.zarr` has a valid `.zgroup`, a valid 6-level `.zattrs`, and a valid `.zarray` at every level (`<i4`, `fill_value: 0`, `blosc/lz4/l5`). Every level directory contains **nothing but the `.zarray`**. Because Zarr treats a missing chunk as `fill_value`, `zarr.open()` succeeds and every read at every level returns zeros. No exception, no warning.

| level | shape | chunks | `.zarray` | chunk keys present | dense grid would be |
|---|---|---|---|---|---|
| 0 | `[62,11008,29952]` | `[2,688,1872]` | 200 | **0** | 7,936 |
| 1 | `[31,5504,14976]` | `[2,688,1872]` | 200 | **0** | 1,024 |
| 2 | `[16,2752,7488]` | `[2,688,1872]` | 200 | **0** | 128 |
| 3 | `[8,1376,3744]` | `[2,688,1872]` | 200 | **0** | 16 |
| 4 | `[4,688,1872]` | `[2,688,1872]` | 200 | **0** | 2 |
| 5 | `[2,344,936]` | `[2,688,1872]` | 200 | **0** | 1 |

Its sibling `3336_predictions2.zarr` has the **identical** layout — same dtype `<i4`, same chunk grid `[2,688,1872]`, same shapes, same codec — and is populated (31 top-level chunk dirs at L0, 16 at L1). The empty store looks like an aborted first write whose successful rerun is `…2`.

*Part 2 — stale `scale` metadata.* Three siblings declare a per-level `coordinateTransformations.scale` that does not match the shape ratio between their own levels:

| root | dtype | L0 shape | L1 shape | **declared** L1 scale | **actual** L1 scale (L0/L1) | status |
|---|---|---|---|---|---|---|
| `3336_predictions9.zarr` | `\|u1` | `[62,11008,29952]` | `[31,5504,14976]` | `[2,2,1]` | `[2,2,2]` | wrong: z is halved but declared unscaled |
| `3336_predictions10.zarr` | `<f8` | `[64,11008,29952]` | `[64,5504,14976]` | `[2,2,1]` | `[1,2,2]` | wrong: declared vector is the true one reversed |
| `3336_predictions11.zarr` | `\|u1` | `[64,11008,29952]` | `[64,5504,14976]` | `[2,2,1]` | `[1,2,2]` | wrong: same as 10 |
| `3336_predictions12.zarr` | `\|u1` | `[64,11008,29952]` | `[64,5504,14976]` | `[1,2,2]` | `[1,2,2]` | **correct** |
| `3336_predictions2.zarr`, `…3`, `…4` | | `[62,…]` | `[31,…]` | `[2,2,2]` | `[2,2,2]` | correct |

The error compounds by level: at L5 the declared scale is `[32,32,1]` against an actual `[1,32,32]` (for 10/11), so any consumer mapping L5 voxel coordinates back to L0 through `scale` is off by 32× on two axes. `…12` already has the right vector, so the writer was fixed at some point; 9/10/11 were produced before the fix and never regenerated.

**What I expected or needed:**
1. `3336_predictions.zarr` either populated or removed. An empty-but-valid store is the most dangerous state a published volume can be in, because nothing downstream can tell it apart from a real all-zero prediction.
2. `scale` in `3336_predictions{9,10,11}.zarr/.zattrs` rewritten to match the shape ratios (`[1,2,2]`,`[1,4,4]`… for 10/11; `[2,2,2]`,`[4,4,4]`… for 9), as `…12` and `…2` already do.

**Evidence / reproduction:**

Part 1:
```
B=https://dl.ash2txt.org/other/dev/inked_zarrs/3336_predictions.zarr; for l in 0 1 2 3 4 5; do printf "L$l .zarray="; curl -s -o /dev/null -w "%{http_code}" $B/$l/.zarray; printf "  chunks="; curl -s $B/$l/ | grep -c 'href="[^.]'; done
```
Output: six lines of `.zarray=200  chunks=0`. Swap in `3336_predictions2.zarr` to see `chunks=31`, `16`, `8`, …

Part 2:
```
for n in 9 10 11 12; do printf "predictions$n L1 scale: "; curl -s https://dl.ash2txt.org/other/dev/inked_zarrs/3336_predictions$n.zarr/.zattrs | python3 -c "import json,sys; print(json.load(sys.stdin)['multiscales'][0]['datasets'][1]['coordinateTransformations'][0]['scale'])"; done
```
Output: `[2.0, 2.0, 1.0]` ×3, then `[1.0, 2.0, 2.0]`. Compare with each store's `0/.zarray` and `1/.zarray` `shape`.

Audit artifacts: 6 × `LEVEL_NO_CHUNKS` (high) and 15 × `SCALE_SHAPE_MISMATCH` (high) in [`artifacts/2026-09-09/audit_pyramid.findings.csv`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/audit_pyramid.findings.csv); per-level headers in `audit_pyramid.levels.jsonl` alongside it.

- [x] I personally encountered or reproduced this using the version and data stated above.

## Details

- Both defects are in the same directory, from the same producer, and are fixed by the same person in one sitting — hence one issue.
- The empty-store symptom (silent fill-value reads) is the same user-visible failure as #1674, but the cause is different: there the chunk *lookup* is wrong; here the chunks were never written.
- The `scale` defect matters more since #1346/#1347 made the renderer bind multiscale datasets by declared metadata rather than by array index — that fix is only as good as the metadata it now trusts.
- Since this is under `other/dev/`, I'd understand if the answer is "delete `3336_predictions.zarr`, leave 9–11 as historical". Even then, a one-line note in the directory would save the next person from opening the empty one.
