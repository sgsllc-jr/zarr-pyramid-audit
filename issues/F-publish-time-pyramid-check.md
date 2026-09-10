<!-- Target: https://github.com/ScrollPrize/villa/issues/new  |  Labels: none  |  Status: DRAFT, not filed  |  File LAST so it can link A–E by number -->

# Proposal: a header-only OME-Zarr pyramid integrity check at publish time — the whole class of defects it catches is invisible to every reader by construction

**In one sentence:** A read-only audit of all 241 Zarr roots on `dl.ash2txt.org` (141 s, a few KB per pyramid, no chunk bytes downloaded) found 18 pyramids with structural defects that no Zarr client will ever raise an error about — declared levels that don't exist, levels with headers but no chunks, `scale` vectors contradicting shapes, codec drift, a chunk store with no header — and I'd like to offer the checker as a publish-time gate so the corpus stops accumulating them.

**I was trying to:** Audit the public OME-Zarr corpus for pyramid integrity before relying on reduced-resolution levels in a segmentation/ink-detection pipeline.

**Using:**
- [`zarr-pyramid-audit`](https://github.com/sgsllc-jr/zarr-pyramid-audit) @ `b3b258b` (MIT): `bin/discover_zarr.py` → `bin/audit_pyramid.py` → `bin/count_chunks.py`; Python 3.12, zarr 3.3.0, requests
- Data: everything Zarr-shaped under `https://dl.ash2txt.org/`, run 2026-09-09 18:48–18:50 UTC
- Commands: `python bin/discover_zarr.py --base https://dl.ash2txt.org/ --max-depth 10` then `python bin/audit_pyramid.py --base https://dl.ash2txt.org/ --roots discover_zarr.roots.jsonl --max-rps 25`

**What happened:**

Discovery crawled 19,995 directory listings (0 errors) and found 241 Zarr roots. The auditor then read `.zattrs` plus one `.zarray` per level for each, and one directory listing per present level to test for chunk presence:

| | |
|---|---|
| roots audited | 241 |
| clean | 111 |
| with structural defects | **18** |
| findings: high / low / info | 40 / 10 / 125 |
| wall time | 141 s |

The actionable codes and what they caught (informational codes like `BARE_ARRAY`, `NOT_MULTISCALE`, `CHUNK_EXCEEDS_SHAPE` are excluded — they describe what a node *is*, not a defect):

| code | hits | what it means | where it fired |
|---|---|---|---|
| `LEVEL_MISSING` | 13 | level declared in `multiscales`, no array header | Frag3 88 keV ×2 (→ issue A), bruniss `s5/surfaces` (→ E) |
| `LEVEL_NO_CHUNKS` | 11 | header present, **zero chunk keys**; every read returns `fill_value`, no error | `3336_predictions.zarr` all 6 levels (→ B), bruniss L1–5 (→ E) |
| `SCALE_SHAPE_MISMATCH` | 15 | declared `scale` matches neither ceil nor floor of shape ratio | `3336_predictions{9,10,11}` (→ B) |
| `COMPRESSOR_DRIFT` | 9 | codec changes between levels | Scroll 5 + 8 bruniss (→ C) |
| `HEADERLESS_CHUNK_STORE` | 1 | chunk keys, no `.zarray`/`.zgroup` — undecodable | bruniss (→ E) |
| `CONTAINER_NO_GROUP_HEADER` | 1 | children are Zarr, root isn't | `s5-fiber-directions.zarr` (→ D) |

Every one of these passes `zarr.open()`. A missing level fails only when someone finally asks for it. An empty level returns plausible zeros forever. A wrong `scale` gives silently wrong geometry (exactly the failure mode #1346/#1347 fixed the *reader* side of). Codec drift is invisible unless you diff headers. That is the failure class: **the data format has no place to be wrong loudly**, so the check has to happen at write/publish time or not at all.

**What I expected or needed:** Something that runs when a volume is published (or nightly over the host) and refuses — or at least flags — a pyramid whose manifest and directory tree disagree. Concretely, the auditor already does this; what I'm asking is whether you'd want it (a) as an external tool you point at the host, (b) as a check inside whatever publishes to `dl.ash2txt.org` / the open-data bucket, or (c) as a subcommand of the `vesuvius` package. I'm happy to do the work for whichever fits, or to have you take the code — it's MIT.

**Evidence / reproduction:**

Full artifacts of the run — per-level records, per-pyramid records, findings CSV, summary, and a provenance manifest (argv, host, package versions) — are committed at [`artifacts/2026-09-09/`](https://github.com/sgsllc-jr/zarr-pyramid-audit/tree/main/artifacts/2026-09-09). Every finding in the six-issue set (A–E plus this one) has a one-line `curl` reproduction in its own issue.

Re-running the corpus audit yourself:
```
git clone https://github.com/sgsllc-jr/zarr-pyramid-audit && cd zarr-pyramid-audit && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python bin/discover_zarr.py --base https://dl.ash2txt.org/ --max-depth 10 --out-dir tmp && python bin/audit_pyramid.py --base https://dl.ash2txt.org/ --roots tmp/discover_zarr.roots.jsonl --max-rps 25 --out-dir tmp
```
(~13 min for discovery, ~2.5 min for the audit, rate-limited to 25 req/s.)

**Independent reproduction (2026-09-10).** A second run from a fresh clone in a separate venv reproduced `LEVEL_MISSING` 13, `LEVEL_NO_CHUNKS` 11, `SCALE_SHAPE_MISMATCH` 15 and `CONTAINER_NO_GROUP_HEADER` 1 exactly. That run used the script's default `--max-depth 6`, which does not reach the 20 roots that sit 7–8 path segments deep (19 under `community-uploads/bruniss/scrolls/s1/…`, 1 under `Scroll5/…/representations/predictions/fibers/`), so it found 229 roots and only 2 of the 9 `COMPRESSOR_DRIFT` hits; the 20 omitted roots were confirmed live by direct request afterwards. The commands above pin `--max-depth 10` for that reason. The same run also surfaced 8 roots under `community-uploads/forrest/tsm/PHerc1667/` that did not exist on 2026-09-09 — see the zarr v3 limitation below.

- [x] I personally encountered or reproduced this using the version and data stated above.

## Details

**Design points that matter for a publish gate**

- **Header-only.** Judged from `.zattrs` + one `.zarray` per level; cost is independent of array size. The chunk-presence check adds one directory listing per level.
- **Absence is only inferred from positive evidence.** `LEVEL_NO_CHUNKS` trusts a listing to prove emptiness only if that listing demonstrably shows dotfiles (it must contain the `.zarray` it was asked to list). If the server hides dotfiles or has no autoindex, the result is `unknown` and *no finding is emitted*. Tri-state, never a boolean — this is what keeps the check safe to point at S3 or a stricter web server without producing a false alarm per level.
- **Two rounding conventions accepted.** Shapes are checked against both `ceil(base/2ⁱ)` and `floor(base/2ⁱ)`; only a shape matching neither is flagged, and a pyramid mixing the two gets `MIXED_ROUNDING` separately.
- **Severity is honest.** `info` codes describe what a node is. Only `high`/`low` are defects. 125 of the 175 findings in this run are `info` and are not in the table above.
- **Read-only, rate-limited, idempotent.** Nothing is written to the host; outputs are backed up rather than overwritten.

**What this run did *not* cover**

- The open-data S3 bucket. 64 of the 241 roots mirror the 64 volumes there; the audit was run against `dl.ash2txt.org` only. S3 listing is a natural extension (the chunk-presence tri-state was designed for it) but is not exercised in the committed artifacts.
- Chunk *content*. Nothing here decodes voxels; a level whose chunks exist but are corrupt would pass.
- Zarr **v3** (`zarr.json`) stores. The auditor reads v2 headers only; a v3 root is reported as `NOT_A_ZARR_GROUP` (severity `info`, not counted as a defect) and its pyramid is not checked. Eight such roots now exist under `community-uploads/forrest/tsm/PHerc1667/`. v3 support is the obvious next step for anything used as a publish gate.

**Related**
- #1643 (uncompressed Kaggle labels), #1649, #1652 — same genre of "published data doesn't match its own manifest", found by hand. A gate would have caught A, B, C, D of this set mechanically at publish time.
- #1674 — the same silent-fill-value symptom as `LEVEL_NO_CHUNKS`, different cause.
- #1346 / #1347 — made the reader trust `scale`; `SCALE_SHAPE_MISMATCH` is the write-side complement.
