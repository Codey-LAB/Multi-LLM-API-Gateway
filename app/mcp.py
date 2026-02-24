# app/mcp.py
# MCP Hub - Part of PyFundaments Architecture
# Copyright 2025 - Volkan Kücükbudak
# Apache License V. 2 + ESOL 1.1
#
# WICHTIG: Diese Datei lebt ausschließlich in /app/ und wird NUR von main.py gestartet.
# Sie hat KEINEN direkten Zugriff auf Keys oder Fundaments - alles kommt vom Wächter.
# Direktstart wird blockiert.

import sys
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger('mcp_hub')

# ============================================================
# GUARD: Kein Direktstart - nur über main.py
# ============================================================
if __name__ == "__main__":
    print("ERROR: app/mcp.py darf nicht direkt gestartet werden.")
    print("Starte stattdessen: python main.py")
    sys.exit(1)


# ============================================================
# MCP Server Factory - bekommt fundaments vom Wächter
# ============================================================

def create_mcp_server(fundaments: Dict[str, Any]):
    """
    Erstellt und konfiguriert den MCP-Server basierend auf verfügbaren Services.
    Wird ausschließlich von main.py aufgerufen.
    
    Args:
        fundaments: Vom Wächter (main.py) initialisierte und validierte Services.
                    Tools werden nur registriert wenn der zugehörige Service vorhanden ist.
    
    Returns:
        Konfiguriertes FastMCP-Objekt, bereit zum Starten.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.critical("FastMCP nicht installiert: pip install fastmcp")
        raise

    config = fundaments["config"]
    
    mcp = FastMCP(
        name="PyFundaments MCP Hub",
        instructions=(
            "Universal MCP Hub basierend auf PyFundaments. "
            "Verfügbare Tools hängen von konfigurierten API-Keys ab. "
            "Alle Operationen laufen durch den PyFundaments Security Layer."
        )
    )

    # ============================================================
    # TOOL REGISTRATION - nur wenn Service/Key verfügbar
    # ============================================================

    _register_llm_tools(mcp, config, fundaments)
    _register_search_tools(mcp, config)
    _register_system_tools(mcp, config, fundaments)
    _register_db_tools(mcp, fundaments)

    # Log was aktiv ist
    logger.info("MCP Hub konfiguriert und bereit.")
    return mcp


# ============================================================
# LLM TOOLS
# ============================================================

def _register_llm_tools(mcp, config, fundaments):
    """Registriert LLM-Tools basierend auf verfügbaren API-Keys."""

    # --- Anthropic ---
    if config.has("ANTHROPIC_API_KEY"):
        import httpx

        @mcp.tool()
        async def anthropic_complete(
            prompt: str,
            model: str = "claude-haiku-4-5-20251001",
            max_tokens: int = 1024
        ) -> str:
            """
            Sendet einen Prompt an die Anthropic API.
            
            Args:
                prompt: Der Eingabe-Text
                model: Claude Modell (default: claude-haiku-4-5-20251001)
                max_tokens: Maximale Antwortlänge
            
            Returns:
                Antwort-Text von Claude
            """
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": config.get("ANTHROPIC_API_KEY"),
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()["content"][0]["text"]

        logger.info("Tool registriert: anthropic_complete")

    # --- OpenRouter ---
    if config.has("OPENROUTER_API_KEY"):
        import httpx

        @mcp.tool()
        async def openrouter_complete(
            prompt: str,
            model: str = "mistralai/mistral-7b-instruct",
            max_tokens: int = 1024
        ) -> str:
            """
            Sendet einen Prompt via OpenRouter (Zugang zu 100+ Modellen).
            
            Args:
                prompt: Der Eingabe-Text
                model: OpenRouter Modell-ID (z.B. 'openai/gpt-4o', 'google/gemini-flash-1.5')
                max_tokens: Maximale Antwortlänge
            
            Returns:
                Antwort-Text vom gewählten Modell
            """
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.get('OPENROUTER_API_KEY')}",
                        "HTTP-Referer": config.get("APP_URL", "https://huggingface.co"),
                        "content-type": "application/json"
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

        logger.info("Tool registriert: openrouter_complete")

    # --- HuggingFace Inference ---
    if config.has("HF_TOKEN"):
        import httpx

        @mcp.tool()
        async def hf_inference(
            prompt: str,
            model: str = "mistralai/Mistral-7B-Instruct-v0.3",
            max_tokens: int = 512
        ) -> str:
            """
            Sendet einen Prompt an HuggingFace Inference API.
            
            Args:
                prompt: Der Eingabe-Text
                model: HF Modell-ID (muss Inference API unterstützen)
                max_tokens: Maximale Antwortlänge
            
            Returns:
                Generierter Text
            """
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.get('HF_TOKEN')}",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=120.0
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

        logger.info("Tool registriert: hf_inference")


# ============================================================
# SEARCH TOOLS
# ============================================================

def _register_search_tools(mcp, config):
    """Registriert Such-Tools basierend auf verfügbaren Keys."""

    if config.has("BRAVE_API_KEY"):
        import httpx

        @mcp.tool()
        async def brave_search(query: str, count: int = 5) -> str:
            """
            Sucht im Web via Brave Search API.
            
            Args:
                query: Suchanfrage
                count: Anzahl Ergebnisse (max 20)
            
            Returns:
                Suchergebnisse als formatierten Text
            """
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"Accept": "application/json", "X-Subscription-Token": config.get("BRAVE_API_KEY")},
                    params={"q": query, "count": min(count, 20)},
                    timeout=30.0
                )
                response.raise_for_status()
                results = response.json().get("web", {}).get("results", [])
                
                if not results:
                    return "Keine Ergebnisse gefunden."
                
                output = []
                for i, r in enumerate(results, 1):
                    output.append(f"{i}. {r.get('title', 'Kein Titel')}\n   {r.get('url', '')}\n   {r.get('description', '')}")
                return "\n\n".join(output)

        logger.info("Tool registriert: brave_search")

    if config.has("TAVILY_API_KEY"):
        import httpx

        @mcp.tool()
        async def tavily_search(query: str, max_results: int = 5) -> str:
            """
            KI-optimierte Websuche via Tavily API.
            
            Args:
                query: Suchanfrage
                max_results: Anzahl Ergebnisse
            
            Returns:
                Suchergebnisse mit KI-Zusammenfassung
            """
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": config.get("TAVILY_API_KEY"),
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                parts = []
                if data.get("answer"):
                    parts.append(f"Zusammenfassung: {data['answer']}")
                for r in data.get("results", []):
                    parts.append(f"- {r['title']}\n  {r['url']}\n  {r.get('content', '')[:200]}...")
                return "\n\n".join(parts)

        logger.info("Tool registriert: tavily_search")


# ============================================================
# SYSTEM TOOLS (immer verfügbar)
# ============================================================

def _register_system_tools(mcp, config, fundaments):
    """Registriert System-Tools - immer aktiv."""

    @mcp.tool()
    def list_active_tools() -> Dict[str, Any]:
        """
        Listet alle aktiven Tools und verfügbaren Services auf.
        Nützlich um zu prüfen welche Funktionen verfügbar sind.
        
        Returns:
            Dictionary mit aktiven Services und deren Status
        """
        status = {}
        for service_name, service_obj in fundaments.items():
            status[service_name] = service_obj is not None
        
        keys_present = []
        for key in ["ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN", 
                    "BRAVE_API_KEY", "TAVILY_API_KEY", "DATABASE_URL"]:
            if config.has(key):
                keys_present.append(key)
        
        return {
            "fundaments_status": status,
            "configured_integrations": keys_present,
            "transport": os.getenv("MCP_TRANSPORT", "stdio")
        }

    logger.info("Tool registriert: list_active_tools")

    @mcp.tool()
    def health_check() -> Dict[str, str]:
        """
        Health-Check Endpoint für HuggingFace Spaces und Monitoring.
        
        Returns:
            Status-Dictionary
        """
        return {"status": "ok", "service": "PyFundaments MCP Hub"}

    logger.info("Tool registriert: health_check")


# ============================================================
# DATABASE TOOLS (nur wenn DB initialisiert)
# ============================================================

def _register_db_tools(mcp, fundaments):
    """Registriert DB-Tools nur wenn Datenbankverbindung vorhanden."""

    if fundaments.get("db") is None:
        logger.info("Keine DB verfügbar - DB-Tools werden nicht registriert.")
        return

    from fundaments.postgresql import execute_secured_query

    @mcp.tool()
    async def db_query(sql: str, *params) -> str:
        """
        Führt eine gesicherte SELECT-Query auf der Datenbank aus.
        Nur Lesezugriff - keine DDL oder DML Statements.
        
        Args:
            sql: SQL SELECT-Statement
        
        Returns:
            Abfrageergebnis als Text
        """
        # Sicherheits-Guard: nur SELECT erlaubt
        if not sql.strip().upper().startswith("SELECT"):
            return "Fehler: Nur SELECT-Statements sind erlaubt."
        
        try:
            result = await execute_secured_query(sql, fetch_method='fetch')
            if not result:
                return "Keine Ergebnisse."
            return str([dict(row) for row in result])
        except Exception as e:
            logger.error(f"DB Query Fehler: {e}")
            return f"Datenbankfehler: {str(e)}"

    logger.info("Tool registriert: db_query")


# ============================================================
# TRANSPORT STARTER - wird von main.py aufgerufen
# ============================================================

async def start_mcp(fundaments: Dict[str, Any]):
    """
    Startet den MCP-Server im konfigurierten Transport-Modus.
    Wird von main.py aufgerufen - nicht direkt.
    
    Transport-Modi:
        stdio: Für lokale Nutzung mit Claude Desktop
        sse:   Für HuggingFace Spaces / Remote-Hosting (PORT=7860)
    """
    mcp = create_mcp_server(fundaments)
    
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    
    if transport == "sse":
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "7860"))
        logger.info(f"MCP Hub startet via SSE auf {host}:{port}")
        mcp.run(transport="sse", host=host, port=port)
    else:
        logger.info("MCP Hub startet via stdio (lokal)")
        mcp.run(transport="stdio")
