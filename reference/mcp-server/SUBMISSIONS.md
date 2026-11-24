<p align="center">
  <a href="https://urml.dev"><img src="https://urml.dev/favicon.svg" alt="URML" width="72" height="72"></a>
</p>

---

# MCP registry submissions (maintainer action)

Ready-to-run playbook for publishing the URML MCP server to PyPI and the MCP
directories. The in-repo [`server.json`](server.json) is the single source; the
entries here point back to it. These steps need the maintainer's PyPI and GitHub
identity, so they are drafted for the founder to run. Contact field everywhere:
`greenvh@gmail.com`. Track progress in
[`examples/lighthouses/distribution.yaml`](../../examples/lighthouses/distribution.yaml)
(the `track: mcp` rows).

Publishing is irreversible and outward-facing.

---

## Prerequisite: the dependencies on PyPI

`urml-mcp-server` depends on `urml-validator`, `urml-llm-bridge` and
`urml-ros2-runtime` at the family version, so those must be on PyPI first.
Since 0.5.0 all three are, and `release.yml` uploads them before the server.

---

## Channel 1: PyPI (`urml-mcp-server`)

On PyPI since 0.5.0, published by `release.yml` with the rest of the family
(see [`RELEASING.md`](../../RELEASING.md)).

Verify from a clean venv outside the repo before real PyPI:

```bash
urml-mcp --help          # console script resolves
python -m pytest reference/mcp-server/tests   # the hermetic tool tests pass
```

---

## Channel 2: Official MCP Registry (`io.github.urml-dev/urml`)

[`server.json`](server.json) is the manifest for
[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).
The registry hosts no code; it points at the PyPI package, so Channel 1 must be
live first.

**What the registry checks:**
- PyPI ownership: the package README, which becomes the PyPI description,
  must contain `mcp-name: io.github.urml-dev/urml`.
  [`README.md`](README.md) carries it in an HTML comment under the title. The
  line first shipped in 0.5.2; earlier versions on PyPI cannot be registered.
- The version: `server.json` names one exact PyPI version. `bump_version.py`
  moves both of its `"version"` fields with the family, so `--check` catches
  a stale manifest.
- The description: at most 100 characters.
- The namespace: `io.github.urml-dev` needs an Owner of the `urml-dev` org.
  The browser device flow (`mcp-publisher login github`) cannot publish to an
  org namespace at present (registry issue #1468); log in with a token that
  has `read:org` instead, or with `login github-oidc` from a workflow.

**Steps** (after the matching release is on PyPI):
1. Get a current `mcp-publisher` from the
   [registry releases](https://github.com/modelcontextprotocol/registry/releases).
2. From `reference/mcp-server/`: `mcp-publisher validate`.
3. `mcp-publisher login github --token "$(gh auth token)"`, as an org Owner.
4. `mcp-publisher publish`, then confirm the entry at
   `https://registry.modelcontextprotocol.io/v0/servers?search=io.github.urml-dev/urml`.

---

## Channel 3: MCP directories (Smithery, Glama, PulseMCP, mcp.so)

These crawl the ecosystem and let you claim ownership of the listing. After the
registry entry is live, submit / claim each under `greenvh@gmail.com`. They are
directory listings, not the source of truth; [`server.json`](server.json) is.

**Listing metadata:**
- **Name:** URML MCP server (`urml-mcp-server`)
- **One-liner:** Validate-before-actuate robot intent as agent tools: validate a plain-language-derived robot program against the robot's declared capabilities and safety envelope before any actuator moves. The server never calls an LLM.
- **Tags:** robotics, robot-intent, validation, safety, ros2, px4, mcp, open-standard
- **Repo:** https://github.com/urml-dev/URML
- **Homepage:** https://urml.dev
- **License:** BUSL-1.1 (free for non-production use)

---

## After publishing

Track each venue in
[`examples/lighthouses/distribution.yaml`](../../examples/lighthouses/distribution.yaml):
fill `submitted_at` / `posted_url`, keep `response: none` until real adoption
signal. Install counts and listing views are vanity, not engagement. Do not
cite them without corroboration. Keep the server in lockstep with the `urml`
CLI; if the CLI changes, update the tools and re-publish.
