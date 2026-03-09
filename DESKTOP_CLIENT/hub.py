# =============================================================================
# mcp_desktop.py
# Universal MCP Desktop Client
# Copyright 2026 - Volkan Kücükbudak
# Apache License V. 2 + ESOL 1.1
# Repo: https://github.com/VolkanSah/Universal-MCP-Hub-sandboxed
# =============================================================================
# USAGE:
#   pip install PySide6 httpx
#   python mcp_desktop.py
#
# CONNECT:
#   1. Enter HF Token (hf_...) in Settings tab
#   2. Enter Hub URL (https://your-space.hf.space) in Settings tab
#   3. Click Connect
#   4. Use Chat tab to talk to your Hub
# =============================================================================

import sys
import json
import asyncio
import httpx
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QTabWidget,
    QStatusBar, QComboBox, QSpinBox
)
from PySide6.QtCore import QThread, Signal, QObject

# =============================================================================
# Local config — saved to ~/.mcp_desktop.json
# Stores: HF token, Hub URL, default provider, default model, font size
# =============================================================================
CONFIG_PATH = Path.home() / ".mcp_desktop.json"

def load_config() -> dict:
    """Load local config from ~/.mcp_desktop.json. Returns defaults if not found."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {
        "hf_token":         "",
        "hub_url":          "",
        "default_provider": "",
        "default_model":    "",
        "font_size":        14,
    }

def save_config(cfg: dict) -> None:
    """Save current config to ~/.mcp_desktop.json."""
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass


# =============================================================================
# Async Worker — handles all HTTP communication with the Hub
# Runs coroutines in a separate thread so the GUI never freezes.
# All results are emitted as Qt Signals back to the main thread.
# =============================================================================
class AsyncWorker(QObject):
    # Signals — connect these in the main thread to handle results
    result  = Signal(str)   # LLM/search response text
    error   = Signal(str)   # error message
    log     = Signal(str)   # log entry
    tools   = Signal(dict)  # tools + models dict from Hub
    status  = Signal(str)   # connection status text

    def __init__(self, hub_url: str, hf_token: str):
        super().__init__()
        self.hub_url  = hub_url.rstrip("/")
        self.hf_token = hf_token
        # Authorization header for private HF Spaces
        self.headers  = {"Authorization": f"Bearer {hf_token}"}

    def _run(self, coro):
        """Run an async coroutine in a fresh event loop (thread-safe)."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Health Check — GET / → returns uptime + status
    # -------------------------------------------------------------------------
    def health_check(self):
        async def _do():
            try:
                async with httpx.AsyncClient() as client:
                    r    = await client.get(
                        f"{self.hub_url}/",
                        headers=self.headers,
                        timeout=10,
                    )
                    data = r.json()
                    self.status.emit(
                        f"● connected — uptime: {data.get('uptime_seconds', '?')}s"
                    )
                    self.log.emit(f"[health] {json.dumps(data)}")
            except Exception as e:
                self.status.emit("✗ disconnected")
                self.error.emit(f"Health check failed: {e}")
        self._run(_do())

    # -------------------------------------------------------------------------
    # Fetch Tools — POST /api → list_active_tools
    # Returns: active tools, active providers, available models
    # -------------------------------------------------------------------------
    def fetch_tools(self):
        async def _do():
            try:
                async with httpx.AsyncClient() as client:
                    r    = await client.post(
                        f"{self.hub_url}/api",
                        headers={**self.headers, "Content-Type": "application/json"},
                        json={"tool": "list_active_tools", "params": {}},
                        timeout=15,
                    )
                    data = r.json()
                    self.tools.emit(data)
                    self.log.emit(f"[tools] {json.dumps(data)}")
            except Exception as e:
                self.error.emit(f"Fetch tools failed: {e}")
        self._run(_do())

    # -------------------------------------------------------------------------
    # LLM Complete — POST /api → llm_complete
    # Sends prompt to Hub, Hub routes to configured LLM provider with fallback.
    # Response includes provider name: "[gemini] Hello!"
    # -------------------------------------------------------------------------
    def llm_complete(self, prompt: str, provider: str = None, model: str = None):
        async def _do():
            try:
                async with httpx.AsyncClient() as client:
                    r    = await client.post(
                        f"{self.hub_url}/api",
                        headers={**self.headers, "Content-Type": "application/json"},
                        json={
                            "tool":   "llm_complete",
                            "params": {
                                "prompt":     prompt,
                                "provider":   provider or "",
                                "model":      model or "",
                                "max_tokens": 1024,
                            },
                        },
                        timeout=60,
                    )
                    data     = r.json()
                    response = data.get("result", data.get("error", str(data)))
                    self.result.emit(response)
                    self.log.emit(f"[llm] prompt: {prompt[:60]}...")
            except Exception as e:
                self.error.emit(f"LLM call failed: {e}")
        self._run(_do())

    # -------------------------------------------------------------------------
    # Web Search — POST /api → web_search
    # -------------------------------------------------------------------------
    def web_search(self, query: str, provider: str = None):
        async def _do():
            try:
                async with httpx.AsyncClient() as client:
                    r    = await client.post(
                        f"{self.hub_url}/api",
                        headers={**self.headers, "Content-Type": "application/json"},
                        json={
                            "tool":   "web_search",
                            "params": {
                                "query":       query,
                                "provider":    provider or "",
                                "max_results": 5,
                            },
                        },
                        timeout=30,
                    )
                    data     = r.json()
                    response = data.get("result", data.get("error", str(data)))
                    self.result.emit(response)
                    self.log.emit(f"[search] query: {query}")
            except Exception as e:
                self.error.emit(f"Search failed: {e}")
        self._run(_do())


