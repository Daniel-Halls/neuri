"""Harness adapter subsystem for Neuri.

Provides vendor-agnostic abstract base classes and concrete CLI drivers for
Google Antigravity, OpenAI Codex CLI, OpenCode, OpenClaw, and local Ollama.
"""

from neuri.adapters.antigravity import AntigravityAdapter
from neuri.adapters.base import BaseHarnessAdapter, HarnessExecutionError
from neuri.adapters.codex import CodexAdapter
from neuri.adapters.ollama_local import OllamaLocalAdapter
from neuri.adapters.openclaw import OpenClawAdapter
from neuri.adapters.opencode import OpenCodeAdapter
from neuri.adapters.registry import AdapterNotFoundError, AdapterRegistry

__all__: list[str] = [
    "AdapterNotFoundError",
    "AdapterRegistry",
    "AntigravityAdapter",
    "BaseHarnessAdapter",
    "CodexAdapter",
    "HarnessExecutionError",
    "OllamaLocalAdapter",
    "OpenClawAdapter",
    "OpenCodeAdapter",
]
