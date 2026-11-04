"""Runtime introspection utilities for Neuri GUI.

Dynamically discovers registered slash commands, harness adapters, available
AI models, and Pydantic schemas so that the GUI stays 100% compatible with
future codebase modifications without requiring frontend changes.
"""

import contextlib
import inspect
from typing import Any

from neuri.adapters.registry import AdapterRegistry
from neuri.core.config import NeuriConfig
from neuri.core.schemas import (
    NeuriTaskEnvelope,
    NiiVueLayerSpec,
    NiiVueSceneSpec,
    RemoteArtifact,
    TaskEdge,
    TaskNode,
)
from neuri.core.session import NeuriSessionEngine
from neuri.core.slash_commands import SlashCommandRouter


class NeuriIntrospector:
    """Introspects Neuri runtime components for dynamic GUI rendering.

    Parameters
    ------------
    None

    Returns
    --------
        NeuriIntrospector: NeuriIntrospector instance
            Constructed introspection utility.
    """

    def __init__(self) -> None:
        """Initialize introspector instance.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes introspector state.
        """

    def discover_slash_commands(
        self, router: SlashCommandRouter
    ) -> list[dict[str, Any]]:
        """Discover all registered slash commands and parameter metadata.

        Parameters
        ------------
        router: SlashCommandRouter
            Active slash command router instance.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of command definitions containing command name,
                description, and handler details.
        """
        from neuri.ui.terminal_chat import SlashAutocompletePopup

        base_commands: dict[str, str] = {
            cmd: desc for cmd, desc in SlashAutocompletePopup.SLASH_COMMANDS
        }

        # Introspect all _handle_* methods or callables on the router
        methods = inspect.getmembers(router, predicate=callable)
        discovered: dict[str, dict[str, Any]] = {}

        for name, method in methods:
            if not name.startswith("_handle_"):
                continue

            cmd_name: str = "/" + name[len("_handle_") :]
            doc: str = inspect.getdoc(method) or "Slash command handler."
            summary: str = doc.strip().split("\n")[0].strip()

            canonical_desc: str = base_commands.get(cmd_name, summary)
            discovered[cmd_name] = {
                "command": cmd_name,
                "description": canonical_desc,
                "method_name": name,
            }

        # Ensure all base commands are included even if aliased
        for cmd, desc in base_commands.items():
            if cmd not in discovered:
                discovered[cmd] = {
                    "command": cmd,
                    "description": desc,
                    "method_name": f"_handle_{cmd.lstrip('/')}",
                }

        results: list[dict[str, Any]] = sorted(
            discovered.values(), key=lambda c: c["command"]
        )
        return results

    def discover_harnesses_and_models(
        self, session_engine: NeuriSessionEngine
    ) -> dict[str, Any]:
        """Discover registered AI harnesses and active model configurations.

        Parameters
        ------------
        session_engine: NeuriSessionEngine
            Active session engine instance.

        Returns
        --------
            dict[str, Any]: dict object
                Mapping of active harness, model, and available harnesses/models.
        """
        registry: AdapterRegistry = AdapterRegistry()
        canonical_harnesses: list[str] = [
            "agy",
            "codex",
            "ollama",
            "openclaw",
            "opencode",
        ]

        active_harness: str = session_engine.harness
        active_model: str = session_engine.model or "default"

        models_by_harness: dict[str, list[str]] = {}
        for h_id in canonical_harnesses:
            models_by_harness[h_id] = registry.get_models_for_harness(h_id)

        info: dict[str, Any] = {
            "active_harness": active_harness,
            "active_model": active_model,
            "harnesses": canonical_harnesses,
            "models_by_harness": models_by_harness,
        }
        return info

    def export_pydantic_schemas(self) -> dict[str, Any]:
        """Export JSON schemas for core data models to drive GUI forms dynamically.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dict object
                Mapping of model names to Pydantic JSON schema definitions.
        """
        models_to_export: list[tuple[str, Any]] = [
            ("TaskNode", TaskNode),
            ("TaskEdge", TaskEdge),
            ("NeuriTaskEnvelope", NeuriTaskEnvelope),
            ("RemoteArtifact", RemoteArtifact),
            ("NiiVueSceneSpec", NiiVueSceneSpec),
            ("NiiVueLayerSpec", NiiVueLayerSpec),
            ("NeuriConfig", NeuriConfig),
        ]
        schemas: dict[str, Any] = {}
        for name, cls in models_to_export:
            with contextlib.suppress(Exception):
                schemas[name] = cls.model_json_schema()
        return schemas


__all__: list[str] = [
    "NeuriIntrospector",
]