# =============================================================================
# Worker Thread — wraps a callable in a QThread
# Keeps the GUI responsive while the worker runs in background.
# =============================================================================
class WorkerThread(QThread):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        self.fn()


# =============================================================================
# Main Window — MCPDesktop
# Tabs: Connect | Chat | Tools | Settings | Logs
# =============================================================================
class MCPDesktop(QMainWindow):

    # GitHub dark theme — readable, professional, no bloat
    STYLE = """
        QMainWindow, QWidget {{
            background-color: #0d1117;
            color: #e6edf3;
            font-family: 'Consolas', monospace;
            font-size: {font_size}px;
        }}
        QTabWidget::pane {{
            border: 1px solid #21262d;
            background: #0d1117;
        }}
        QTabBar::tab {{
            background: #161b22;
            color: #8b949e;
            padding: 8px 20px;
            border: 1px solid #21262d;
            border-bottom: none;
        }}
        QTabBar::tab:selected {{
            background: #0d1117;
            color: #58a6ff;
            border-bottom: 2px solid #58a6ff;
        }}
        QTabBar::tab:hover {{ color: #e6edf3; }}
        QLineEdit {{
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 4px;
            padding: 6px 10px;
            color: #e6edf3;
        }}
        QLineEdit:focus {{ border-color: #58a6ff; }}
        QTextEdit {{
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 4px;
            padding: 8px;
            color: #e6edf3;
            font-family: 'Consolas', monospace;
        }}
        QPushButton {{
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: #30363d;
            border-color: #58a6ff;
            color: #58a6ff;
        }}
        QPushButton:pressed {{ background: #161b22; }}
        QPushButton#connect_btn {{
            background: #238636;
            border-color: #2ea043;
            color: #ffffff;
        }}
        QPushButton#connect_btn:hover {{ background: #2ea043; }}
        QPushButton#send_btn {{
            background: #1f6feb;
            border-color: #388bfd;
            color: #ffffff;
            min-width: 80px;
        }}
        QPushButton#send_btn:hover {{ background: #388bfd; }}
        QPushButton#save_btn {{
            background: #6e40c9;
            border-color: #8957e5;
            color: #ffffff;
        }}
        QPushButton#save_btn:hover {{ background: #8957e5; }}
        QComboBox {{
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 4px;
            padding: 6px 10px;
            color: #e6edf3;
        }}
        QComboBox QAbstractItemView {{
            background: #161b22;
            border: 1px solid #30363d;
            color: #e6edf3;
            selection-background-color: #21262d;
        }}
        QSpinBox {{
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 4px;
            padding: 4px 8px;
            color: #e6edf3;
        }}
        QStatusBar {{
            background: #161b22;
            color: #8b949e;
            border-top: 1px solid #21262d;
            font-size: 12px;
        }}
    """

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self._thread = None  # keep thread reference alive

        self.setWindowTitle("Universal MCP Desktop")
        self.setMinimumSize(960, 700)
        self._apply_style()
        self._build_ui()
        self._set_status("✗ not connected")

    def _apply_style(self):
        """Apply stylesheet with current font size from config."""
        self.setStyleSheet(
            self.STYLE.format(font_size=self.cfg.get("font_size", 14))
        )

    # =========================================================================
    # UI Construction
    # =========================================================================
    def _build_ui(self):
        central = QWidget()
        layout  = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar — title + connection status
        layout.addWidget(self._build_header())

        # Tab widget — main UI
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_chat(),     "💬 Chat")
        self.tabs.addTab(self._tab_tools(),    "🛠 Tools")
        self.tabs.addTab(self._tab_settings(), "⚙ Settings")
        self.tabs.addTab(self._tab_logs(),     "📋 Logs")
        layout.addWidget(self.tabs)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_header(self) -> QWidget:
        """Top header bar with title and live connection status."""
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background: #161b22; border-bottom: 1px solid #21262d;")
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 0, 16, 0)

        title = QLabel("⬡ Universal MCP Desktop")
        title.setStyleSheet("color: #58a6ff; font-size: 15px; font-weight: bold;")
        row.addWidget(title)
        row.addStretch()

        self.status_label = QLabel("✗ not connected")
        self.status_label.setStyleSheet("color: #f85149; font-size: 12px;")
        row.addWidget(self.status_label)

        return header

    # =========================================================================
    # Tab: Chat
    # Send prompts to Hub → LLM provider with fallback chain
    # Provider + model can be overridden per message
    # =========================================================================
    def _tab_chat(self) -> QWidget:
        tab    = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Provider + model selector row
        selector_row = QHBoxLayout()

        selector_row.addWidget(QLabel("Provider:"))
        self.provider_select = QComboBox()
        self.provider_select.addItem("default (from .pyfun)")
        self.provider_select.setMinimumWidth(180)
        selector_row.addWidget(self.provider_select)

        selector_row.addWidget(QLabel("  Model:"))
        self.model_select = QComboBox()
        self.model_select.addItem("default (from .pyfun)")
        self.model_select.setMinimumWidth(220)
        selector_row.addWidget(self.model_select)

        selector_row.addStretch()

        # Health check button in chat tab for convenience
        health_btn = QPushButton("❤ Ping")
        health_btn.clicked.connect(self._health_check)
        selector_row.addWidget(health_btn)
        layout.addLayout(selector_row)

        # Chat output — read only, shows conversation history
        self.chat_output = QTextEdit()
        self.chat_output.setReadOnly(True)
        self.chat_output.setPlaceholderText(
            "Connect in Settings tab first, then type a prompt below..."
        )
        layout.addWidget(self.chat_output)

        # Input row — prompt + send button
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Enter prompt and press Enter...")
        self.chat_input.returnPressed.connect(self._send_chat)
        input_row.addWidget(self.chat_input)

        send_btn = QPushButton("Send ▶")
        send_btn.setObjectName("send_btn")
        send_btn.clicked.connect(self._send_chat)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

        return tab

    # =========================================================================
    # Tab: Tools
    # Shows all active tools and providers loaded from Hub via list_active_tools
    # =========================================================================
    def _tab_tools(self) -> QWidget:
        tab    = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("↻ Refresh Tools")
        refresh_btn.clicked.connect(self._fetch_tools)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Shows raw JSON from Hub — tools, providers, models
        self.tools_output = QTextEdit()
        self.tools_output.setReadOnly(True)
        self.tools_output.setPlaceholderText(
            "Click 'Refresh Tools' to load active tools from Hub..."
        )
        layout.addWidget(self.tools_output)

        return tab

    # =========================================================================
    # Tab: Settings
    # HF Token, Hub URL, default provider/model, font size
    # All saved to ~/.mcp_desktop.json on "Save & Connect"
    # =========================================================================
    def _tab_settings(self) -> QWidget:
        tab    = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # HuggingFace Token — required for private Spaces
        layout.addWidget(self._section("HuggingFace Token (required for private Spaces)"))
        self.token_input = QLineEdit(self.cfg.get("hf_token", ""))
        self.token_input.setPlaceholderText("hf_...")
        self.token_input.setEchoMode(QLineEdit.Password)  # hide token
        layout.addWidget(self.token_input)

        # Hub URL — your HF Space URL
        layout.addWidget(self._section("Hub URL"))
        self.url_input = QLineEdit(self.cfg.get("hub_url", ""))
        self.url_input.setPlaceholderText("https://your-space-name.hf.space")
        layout.addWidget(self.url_input)

        # Default provider override — optional, Hub uses .pyfun default if empty
        layout.addWidget(self._section("Default Provider (optional — overrides .pyfun)"))
        self.default_provider_input = QLineEdit(self.cfg.get("default_provider", ""))
        self.default_provider_input.setPlaceholderText(
            "e.g. gemini, anthropic, huggingface — leave empty for Hub default"
        )
        layout.addWidget(self.default_provider_input)

        # Default model override — optional
        layout.addWidget(self._section("Default Model (optional — overrides .pyfun)"))
        self.default_model_input = QLineEdit(self.cfg.get("default_model", ""))
        self.default_model_input.setPlaceholderText(
            "e.g. gemini-3.0 — leave empty for Hub default"
        )
        layout.addWidget(self.default_model_input)

        # Font size — applies immediately after save
        layout.addWidget(self._section("Font Size"))
        font_row = QHBoxLayout()
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(10, 24)
        self.font_size_input.setValue(self.cfg.get("font_size", 14))
        font_row.addWidget(self.font_size_input)
        font_row.addStretch()
        layout.addLayout(font_row)

        layout.addStretch()

        # Save & Connect button
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save & Connect")
        save_btn.setObjectName("save_btn")
        save_btn.clicked.connect(self._save_and_connect)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Info text
        info = QTextEdit()
        info.setReadOnly(True)
        info.setMaximumHeight(80)
        info.setPlainText(
            "Settings are saved locally in ~/.mcp_desktop.json  |  "
            "Token is never sent to anyone except your own Hub."
        )
        info.setStyleSheet(
            "color: #8b949e; background: #0d1117; border: none; font-size: 12px;"
        )
        layout.addWidget(info)

        return tab

    # =========================================================================
    # Tab: Logs
    # All HTTP requests, responses, errors — timestamped
    # =========================================================================
    def _tab_logs(self) -> QWidget:
        tab    = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("🗑 Clear Logs")
        clear_btn.clicked.connect(lambda: self.log_output.clear())
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("All requests and responses appear here...")
        layout.addWidget(self.log_output)

        return tab

    # =========================================================================
    # Helper Widgets
    # =========================================================================
    def _section(self, text: str) -> QLabel:
        """Section label — uppercase, muted color."""
        label = QLabel(text)
        label.setStyleSheet("color: #8b949e; font-size: 11px; margin-top: 8px;")
        return label

    # =========================================================================
    # Status + Log helpers
    # =========================================================================
    def _set_status(self, text: str):
        """Update header status label + status bar. Green if connected, red if not."""
        self.status_label.setText(text)
        self.status_bar.showMessage(text)
        connected = "connected" in text and "not" not in text
        color = "#3fb950" if connected else "#f85149"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _log(self, msg: str):
        """Append timestamped log entry to Logs tab."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{ts}] {msg}")

    def _make_worker(self) -> AsyncWorker:
        """Create AsyncWorker with current Hub URL + HF Token from config."""
        return AsyncWorker(
            hub_url=self.cfg.get("hub_url", ""),
            hf_token=self.cfg.get("hf_token", ""),
        )

    def _run_in_thread(self, fn):
        """Run a function in a background QThread. Keeps GUI responsive."""
        t = WorkerThread(fn)
        t.start()
        self._thread = t  # prevent garbage collection

    # =========================================================================
    # Actions
    # =========================================================================
    def _save_and_connect(self):
        """Save settings to config file and run health check to verify connection."""
        self.cfg["hf_token"]         = self.token_input.text().strip()
        self.cfg["hub_url"]          = self.url_input.text().strip()
        self.cfg["default_provider"] = self.default_provider_input.text().strip()
        self.cfg["default_model"]    = self.default_model_input.text().strip()
        self.cfg["font_size"]        = self.font_size_input.value()
        save_config(self.cfg)

        # Apply new font size immediately
        self._apply_style()

        if not self.cfg["hf_token"] or not self.cfg["hub_url"]:
            self._set_status("✗ token and URL required!")
            return

        self._set_status("… connecting")
        self._log(f"Connecting to {self.cfg['hub_url']}...")

        w = self._make_worker()
        w.status.connect(self._set_status)
        w.error.connect(lambda e: self._log(f"ERROR: {e}"))
        w.log.connect(self._log)
        self._run_in_thread(w.health_check)

    def _health_check(self):
        """Ping Hub health endpoint — updates connection status."""
        w = self._make_worker()
        w.status.connect(self._set_status)
        w.error.connect(lambda e: self._log(f"ERROR: {e}"))
        w.log.connect(self._log)
        self._run_in_thread(w.health_check)

    def _fetch_tools(self):
        """Fetch active tools + providers + models from Hub via list_active_tools."""
        w = self._make_worker()
        w.tools.connect(self._on_tools)
        w.error.connect(lambda e: self._log(f"ERROR: {e}"))
        w.log.connect(self._log)
        self._run_in_thread(w.fetch_tools)

    def _on_tools(self, data: dict):
        """Handle tools response — populate provider + model dropdowns."""
        # Show raw JSON in Tools tab
        result = data.get("result", data)
        if isinstance(result, list):
            # Simple list response from /api list_active_tools fix
            self.tools_output.setPlainText(json.dumps({"active_tools": result}, indent=2))
        else:
            self.tools_output.setPlainText(json.dumps(result, indent=2))

        # Populate provider dropdown
        providers = result.get("active_llm_providers", []) if isinstance(result, dict) else []
        self.provider_select.clear()
        self.provider_select.addItem("default (from .pyfun)")
        for p in providers:
            self.provider_select.addItem(p)

        # Populate model dropdown
        models = result.get("available_models", []) if isinstance(result, dict) else []
        self.model_select.clear()
        self.model_select.addItem("default (from .pyfun)")
        for m in models:
            self.model_select.addItem(m)

        self._log(f"Tools loaded: {result}")

    def _send_chat(self):
        """Send prompt to Hub via llm_complete. Uses selected provider + model."""
        prompt = self.chat_input.text().strip()
        if not prompt:
            return

        # Get provider override — None = use Hub default from .pyfun
        provider = self.provider_select.currentText()
        if "default" in provider:
            provider = self.cfg.get("default_provider") or None

        # Get model override — None = use Hub default from .pyfun
        model = self.model_select.currentText()
        if "default" in model:
            model = self.cfg.get("default_model") or None

        self.chat_output.append(f"\n▶ You: {prompt}")
        self.chat_input.clear()
        self._log(f"Sending to Hub — provider: {provider or 'default'}, model: {model or 'default'}")

        w = self._make_worker()
        # Response includes provider name: "[gemini] Hello!"
        w.result.connect(lambda r: self.chat_output.append(f"⬡ Hub: {r}\n"))
        w.error.connect(lambda e: self.chat_output.append(f"✗ Error: {e}\n"))
        w.log.connect(self._log)
        self._run_in_thread(lambda: w.llm_complete(prompt, provider, model))


# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    # Windows event loop fix — prevents RuntimeError on Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app    = QApplication(sys.argv)
    window = MCPDesktop()
    window.show()
    sys.exit(app.exec())
