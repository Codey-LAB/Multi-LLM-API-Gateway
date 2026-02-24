---
title: Universal MCP Hub
emoji: 🔐
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Universal MCP Hub 
> for advanced use have a loock on PyFundaments_README.md and docs/ folder

Universal MCP-Server (paranoid mode enabled) under ESOL!

## Setup

1. **Fork** this Space.
2. Enter your API keys as **Space Secrets** (Settings → Variables and secrets).
3. The Space will start automatically.

## Available Tools (Depending on Configured Keys)

| Secret | Tool | Description |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | `anthropic_complete` | Claude Models |
| `OPENROUTER_API_KEY` | `openrouter_complete` | 100+ Models via OpenRouter |
| `HF_TOKEN` | `hf_inference` | HuggingFace Inference API |
| `BRAVE_API_KEY` | `brave_search` | Web Search |
| `TAVILY_API_KEY` | `tavily_search` | AI-optimized Search |
| *(Always Active)* | `list_active_tools` | Shows all currently active tools |
| *(Always Active)* | `health_check` | System health check |

## MCP Client Configuration (SSE)

To connect your local Claude Desktop or any MCP client to this hub, use the following configuration:

```json
{
  "mcpServers": {
    "pyfundaments-hub": {
      "url": "https://YOUR_USERNAME-pyfundaments-mcp-hub.hf.space/sse"
    }
  }
}
