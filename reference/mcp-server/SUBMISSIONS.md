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

## Channel 3: the Claude directory (separate from the registry)

Publishing to the open registry does NOT list the server in Claude; Anthropic
says so explicitly. The Claude directory / Claude Marketplace is one separate
submission at [claude.ai/directory/manage](https://claude.ai/directory/manage)
(any paid plan, community listing by default, Verified decided by Anthropic
during review; submissions are auto-scanned). Connector listings are
remote-only; a local stdio server like ours reaches the directory only inside
a Claude Code **plugin bundle** (desktop extensions / MCPB are deprecated).
Practical path: wrap the server (`uvx urml-mcp-server` style) plus the Agent
Skill in a plugin and submit that. Founder action; track in the ledger.

## Channel 4: MCP directories (Glama, mcp.so; Smithery and PulseMCP need no action)

Directory landscape as of 2026-11 (re-verified during the LLM-citability
research, notes in `research_notes/` and the maintainer's report):

- **Glama**: auto-indexes GitHub, but checked 2026-11-25: URML is NOT in
  its index (the expected listing URLs 404, search finds nothing), and the
  "Add Server" flow sits behind sign-in with no public form or documented
  claim process. Likely cause: the server lives in a subfolder of a large
  repo (`reference/mcp-server/`), the shape GitHub crawlers miss, and the
  registry entry is a day old. Playbook:
  1. Wait a week for auto-ingest from the official registry first;
     re-check `https://glama.ai/mcp/servers?query=urml`.
  2. If still absent: sign in at glama.ai with the `ido-beamdesk` GitHub
     account, use the Add Server button, point it at
     `https://github.com/urml-dev/URML` (server in `reference/mcp-server/`).
  3. If the add flow rejects a subfolder server, email `support@glama.ai`
     from `greenvh@gmail.com`:

     > Subject: Listing request: URML MCP server
     >
     > Hi, could you add our MCP server to the directory? It is in the
     > official MCP registry as io.github.urml-dev/urml (PyPI package
     > urml-mcp-server), and the source lives in a subfolder of our main
     > repo: https://github.com/urml-dev/URML/tree/main/reference/mcp-server.
     > Listing metadata is below. I maintain the project and can verify
     > ownership through the urml-dev GitHub org.

     Append the listing metadata block below.
  4. Once listed, claim it while signed in, then fill `submitted_at` /
     `posted_url` in the ledger and refresh the outreach mirror.
- **mcp.so**: checked 2026-11-25: URML is not listed (search returns 0
  results, every plausible `/servers/<slug>` URL 404s). Submission is a
  form at `https://mcp.so/submit?type=server`: one required field,
  Repository URL; the site then fetches name, description, config and
  tools for review before submitting. Two tiers: free (goes live "after
  review", no timeframe published) and a one-time $39 paid tier
  (immediate publish, verified badge, featured placement, dofollow
  link). Playbook:
  1. Sign in at mcp.so (method undocumented; expect GitHub or email),
     open the submit form, enter
     `https://github.com/urml-dev/URML` as the Repository URL. If the
     fetched details come out wrong because the server lives in
     `reference/mcp-server/`, retry with the subfolder URL
     `https://github.com/urml-dev/URML/tree/main/reference/mcp-server`;
     the form does not document whether subfolders are accepted, so
     this is a live test.
  2. Review the fetched name/description against the listing metadata
     block below before submitting; fix drift in the form, not by
     accepting whatever it scraped.
  3. Use the FREE tier. The $39 tier buys placement and a badge, which
     is directory vanity, not adoption; paying for priority placement
     is off-ethos unless the founder decides otherwise.
  4. Once live, fill `submitted_at` / `posted_url` in the ledger and
     refresh the outreach mirror.
- **PulseMCP**: submissions frozen; it re-ingests from the official registry,
  so Channel 2 covers it. No action.
- **Smithery**: proxy/CLI hosting shut down 2026-10-31; the directory
  continues under Arcade.dev with no documented submission path. No action.

They are directory listings, not the source of truth;
[`server.json`](server.json) is. Claim under `greenvh@gmail.com`.

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
