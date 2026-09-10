<!-- Target: https://github.com/ScrollPrize/villa/issues/new  |  Labels: none  |  Status: DRAFT, not filed -->

# `s5-fiber-directions.zarr` has no root `.zgroup`/`.zattrs`, so the `.zarr` path cannot be opened as a group even though `horizontal/` and `vertical/` inside it are valid

**In one sentence:** `full-scrolls/Scroll5/PHerc172.volpkg/representations/direction_fields/s5-fiber-directions.zarr/` contains two valid Zarr groups (`horizontal/`, `vertical/`) but no `.zgroup` or `zarr.json` at the `.zarr` root, so opening the path the name advertises fails and users have to know to open the children directly; its sibling `s5-structure-tensor` (no `.zarr` suffix) does have the root header.

**I was trying to:** Audit the public OME-Zarr corpus for pyramid integrity before relying on reduced-resolution levels in a segmentation/ink-detection pipeline.

**Using:**
- Data: `https://dl.ash2txt.org/full-scrolls/Scroll5/PHerc172.volpkg/representations/direction_fields/` (checked 2026-09-09, re-checked 2026-09-10)
- Tool: [`zarr-pyramid-audit`](https://github.com/sgsllc-jr/zarr-pyramid-audit) `bin/audit_pyramid.py` @ `b3b258b`, Python 3.12.3, zarr 3.3.0
- Command: `python bin/audit_pyramid.py --base https://dl.ash2txt.org/ --root full-scrolls/Scroll5/PHerc172.volpkg/representations/direction_fields/s5-fiber-directions.zarr`

**What happened:**

| path (under `direction_fields/`) | `.zgroup` | `.zattrs` |
|---|---|---|
| `s5-fiber-directions.zarr/` | **404** | **404** |
| `s5-fiber-directions.zarr/horizontal/` | 200 | 404 |
| `s5-fiber-directions.zarr/vertical/` | 200 | 404 |
| `s5-structure-tensor/` (sibling) | 200 | 200 |

Root listing of `s5-fiber-directions.zarr/` is exactly `horizontal/  vertical/` — no metadata file of any kind. The auditor classifies it as `CONTAINER_NO_GROUP_HEADER`: 2/2 probed children are Zarr nodes, root has no group header. Nothing in the standard tells a client to descend into an unlabelled directory looking for groups, so `zarr.open_group("…/s5-fiber-directions.zarr", mode="r")` has no metadata to open.

**What I expected or needed:** A `.zgroup` (`{"zarr_format": 2}`) at the `.zarr` root — one file — so the store opens at the path its name gives, and `horizontal`/`vertical` show up as its members. A `.zattrs` describing the fields (as `s5-structure-tensor/.zattrs` does with `original_volume_shape`, `patch_size`, `sigma`, …) would be a bonus.

**Evidence / reproduction:**
```
for f in .zgroup .zattrs horizontal/.zgroup vertical/.zgroup; do printf "$f "; curl -s -o /dev/null -w "%{http_code}\n" https://dl.ash2txt.org/full-scrolls/Scroll5/PHerc172.volpkg/representations/direction_fields/s5-fiber-directions.zarr/$f; done
```
Output: `404 404 200 200`.

Artifact: 1 × `CONTAINER_NO_GROUP_HEADER` (low) in [`audit_pyramid.findings.csv`](https://github.com/sgsllc-jr/zarr-pyramid-audit/blob/main/artifacts/2026-09-09/audit_pyramid.findings.csv).

- [x] I personally encountered or reproduced this using the version and data stated above.

## Details

- Low severity: no data is missing or wrong, and anyone who lists the directory will figure it out. Filed because it is a one-file fix and because it is the only official root in the corpus with this shape.
- Minor: the two direction-field representations are named inconsistently — `s5-fiber-directions.zarr` vs `s5-structure-tensor` — which is what makes the missing header surprising (the one *with* the `.zarr` suffix is the one that doesn't open).
