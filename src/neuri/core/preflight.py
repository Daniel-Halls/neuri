"""Zero-token deterministic pre-flight validator for Neuri task envelopes.

Enforces zero Protected Health Information (PHI) leakage, coordinate space
compatibility, artifact POSIX existence, and skill catalog registration
before any harness subprocess is spawned.
"""

from collections.abc import Sequence
from pathlib import Path
import shutil
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
import yaml

from neuri.core.paths import PathResolver
from neuri.core.schemas import NeuriTaskEnvelope, RemoteArtifact


class PreflightValidationError(Exception):
    """Exception raised when a task envelope fails pre-flight validation.

    Parameters
    ------------
    message: str
        Explanatory error message detailing pre-flight failure.
    errors: Sequence[str] | None
        List of specific validation failure reasons. Defaults to None.

    Returns
    --------
        PreflightValidationError: PreflightValidationError instance
            Constructed exception object.
    """

    def __init__(
        self, message: str, errors: Sequence[str] | None = None
    ) -> None:
        """Initialize pre-flight validation error with failure causes.

        Parameters
        ------------
        message: str
            Primary descriptive message.
        errors: Sequence[str] | None
            Granular list of validation failures. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes error attributes.
        """
        super().__init__(message)
        self.message: str = message
        err_list: list[str] = list(errors) if errors is not None else [message]
        self.errors: list[str] = err_list


