# VDA 5050 3.0.0 JSON schemas (test fixtures)

Copied from the [`VDA5050/VDA5050`](https://github.com/VDA5050/VDA5050) repository at tag `3.0.0` (released 2026-03-18), directory `json_schemas/`. MIT License, copyright Verband der Automobilindustrie; the license text is in [`LICENSE.txt`](LICENSE.txt).

The tests validate every message the adapter and the simulated vehicle publish against these files. They are test fixtures only and are not shipped in the wheel.

| File | Upstream SHA-256 | Changed here |
|---|---|---|
| `order.schema` | `f7e2d3b5c914e76d28d39e3e5a08b6997e56e9c4cbcceb634f13fe3573986d12` | Yes, see below |
| `instantActions.schema` | `230bfcab4617fb9e8b93c1b9c18c99da43b1c80619e3a1ecc8daa926cd792450` | No |
| `state.schema` | `f00d6620e0d1d20efa99f8ce3bd1a25a578f0c01e96cc9b52548259f4847d307` | No |
| `connection.schema` | `083dffd157e1af2d365e24b73dfc18e404addb3e1e46dd4c7fbab63cd777cafb` | No |

**The one change.** Upstream `order.schema` at `3.0.0` is not valid JSON: it has trailing commas before closing braces (the first at line 314). No JSON parser accepts it as published. The copy here removes those trailing commas and nothing else; `diff` with trailing commas stripped from both files is empty. `factsheet.schema` and `visualization.schema` have the same defect upstream and are not used here.
