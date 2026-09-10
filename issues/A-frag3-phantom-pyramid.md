<!-- Target: https://github.com/ScrollPrize/villa/issues/new  |  Labels: none  |  Status: DRAFT, not filed -->

# Frag3 88 keV volumes declare a 6-level pyramid but only level 0 exists (both `volumes_zarr` and `volumes_standardized`)

**In one sentence:** `fragments/Frag3/PHercParis1Fr34.volpkg/{volumes_zarr,volumes_standardized}/88keV_3.24um_.zarr` each carry a `.zattrs` declaring six multiscale levels with full scale transforms, but only `0/` exists on the server — `1/`..`5/` return 404 — while the 54 keV siblings in the same two directories are complete.

**I was trying to:** Audit the public OME-Zarr corpus for pyramid integrity before relying on reduced-resolution levels in a segmentation/ink-detection pipeline.

**Using:**
- Data: `https://dl.ash2txt.org/fragments/Frag3/PHercParis1Fr34.volpkg/volumes_zarr/88keV_3.24um_.zarr` and `.../volumes_standardized/88keV_3.24um_.zarr` (checked 2026-09-09 and re-checked 2026-09-10)
- Tool: [`zarr-pyramid-audit`](https://github.com/sgsllc-jr/zarr-pyramid-audit) `bin/audit_pyramid.py` @ `b3b258b` (header-only, read-only), Python 3.12.3, zarr 3.3.0
- Command: `python bin/audit_pyramid.py --base https://dl.ash2txt.org/ --root fragments/Frag3/PHercParis1Fr34.volpkg/volumes_zarr/88keV_3.24um_.zarr`

**What happened:**

Root listing of each 88 keV store is exactly `0/  .zattrs  .zgroup`. The `.zattrs` is well-formed OME-NGFF 0.4 and declares `datasets` with `path` `"0"`..`"5"` and `scale` `[1,1,1]`, `[2,2,2]`, … `[32,32,32]`. Any client that trusts the manifest and requests a reduced level gets a 404 (over HTTP) or `KeyError`/`FileNotFoundError` (via zarr), not a "this pyramid has one level" answer.

| store | dtype | L0 shape | L0 | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|---|---|---|
| `volumes_zarr/88keV_3.24um_.zarr` | `<u2` | `[6650,1644,6108]` | 200 | 404 | 404 | 404 | 404 | 404 |
| `volumes_standardized/88keV_3.24um_.zarr` | `\|u1` | `[6650,1644,6108]` | 200 | 404 | 404 | 404 | 404 | 404 |
| `volumes_zarr/54keV_3.24um_.zarr` (sibling) | `<u2` | `[6656,1440,6312]` | 200 | 200 | 200 | 200 | 200 | 200 |
| `volumes_standardized/54keV_3.24um_.zarr` (sibling) | `\|u1` | `[6656,1440,6312]` | 200 | 200 | 200 | 200 | 200 | 200 |

Level 0 itself is populated (32 top-level chunk dirs, `blosc/zstd/l3`, `128³` chunks) — the data is fine; the pyramid is not.

**What I expected or needed:** Either the five reduced levels present as declared, or a `.zattrs` that declares only the level that exists.

**Evidence / reproduction:**

```
for l in 0 1 2 3 4 5; do printf "L$l "; curl -s -o /dev/null -w "%{http_code}\n" https://dl.ash2txt.org/fragments/Frag3/PHercParis1Fr34.volpkg/volumes_zarr/88keV_3.24um_.zarr/$l/.zarray; done
```
Output: `L0 200` then `L1..L5 404`. Same result with `volumes_standardized` substituted.

Audit artifacts (10 × `LEVEL_MISSING`, severity `high`): [`artifacts/2026-09-09/audit_pyramid.findings.csv`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/audit_pyramid.findings.csv)

- [x] I personally encountered or reproduced this using the version and data stated above.

## Details

- **Scope is narrow.** Of 34 Zarr roots under `fragments/` on `dl.ash2txt.org`, these two are the *only* ones with any declared-but-missing level. The 54 keV volumes in the same `volpkg` — same acquisition, same export path — are complete. This looks like one export/upload job that stopped after level 0, not a convention.
- **No mirror to fall back to.** `s3://vesuvius-challenge-open-data/PHercParis1Fr34/` contains a single photo; no fragment volumes are on S3. `dl.ash2txt.org` is the only host of this volume, so the reduced levels are missing everywhere.
- **Why it matters even though L0 is intact.** Viewers navigate at L3–5, QC/registration runs at L2, and some published models train on a specific level. A manifest that promises those levels and 404s is worse than one that doesn't promise them: it fails at first use, after the pipeline has been written against it.
- **Cheap fix.** Regenerate `1/`..`5/` from the intact `0/` with the same tool that produced the 54 keV pyramids (which use `ceil` rounding and `blosc/zstd/l3` at every level), or trim `.zattrs` to `datasets: [{path: "0"}]` until that happens.
- Related: #1652 covers a *different* Frag/Scroll-identity reachability problem for 88 keV data; this issue is about a pyramid that is reachable but incomplete.
