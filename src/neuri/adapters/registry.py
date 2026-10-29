"""Central adapter registry and factory for agent harness dispatchers.

Provides discovery, resolution, and registration of external agent harness
adapters (Antigravity, Codex, OpenCode, OpenClaw, Ollama).
"""

from typing import Any

from neuri.adapters.antigravity import AntigravityAdapter
from neuri.adapters.base import BaseHarnessAdapter
from neuri.adapters.codex import CodexAdapter
from neuri.adapters.ollama_local import OllamaLocalAdapter
from neuri.adapters.openclaw import OpenClawAdapter
from neuri.adapters.opencode import OpenCodeAdapter


class AdapterNotFoundError(Exception):
    """Exception raised when an unknown or unregistered harness ID is requested.

    Parameters
    ------------
    harness_id: str
        Target harness identifier that was not found.

    Returns
    --------
        AdapterNotFoundError: AdapterNotFoundError instance
            Constructed exception object.
    """

    def __init__(self, harness_id: str) -> None:
        """Initialize adapter not found error.

        Parameters
        ------------
        harness_id: str
            Identifier of missing harness.

        Returns
        --------
            None: NoneType object
                Initializes exception attributes.
        """
        super().__init__(
            f"No harness adapter registered for identifier: '{harness_id}'. "
            f"Available harnesses: agy, codex, opencode, openclaw, ollama_local."
        )
        self.harness_id: str = harness_id


class AdapterRegistry:
    """Registry maintaining initialized BaseHarnessAdapter instances by ID.

    Encapsulates standard adapters for Tier-1 and Tier-2 harnesses without
    module-level global state.

    Parameters
    ------------
    custom_adapters: dict[str, BaseHarnessAdapter] | None
        Optional dictionary of custom adapter instances. Defaults to None.

    Returns
    --------
        AdapterRegistry: AdapterRegistry instance
            Constructed adapter registry.
    """

    def __init__(
        self, custom_adapters: dict[str, BaseHarnessAdapter] | None = None
    ) -> None:
        """Initialize adapter registry with built-in harness drivers.

        Parameters
        ------------
        custom_adapters: dict[str, BaseHarnessAdapter] | None
            Custom adapters to register. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes internal adapters mapping.
        """
        self._adapters: dict[str, BaseHarnessAdapter] = {}
        self._register_defaults()

        if custom_adapters is not None:
            for h_id, adapter in custom_adapters.items():
                self.register_adapter(h_id, adapter)

    def _register_defaults(self) -> None:
        """Register default Tier-1 and Tier-2 harness adapters.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Populates default adapters.
        """
        agy: AntigravityAdapter = AntigravityAdapter()
        codex: CodexAdapter = CodexAdapter()
        opencode: OpenCodeAdapter = OpenCodeAdapter()
        openclaw: OpenClawAdapter = OpenClawAdapter()
        ollama: OllamaLocalAdapter = OllamaLocalAdapter()

        self._adapters["agy"] = agy
        self._adapters["antigravity"] = agy
        self._adapters["codex"] = codex
        self._adapters["opencode"] = opencode
        self._adapters["openclaw"] = openclaw
        self._adapters["ollama"] = ollama
        self._adapters["ollama_local"] = ollama

    def get_adapter(self, harness_id: str) -> BaseHarnessAdapter:
        """Retrieve registered adapter for a given harness identifier.

        Parameters
        ------------
        harness_id: str
            Target harness ID (e.g. 'agy', 'codex', 'ollama').

        Returns
        --------
            BaseHarnessAdapter: BaseHarnessAdapter instance
                Matching adapter instance.
        """
        key: str = harness_id.strip().lower()
        if key not in self._adapters:
            raise AdapterNotFoundError(harness_id)
        adapter: BaseHarnessAdapter = self._adapters[key]
        return adapter

    def register_adapter(
        self, harness_id: str, adapter: BaseHarnessAdapter
    ) -> None:
        """Register or override an adapter for a given harness identifier.

        Parameters
        ------------
        harness_id: str
            Target harness ID.
        adapter: BaseHarnessAdapter
            Adapter instance implementing BaseHarnessAdapter.

        Returns
        --------
            None: NoneType object
                Updates internal registry mapping.
        """
        key: str = harness_id.strip().lower()
        self._adapters[key] = adapter

    def list_available(self) -> list[str]:
        """List distinct available harness IDs whose CLI binaries are on PATH.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Sorted list of unique canonical available harness IDs.
        """
        canonical_ids: set[str] = set()
        for adapter in self._adapters.values():
            if adapter.is_available():
                canonical_ids.add(adapter.harness_id)
        available_sorted: list[str] = sorted(canonical_ids)
        return available_sorted

    def list_all(self) -> list[str]:
        """List all registered harness identifiers regardless of availability.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Sorted list of all registered harness IDs.
        """
        all_ids: list[str] = sorted(set(self._adapters.keys()))
        return all_ids

    def get_models_for_harness(self, harness_id: str) -> list[str]:
        """Query real model list directly from the target harness binary.

        Parameters
        ------------
        harness_id: str
            Target harness ID (e.g. 'agy', 'ollama').

        Returns
        --------
            list[str]: list object
                Models returned directly from the harness binary.
        """
        adapter: BaseHarnessAdapter = self.get_adapter(harness_id)
        models: list[str] = adapter.list_available_models()
        return models

    def list_all_models(self) -> dict[str, list[str]]:
        """Query real model lists across all available harnesses on system.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, list[str]]: dictionary object
                Mapping of harness ID to live models reported by binary.
        """
        result: dict[str, list[str]] = {}
        for h_id in self.list_available():
            adapter: BaseHarnessAdapter = self._adapters[h_id]
            models: list[str] = adapter.list_available_models()
            if models:
                result[h_id] = models
        return result


__all__: list[str] = [
    "AdapterNotFoundError",
    "AdapterRegistry",
]
