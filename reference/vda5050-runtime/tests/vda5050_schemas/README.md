# VDA 5050 JSON schemas (test fixtures)

Copied unmodified from the [`VDA5050/VDA5050`](https://github.com/VDA5050/VDA5050) repository, `main` branch at commit [`f480c40`](https://github.com/VDA5050/VDA5050/tree/f480c4020c91577841400b27390e8eb38120e434/json_schemas) (2026-11-11), directory `json_schemas/`. MIT License, copyright Verband der Automobilindustrie; the license text is in [`LICENSE.txt`](LICENSE.txt).

The tests validate every message the adapter and the simulated vehicle publish against these files. They are test fixtures only and are not shipped in the wheel.

| File | SHA-256 |
|---|---|
| `order.schema` | `3d8b37a6660d72dd8c581f8df583cb722a04a0b03f9fc9e7c4c59897fe29d902` |
| `instantActions.schema` | `230bfcab4617fb9e8b93c1b9c18c99da43b1c80619e3a1ecc8daa926cd792450` |
| `state.schema` | `9cb308fb2b59c591f518dabd32f030430e26963e5ad38e08d199eb1650dfc061` |
| `connection.schema` | `50710e678b56ddeffe2af7f3c87687abd20f425d62235e05809895074abbd555` |

**Why `main` and not the `3.0.0` tag.** The VDA 5050 core team keeps the schemas on the repository branch and does not release them: "Schemas are always updated in the respective GitHub branch directly" ([VDA5050/VDA5050#660](https://github.com/VDA5050/VDA5050/issues/660), 2026-10-22). The `3.0.0` tag's `order`, `factsheet` and `visualization` schemas contain trailing commas and do not parse; `main` fixed that in [#599](https://github.com/VDA5050/VDA5050/pull/599). The commits on `main` since `3.0.0` correct the 3.0.0 schemas (a unit, an enum, descriptions) and do not change the message format, so these files describe 3.0.0 messages.

To update: pick a newer `main` commit, copy the four files unchanged, and update the commit and the hashes above.
