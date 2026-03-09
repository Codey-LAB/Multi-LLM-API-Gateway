---
title: Universal MCP Hub
emoji: 👀
colorFrom: indigo
colorTo: red
sdk: docker
pinned: false
license: apache-2.0
short_description: 'Universal MCP Server(Sandboxed) built on PyFundaments '
---

# Universal MCP Hub (Sandboxed)
The only real (MCP) HUB you need!

> running on simpleCity and **paranoidMode** — built on [PyFundaments](PyFundaments.md).

... because too many (Hype) MCP servers exist with no sandboxing, hardcoded keys, and zero security thought. 


#### This one is different.

- **No key → no tool → no crash**
- `main.py` = Guardian (controls everything, nothing bypasses it)
- `app/app.py` receives only injected, validated services — never reads `os.environ` directly
- Every tool is registered dynamically — only if the API key exists

> *"I use AI as a tool, not as a replacement for thinking."* — Volkan Kücükbudak

---

## Quick Start

1. **Fork/Clone** this Repo (Space)
2. Add your API keys as **Space Secrets** (Settings → Variables and secrets)
3. Space starts automatically — only tools with valid keys are registered

That's it. No config files to edit, no code to touch.

[Demo for `cloning space`](https://huggingface.co/spaces/codey-lab/Universal-MCP-Hub-DEMO) on HF

---

## Available Tools

Tools are registered automatically based on which keys you configure. No key = tool doesn't exist. No crashes, no errors, no exposed secrets.

| Secret | Tool | Description |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | `llm_complete` | Claude Haiku / Sonnet / Opus |
| `GEMINI_API_KEY` | `llm_complete` | Gemini Flash / Pro |
| `OPENROUTER_API_KEY` | `llm_complete` | 100+ models via OpenRouter |
| `HF_TOKEN` | `llm_complete` | HuggingFace Inference API |
| `BRAVE_API_KEY` | `web_search` | Web Search (independent index) |
| `TAVILY_API_KEY` | `web_search` | AI-optimized Search |
| `DATABASE_URL` | `db_query` | Read-only DB access (SELECT only) |
| *(always active)* | `list_active_tools` | Lists all currently active tools |
| *(always active)* | `health_check` | System health + uptime |

All LLM providers share a single `llm_complete` tool with automatic **fallback chain**: `anthropic → gemini → openrouter → huggingface`

---

## MCP Client Configuration (SSE)

Connect Claude Desktop or any MCP-compatible client:

```json
{
  "mcpServers": {
    "universal-mcp-hub": {
      "url": "https://YOUR_USERNAME-universal-mcp-hub.hf.space/sse"
    }
  }
}
```

For private Spaces, add your HF token:

```json
{
  "mcpServers": {
    "universal-mcp-hub": {
      "url": "https://YOUR_USERNAME-universal-mcp-hub.hf.space/sse",
      "headers": {
        "Authorization": "Bearer hf_..."
      }
    }
  }
}
```

---

## Desktop Client
#### Perfect for non-public spaces


- A standalone PySide6 desktop client is included: `hub.py`, with help of ClaudeAi, was to lazy 😄
- Features: Chat tab, Tools inspector, Settings (provider/model override, font size), Logs — all saved locally in `~/.mcp_desktop.json`. Token never leaves your machine except to your own Hub.
- more about the [Desktop Client](DESKTOP_CLIENT/README.md)

---

## Architecture
```
UMH
├── main.py # run main!
├── README.md
├── ESOL
├── LICENSE
├── PyFundaments.md
├── PyFundaments – Function Overview.md
├── SECURITY.md
├── requirements.txt
├── .gitignore
├── example.Dockerfile
├── example-mcp___.env
├── DESKTOP_CLIENT
│   └── hub.py        ← light MCP Desktop client
├── app/
│   ├── __init__.py
│   ├── app.py        ←  sandboxed Orchestrator
│   ├── mcp.py        ← MCP SSE server (FastMCP + Quart)
│   ├── tools.py      ← Tool registry (from .pyfun)
│   ├── provider.py   ← LLM + Search execution + fallback
│   ├── models.py     ← Model limits + costs
│   ├── db_sync.py    ← Internal SQLite state (IPC)
│   ├── config.py     ← .pyfun parser (single source of truth)
│   └── .pyfun        ←  single source of truth
├── fundaments/ # do not touch!
│   ├── __init__.py
│   ├── access_control.py
│   ├── config_handler.py
│   ├── encryption.py
│   ├── postgresql.py
│   ├── security.py
│   └── user_handler.py
└── docs/
    ├── access_control.py.md
    ├── encryption.py.md
    ├── postgresql.py.md
    ├── security.py.md
    └── user_handler.py.md



```

**The Guardian pattern:** `app/*` never touches `os.environ`, `.env`, or `fundaments/` directly. Everything is injected by `main.py` as a validated `fundaments` dict. The sandbox is structural — not optional.

---

## Configuration (.pyfun)

All app behavior is configured via `app/.pyfun` — a structured, human-readable config format:

```ini
[LLM_PROVIDER.anthropic]
active           = "true"
env_key          = "ANTHROPIC_API_KEY"
default_model    = "claude-haiku-4-5-20251001"
fallback_to      = "gemini"
[LLM_PROVIDER.anthropic_END]

[TOOL.llm_complete]
active           = "true"
provider_type    = "llm"
default_provider = "anthropic"
timeout_sec      = "60"
[TOOL.llm_complete_END]
```

Add a new tool/Provider/API_URL or something else just = edit `.pyfun` only. No code changes required.

---

## Security Design

- All API keys via e.g. HF Space Secrets — never hardcoded, never in `.pyfun`
- `list_active_tools` returns key **names** only, never values
- DB tools are `SELECT`-only, enforced at application level
- Direct execution of `app/*` is blocked by design
- `app/*` has zero access to `fundaments/` internals
- Built on [PyFundaments](PyFundaments.md) — security-first Python architecture

> PyFundaments is not perfect. But it's more secure than most of what runs in production today!

---

## Foundation

- [PyFundaments](PyFundaments.md) — Security-first Python boilerplate
- [PyFundaments Function Overview](Fundaments-–-Function---Overview.md)
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- [SECURITY.md](SECURITY.md)

---

## History

[ShellMaster](https://github.com/VolkanSah/ChatGPT-ShellMaster) (2023, archived, MIT) was the precursor — a browser-accessible shell for ChatGPT with session memory via `/tmp/shellmaster_brain.log`, built before MCP was a word. Universal MCP Hub is its natural evolution.

---

## License

Dual-licensed:

- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [Ethical Security Operations License v1.1 (ESOL)](ESOL) — mandatory, non-severable

By using this software you agree to all ethical constraints defined in ESOL v1.1. Misuse may result in automatic license termination and legal liability.

---

*Architecture, security decisions, and PyFundaments by Volkan Kücükbudak. Built with Claude (Anthropic) as a typing assistant for docs & some bugs*

> crafted with passion by Volkan Kücükbudak - just want to feel how it works, mean i do not need it, have cli 😄
