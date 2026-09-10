# Issue drafts

Drafts of issues against [ScrollPrize/villa](https://github.com/ScrollPrize/villa/issues) based on the
2026-09-09 audit in [`../artifacts/2026-09-09/`](../artifacts/2026-09-09/). Each follows villa's issue
template. Status of each is in the HTML comment on its first line. Intended filing order is A → F;
F is filed last so it can reference the others by number.

| file | subject | severity |
|---|---|---|
| `A-frag3-phantom-pyramid.md` | Frag3 88 keV: 6 levels declared, only L0 exists (both copies) | high |
| `B-inked-zarrs-3336-predictions.md` | `3336_predictions.zarr` empty at all levels; `…9/10/11` wrong `scale` | high |
| `C-reduced-level-codec-policy.md` | L0 compressed, L1–5 `null` in 9 pyramids; measured sizes/ratios | low |
| `D-s5-fiber-directions-no-zgroup.md` | `.zarr` root has no group header | low |
| `E-bruniss-stores.md` | headerless store, header-only levels, stray partial copy (@bruniss) | high |
| `F-publish-time-pyramid-check.md` | proposal: auditor as publish-time check | — |
