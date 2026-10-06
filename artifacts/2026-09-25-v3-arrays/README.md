# PHerc1667 bare Zarr v3 array classification

## Result

When checking the eight published PHerc1667 label/teacher arrays below for use
in a header-only data inventory, `read_pyramid` treated their `zarr.json`
documents like group metadata. On upstream commit
`661e9f7855270ca7d652472cd9888dd3a3b7ae89`, every array received
`NOT_A_ZARR_GROUP`, `node_kind="unknown"`, and
`group has no multiscales/datasets`.

The change recognizes `node_type="array"` before looking for group-only
multiscales metadata. All eight now receive the existing `BARE_ARRAY`
informational code, `node_kind="array"`, and no group-metadata error. Shape,
chunk shape and dtype are included in the description; attributes remain
available on `PyramidMeta`. Group metadata still follows the existing path.

| Same captured responses | Upstream | Modified |
|---|---:|---:|
| Roots examined | 8 | 8 |
| Correctly classified bare v3 arrays | 0 | 8 |
| `NOT_A_ZARR_GROUP` records | 8 | 0 |
| Group-metadata errors on bare arrays | 8 | 0 |
| Array payload bytes downloaded | 0 | 0 |

This corrects inventory classification. It does **not** find eight corrupt
datasets, decode array contents, improve ink-detection accuracy, or add full
Zarr v3 conformance validation. Both old and new codes are informational, so
this does not change the actionable-defect count.

## Public inputs and provenance

Source prefix:
<https://dl.ash2txt.org/community-uploads/forrest/tsm/PHerc1667/>

- `labels/coarse.zarr`
- `labels/fine.zarr`
- `rectoverso/rectoverso.zarr`
- `teachers/fiber.zarr`
- `teachers/ink.zarr`
- `teachers/lasagna.zarr`
- `teachers/m7_l2.zarr`
- `teachers/recto.zarr`

`headers.json` records the retrieval time, URL, status, exact response text
and SHA-256 for each of 16 requests: `.zgroup` (404) and `zarr.json` (200)
per root. These public metadata responses come from the Vesuvius Challenge
community upload by Forrest McDonald. Data attribution and the CC-BY-NC 4.0
data license are described in the repository's main README and
<https://scrollprize.org/data>. The inherited MIT license covers code, not
the captured data. The eight stores and the previous limitation were already
documented by the original author in
<https://github.com/ScrollPrize/villa/issues/1760>; this work supplies the
classification fix and repeatable regression evidence, not a new discovery
of those stores.

## Reproduce

```bash
# New live capture: 3 requests/second maximum, no chunks or directory crawl.
python bin/reproduce_v3_arrays.py --capture tmp/pherc1667-headers.json

# Offline replay of the submitted evidence; checks response SHA-256 values.
python bin/reproduce_v3_arrays.py --replay artifacts/2026-09-25-v3-arrays/headers.json
python -m unittest discover -s tests -v
```

`before.jsonl` and `after.jsonl` classify exactly the same captured responses.
`tests-before.txt` records the regression tests failing on the original code;
`tests-after.txt` records all six test methods passing, including all eight
real-array subtests. Additional tests cover a v2 bare array, a v3 group,
an OME v3 group with a level, an unknown node type, and array attributes
that resemble group metadata. These small unit cases supplement the real
data reproduction; they are not evidence of additional corpus findings.

Environment: Windows, CPython 3.13, requests 2.34.2. No GPU or paid compute.

## Authorship disclosure

Code, reproduction and this report were produced by OpenAI Codex on behalf
of GitHub user `junter1989k-ai`, who authorized preparing and submitting a
research software contribution. These were agent-executed runs; no claim
of independent human code review or manual scroll annotation is made.
The original auditor and its historical findings remain credited to
`sgsllc-jr` / James Ryan.