class PreflightCheckResult(BaseModel):
    """Result container summarizing pre-flight validation checks.

    Parameters
    ------------
    passed: bool
        Whether all mandatory pre-flight checks succeeded.
    errors: list[str]
        List of critical failure messages that block execution.
    warnings: list[str]
        List of non-blocking advisory warnings.

    Returns
    --------
        PreflightCheckResult: PreflightCheckResult instance
            Validated pre-flight check result.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PreflightValidator:
    """Deterministic, zero-token validator for Neuri task envelopes.

    Inspects task envelopes prior to dispatch to guarantee:
    1. Zero Protected Health Information (PHI) in header summaries.
    2. Coordinate space compatibility across input artifacts.
    3. Input artifact existence on local or accessible filesystems.
    4. Valid skill pack registrations in catalog.
    5. Harness executable availability on host.

    Parameters
    ------------
    catalog_path: Path | None
        Optional path to skills/index.yaml catalog. Defaults to None.
    workspace_dir: Path | None
        Optional workspace root directory. Defaults to None.

    Returns
    --------
        PreflightValidator: PreflightValidator instance
            Constructed pre-flight validator.
    """

    STANDARD_SPACES: set[str] = {
        "mni152nlin2009casym",
        "mni152nlin6asym",
        "mni305",
        "fsaverage",
        "fsaverage5",
        "fsaverage6",
        "fs_lr",
        "colin27",
        "native",
        "t1w",
        "t2w",
        "bold",
        "dwi",
        "subject",
    }

    def __init__(
        self,
        catalog_path: Path | None = None,
        workspace_dir: Path | None = None,
    ) -> None:
        """Initialize validator with optional catalog and workspace paths.

        Parameters
        ------------
        catalog_path: Path | None
            Path to skills/index.yaml. Defaults to None.
        workspace_dir: Path | None
            Workspace directory. Defaults to None.

        Returns
        --------
        None: NoneType object
            Initializes catalog and workspace path attributes.
        """
        self._catalog_path: Path | None = catalog_path
        self._workspace_dir: Path | None = workspace_dir
        self._known_skills: set[str] = self._load_known_skills()

    def _load_known_skills(self) -> set[str]:
        """Load known skill IDs from skills/index.yaml and workspace skills.

        Parameters
        ------------
        None

        Returns
        --------
            set[str]: set object
                Set of known skill identifiers.
        """
        skills: set[str] = set()

        # Check explicit catalog path
        if self._catalog_path and self._catalog_path.is_file():
            try:
                content: str = self._catalog_path.read_text(encoding="utf-8")
                data: dict[str, Any] = yaml.safe_load(content) or {}
                for item in data.get("skills", []):
                    if isinstance(item, dict) and "id" in item:
                        skills.add(str(item["id"]))
                        for alias in item.get("aliases", []):
                            skills.add(str(alias))
            except Exception:
                pass

        # Check default project path via PathResolver
        default_idx: Path = PathResolver.get_default_skills_index()
        if default_idx.is_file() and default_idx != self._catalog_path:
            try:
                content = default_idx.read_text(encoding="utf-8")
                data = yaml.safe_load(content) or {}
                for item in data.get("skills", []):
                    if isinstance(item, dict) and "id" in item:
                        skills.add(str(item["id"]))
                        for alias in item.get("aliases", []):
                            skills.add(str(alias))
            except Exception:
                pass

        # Check custom workspace skills directory
        if self._workspace_dir:
            ws_skills: Path = self._workspace_dir / ".neuri" / "skills"
            if ws_skills.is_dir():
                for sub in ws_skills.iterdir():
                    if sub.is_dir():
                        skills.add(sub.name)

        return skills

    def validate_envelope(
        self, envelope: NeuriTaskEnvelope, check_harness: bool = False
    ) -> PreflightCheckResult:
        """Perform comprehensive deterministic validation on a task envelope.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            The task envelope to validate.
        check_harness: bool
            Whether to verify harness CLI is installed on PATH.
            Defaults to False.

        Returns
        --------
            PreflightCheckResult: PreflightCheckResult instance
                Summary of validation pass/fail with errors and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Enforce zero PHI on all input artifacts
        phi_errors: list[str] = self._validate_phi(envelope.input_artifacts)
        errors.extend(phi_errors)

        # 2. Check coordinate space compatibility
        space_errors, space_warnings = self._validate_spaces(
            envelope.input_artifacts
        )
        errors.extend(space_errors)
        warnings.extend(space_warnings)

        # 3. Check artifact file existence for local artifacts
        artifact_errors: list[str] = self._validate_artifact_paths(
            envelope.input_artifacts
        )
        errors.extend(artifact_errors)

        # 4. Check registered skill paths
        skill_errors: list[str] = self._validate_skills(envelope.skill_paths)
        errors.extend(skill_errors)

        # 5. Optionally verify harness availability
        if check_harness:
            harness_err: str | None = self._validate_harness(
                envelope.harness_id
            )
            if harness_err:
                errors.append(harness_err)

        passed_status: bool = len(errors) == 0
        result: PreflightCheckResult = PreflightCheckResult(
            passed=passed_status,
            errors=errors,
            warnings=warnings,
        )
        return result

    def verify_or_raise(
        self, envelope: NeuriTaskEnvelope, check_harness: bool = False
    ) -> None:
        """Validate envelope and raise PreflightValidationError on failure.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            The task envelope to validate.
        check_harness: bool
            Whether to verify harness CLI is on PATH. Defaults to False.

        Returns
        --------
            None: NoneType object
                Completes cleanly if validation passes.
        """
        result: PreflightCheckResult = self.validate_envelope(
            envelope, check_harness=check_harness
        )
        if not result.passed:
            err_msg: str = (
                f"Pre-flight validation failed for node '{envelope.node_id}': "
                + "; ".join(result.errors)
            )
            raise PreflightValidationError(err_msg, errors=result.errors)

    def _validate_phi(self, artifacts: Sequence[RemoteArtifact]) -> list[str]:
        """Verify that every artifact header has phi_sanitized=True.

        Parameters
        ------------
        artifacts: Sequence[RemoteArtifact]
            Input artifacts to inspect.

        Returns
        --------
            list[str]: list object
                List of PHI validation error messages.
        """
        errors: list[str] = []
        for art in artifacts:
            if not art.header_summary.phi_sanitized:
                msg: str = (
                    f"Artifact '{art.artifact_id}' ({art.posix_path}) has "
                    f"phi_sanitized=False. All data entering LLM context must "
                    f"be PHI sanitized."
                )
                errors.append(msg)
        return errors

    def _validate_spaces(
        self, artifacts: Sequence[RemoteArtifact]
    ) -> tuple[list[str], list[str]]:
        """Verify coordinate space consistency among input artifacts.

        Parameters
        ------------
        artifacts: Sequence[RemoteArtifact]
            Input artifacts to inspect.

        Returns
        --------
            tuple[list[str], list[str]]: tuple object
                Tuple of (errors, warnings) strings.
        """
        errors: list[str] = []
        warnings: list[str] = []
        spaces_observed: set[str] = set()

        for art in artifacts:
            if art.space:
                norm_space: str = art.space.strip().lower()
                spaces_observed.add(norm_space)
                if norm_space not in self.STANDARD_SPACES:
                    warnings.append(
                        f"Artifact '{art.artifact_id}' references non-standard "
                        f"coordinate space '{art.space}'."
                    )

        # If multiple distinct standard spaces are mixed without transform
        standard_spatial: set[str] = {
            s for s in spaces_observed if s.startswith("mni") or s.startswith("fs")
        }
        native_spatial: set[str] = {
            s for s in spaces_observed if s in ("native", "t1w", "bold", "subject")
        }

        if len(standard_spatial) > 1:
            errors.append(
                f"Multiple conflicting standard spaces detected among inputs: "
                f"{sorted(standard_spatial)}. Explicit spatial normalization "
                f"or transformation step is required."
            )

        if standard_spatial and native_spatial:
            warnings.append(
                f"Input artifacts mix standard space ({sorted(standard_spatial)}) "
                f"with native space ({sorted(native_spatial)}). Verify that "
                f"coregistration is intended."
            )

        res: tuple[list[str], list[str]] = (errors, warnings)
        return res

    def _validate_artifact_paths(
        self, artifacts: Sequence[RemoteArtifact]
    ) -> list[str]:
        """Check filesystem existence for localhost artifacts.

        Parameters
        ------------
        artifacts: Sequence[RemoteArtifact]
            Input artifacts to inspect.

        Returns
        --------
            list[str]: list object
                List of path validation error messages.
        """
        errors: list[str] = []
        for art in artifacts:
            if art.host in ("localhost", "local", "127.0.0.1"):
                p: Path = Path(art.posix_path)
                if not p.exists():
                    errors.append(
                        f"Local artifact file not found at POSIX path: "
                        f"'{art.posix_path}' (id: '{art.artifact_id}')"
                    )
        return errors

    def _validate_skills(self, skill_paths: Sequence[str]) -> list[str]:
        """Verify that referenced skill IDs or paths exist.

        Parameters
        ------------
        skill_paths: Sequence[str]
            Skill path strings or IDs.

        Returns
        --------
            list[str]: list object
                List of skill validation error messages.
        """
        errors: list[str] = []
        if not self._known_skills:
            return errors

        for skill in skill_paths:
            # Could be a skill ID or a directory path
            skill_name: str = Path(skill).name
            if (
                skill not in self._known_skills
                and skill_name not in self._known_skills
                and not Path(skill).is_dir()
            ):
                errors.append(
                    f"Referenced skill '{skill}' is not registered in the "
                    f"neuroscience skills catalog or workspace skills."
                )
        return errors

    def _validate_harness(self, harness_id: str) -> str | None:
        """Check if target harness binary exists on PATH.

        Parameters
        ------------
        harness_id: str
            Harness identifier ('agy', 'codex', 'ollama', etc.).

        Returns
        --------
            str | None: string or None
                Error message if harness binary is not installed, else None.
        """
        executable_map: dict[str, str] = {
            "agy": "agy",
            "antigravity": "agy",
            "codex": "codex",
            "opencode": "opencode",
            "openclaw": "openclaw",
            "ollama": "ollama",
            "ollama_local": "ollama",
        }
        cmd_name: str = executable_map.get(harness_id.lower(), harness_id)
        if shutil.which(cmd_name) is None:
            err: str = (
                f"Harness CLI executable '{cmd_name}' for harness '{harness_id}' "
                f"was not found on system PATH."
            )
            return err
        return None


__all__: list[str] = [
    "PreflightCheckResult",
    "PreflightValidationError",
    "PreflightValidator",
]
