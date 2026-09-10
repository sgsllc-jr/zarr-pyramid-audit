# Issue drafts

Drafts of issues against [ScrollPrize/villa](https://github.com/ScrollPrize/villa/issues) based on the
2026-09-09 audit in [`../artifacts/2026-09-09/`](../artifacts/2026-09-09/). Each follows villa's issue
template. All six were filed on 2026-09-10 as villa #1755–#1760, in order A → F (F last so it could
reference the others by number). Each file's first line records its issue URL; the body posted is the file minus
that comment and the H1 (which became the title).

| file | filed as | subject | severity |
|---|---|---|---|
| `A-frag3-phantom-pyramid.md` | [#1755](https://github.com/ScrollPrize/villa/issues/1755) | Frag3 88 keV: 6 levels declared, only L0 exists (both copies) | high |
| `B-inked-zarrs-3336-predictions.md` | [#1756](https://github.com/ScrollPrize/villa/issues/1756) | `3336_predictions.zarr` empty at all levels; `…9/10/11` wrong `scale` | high |
| `C-reduced-level-codec-policy.md` | [#1757](https://github.com/ScrollPrize/villa/issues/1757) | L0 compressed, L1–5 `null` in 9 pyramids; measured sizes/ratios | low |
| `D-s5-fiber-directions-no-zgroup.md` | [#1758](https://github.com/ScrollPrize/villa/issues/1758) | `.zarr` root has no group header | low |
| `E-bruniss-stores.md` | [#1759](https://github.com/ScrollPrize/villa/issues/1759) | headerless store, header-only levels, stray partial copy (@bruniss) | high |
| `F-publish-time-pyramid-check.md` | [#1760](https://github.com/ScrollPrize/villa/issues/1760) | proposal: auditor as publish-time check | — |
