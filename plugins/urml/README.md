# URML plugin for Claude Code

URML (Universal Robot Language) is a small, human-readable language for describing what a robot should do. This plugin gives Claude two things: an MCP server whose tools validate and run URML programs, and an Agent Skill that teaches Claude the translate, validate, execute loop.

The rule the tools enforce: no program reaches an actuator until it passes static verification against the robot's declared capability manifest and the active safety envelope. Claude does the language work; the validator decides what is admissible. When the robot cannot do what was asked, the honest output is a refusal, not a guess.

## Install

```text
/plugin marketplace add urml-dev/URML
/plugin install urml@urml-dev
```

The MCP server runs locally over stdio via `uvx` from PyPI (`urml-mcp-server`, pinned per release). Everything works offline and without an API key; try a hermetic round trip with no robot attached:

```bash
pip install urml-validator urml-llm-bridge
urml init my-robot --profile home && cd my-robot
urml validate program.urml.yaml --manifest manifest.yaml --envelope envelope.yaml --profile home
```

## What you get

- MCP tools to validate a URML program against a capability manifest and safety envelope, and to execute validated programs on a reference runtime.
- The `urml-robot-intent` skill: when to write URML, how to revise from validator errors, and when to refuse.

## License

Source-available under the Business Source License 1.1: free for research, teaching, evaluation, development, testing and simulation; production use needs a commercial license (see [urml.dev/pricing](https://urml.dev/pricing)). The spec, runtimes and conformance suite live in [urml-dev/URML](https://github.com/urml-dev/URML).
