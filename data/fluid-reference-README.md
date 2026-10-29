# Final fluid reference snapshots

`provenance-fluid-reference.json` identifies five final BP files, extracted
offline from the two complete fluid ZIPs after size and publisher-MD5
verification. It binds archive SHA-256, exact member name, extracted-file
CRC32/SHA-256, decoded-array SHA-256, component dimensions and timing metadata.

| Model | Stored frame | Stored time |
|---|---:|---:|
| One-fluid electron and field | 30 | 300.0001500000136 |
| Two-fluid both electrons and field | 30 | 300.0499847996274 |

The embedded Lua inputs match the posted decks byte-for-byte and retain
`tEnd=600/OmegaPe0`, `nFrame=60`, giving nominal output cadence 10 in the
normalized units. The `_300.bp` suffix is a nominal time label; it does not
mean frame 300 or establish identical physical times between models. Use
the stored times when planning or interpreting a baseline comparison.

`experiments/read_gkeyll_bp.py` is a portable optional Linux ADIOS2 CLI. After
extracting exact members into a nonpublic cache, decode without network:

```sh
python experiments/read_gkeyll_bp.py --input /local/cache/example.bp --output-dir /local/cache/decoded
```

The helper accepts multiple single-file BP inputs, exports every variable
to NPZ, and records JSON metadata. Large embedded-input text is retained
locally with its hash rather than printed or included in the portable
receipt. Use the separate `requirements-bp.txt` environment; the original
Windows/core requirements and original pinned scripts remain unchanged.

Electron arrays have shape `[480,640,10]` in `[x,y,component]` order. Field
arrays have shape `[480,640,8]`; all components are retained. Independent
official component-order evidence is in `gkeyll-layout-provenance.json`.
The final raw BP/NPZ arrays and full metadata stay outside the public
repository or under Git-ignored `data/raw/`.

Recorded Gkeyll build attributes remain partial/dirty provenance. The reader
does not certify an original clean executable or silently align different
output times. No new simulation or comparison result is implied by decoding.
