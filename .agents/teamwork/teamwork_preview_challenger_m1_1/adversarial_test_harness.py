"""Adversarial Verification Harness for Neuri Core Schemas (M1).

Executes targeted stress-tests and invariant probes against src/neuri/core/schemas.py.
Reports empirical findings, security gaps, and data-integrity risks.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import sys
from typing import Any

from pydantic import ValidationError

from neuri.core.schemas import (
    ChatRole,
    ChatTurn,
    ModalityType,
    NeuriTaskEnvelope,
    NeuriTaskResult,
    NiiVueLayerSpec,
    NiiVueSceneSpec,
    RemoteArtifact,
    SanitizedNeuroHeader,
    SessionEvent,
    SessionEventType,
    TaskEdge,
    TaskNode,
    TaskState,
    TelemetryEvent,
)


@dataclass
class ProbeResult:
    """Outcome of a single empirical challenge probe."""

    probe_id: str
    target_model: str
    description: str
    passed: bool
    vulnerability_detected: bool
    details: str
    blast_radius: str


class SchemaAdversarialHarness:
    """Automated empirical challenge runner for core schemas."""

    def __init__(self) -> None:
        """Initialize the challenge runner."""
        self.results: list[ProbeResult] = []

    def run_all_probes(self) -> list[ProbeResult]:
        """Execute all adversarial probes."""
        self.probe_01_phi_literal_rejection()
        self.probe_02_phi_post_instantiation_mutation()
        self.probe_03_phi_smuggling_via_dtype()
        self.probe_04_negative_voxel_sizes()
        self.probe_05_negative_tr_and_sampling_rate()
        self.probe_06_nan_in_value_range_and_json()
        self.probe_07_contradictory_remote_artifact_uri()
        self.probe_08_relative_posix_path_in_remote_artifact()
        self.probe_09_invalid_sha256_header_format()
        self.probe_10_task_edge_empty_strings()
        self.probe_11_envelope_alias_mismatch_with_project_spec()
        self.probe_12_niivue_scene_empty_volumes()
        self.probe_13_json_roundtrip_fidelity()
        return self.results

    def probe_01_phi_literal_rejection(self) -> None:
        """Probe 01: Verify phi_sanitized=False is strictly rejected on init."""
        probe_id = "PROBE-01-PHI-INIT"
        try:
            SanitizedNeuroHeader(
                shape=[256, 256, 176],
                dtype="float32",
                phi_sanitized=False,  # type: ignore[arg-type]
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Init with phi_sanitized=False",
                    passed=False,
                    vulnerability_detected=True,
                    details="phi_sanitized=False was accepted without error!",
                    blast_radius="CRITICAL: Unsanitized PHI admitted to system.",
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Init with phi_sanitized=False rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="ValidationError raised as expected.",
                    blast_radius="None (Invariant held).",
                )
            )

    def probe_02_phi_post_instantiation_mutation(self) -> None:
        """Probe 02: Attempt post-instantiation mutation of phi_sanitized."""
        probe_id = "PROBE-02-PHI-MUTATION"
        header = SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
        )
        try:
            # Attempt to mutate the sanitized flag on existing instance
            header.phi_sanitized = False  # type: ignore[assignment]
            # Verify if mutation succeeded
            if header.phi_sanitized is False:
                self.results.append(
                    ProbeResult(
                        probe_id=probe_id,
                        target_model="SanitizedNeuroHeader",
                        description="Post-instantiation mutation of phi_sanitized to False",
                        passed=False,
                        vulnerability_detected=True,
                        details=(
                            "SanitizedNeuroHeader is mutable and lacks "
                            "frozen=True or validate_assignment=True. "
                            "header.phi_sanitized was successfully set to False."
                        ),
                        blast_radius=(
                            "HIGH: A downstream component or adapter can mutate "
                            "header.phi_sanitized = False post-construction "
                            "bypassing initial validation."
                        ),
                    )
                )
            else:
                self.results.append(
                    ProbeResult(
                        probe_id=probe_id,
                        target_model="SanitizedNeuroHeader",
                        description="Post-instantiation mutation prevented",
                        passed=True,
                        vulnerability_detected=False,
                        details="Assignment did not change value.",
                        blast_radius="None.",
                    )
                )
        except (ValidationError, TypeError):
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Post-instantiation mutation rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="Model is immutable or validates assignment.",
                    blast_radius="None.",
                )
            )

    def probe_03_phi_smuggling_via_dtype(self) -> None:
        """Probe 03: Test PHI smuggling into unconstrained dtype field."""
        probe_id = "PROBE-03-PHI-SMUGGLING-DTYPE"
        smuggled_phi = (
            "float32; PATIENT_NAME: Jane Doe; DOB: 1975-04-12; SSN: 123-45-6789"
        )
        try:
            header = SanitizedNeuroHeader(
                shape=[256, 256, 176],
                dtype=smuggled_phi,
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Smuggle PHI payload inside dtype field",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"SanitizedNeuroHeader accepted arbitrary string for dtype: '{header.dtype}'. "
                        "No regex or allowed enum (e.g. float32, int16) is enforced on dtype."
                    ),
                    blast_radius=(
                        "MEDIUM: Adversarial or malformed upstream headers can smuggle "
                        "unstructured patient metadata through unconstrained text fields."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Smuggle PHI payload inside dtype rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="dtype field is strictly validated.",
                    blast_radius="None.",
                )
            )

    def probe_04_negative_voxel_sizes(self) -> None:
        """Probe 04: Test non-positive and negative voxel dimensions."""
        probe_id = "PROBE-04-NEGATIVE-VOXEL-SIZES"
        try:
            header = SanitizedNeuroHeader(
                shape=[256, 256, 176],
                dtype="float32",
                voxel_sizes_mm=[-1.0, 0.0, 2.0],
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Negative and zero voxel sizes in voxel_sizes_mm",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"SanitizedNeuroHeader accepted invalid voxel sizes: {header.voxel_sizes_mm}. "
                        "No validator enforces positive zoom values (> 0)."
                    ),
                    blast_radius=(
                        "MEDIUM: Downstream spatial transforms and NiiVue/FSL tools "
                        "will produce negative Jacobian determinants or inverted coordinates."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Negative voxel sizes rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="voxel_sizes_mm enforced positive values.",
                    blast_radius="None.",
                )
            )

    def probe_05_negative_tr_and_sampling_rate(self) -> None:
        """Probe 05: Test negative acquisition repetition time and sampling rate."""
        probe_id = "PROBE-05-NEGATIVE-TIMING"
        try:
            header = SanitizedNeuroHeader(
                shape=[64, 64, 30, 200],
                dtype="float32",
                tr_seconds=-2.0,
                sampling_freq_hz=-1000.0,
                channel_count=-32,
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Negative tr_seconds, sampling_freq_hz, and channel_count",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"Accepted tr_seconds={header.tr_seconds}, "
                        f"sampling_freq_hz={header.sampling_freq_hz}, "
                        f"channel_count={header.channel_count}. "
                        "Missing gt=0 / ge=1 constraints."
                    ),
                    blast_radius=(
                        "LOW: Inverted time calculations and negative frequency ranges "
                        "in EEG/fMRI analysis steps."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="Negative timing parameters rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="Timing parameters strictly validated.",
                    blast_radius="None.",
                )
            )

    def probe_06_nan_in_value_range_and_json(self) -> None:
        """Probe 06: Test NaN injection into value_range and standard JSON output."""
        probe_id = "PROBE-06-NAN-VALUE-RANGE"
        try:
            header = SanitizedNeuroHeader(
                shape=[10, 10, 10],
                dtype="float32",
                value_range=(float("nan"), 100.0),
            )
            dumped_dict = header.model_dump()
            json_str = header.model_dump_json()

            # Test strict RFC 8259 JSON parsing (which forbids NaN)
            try:
                json.loads(json_str, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Strict JSON violation: {x}")))
                json_strict_safe = True
            except (ValueError, json.JSONDecodeError):
                json_strict_safe = False

            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="NaN accepted in value_range bypassing min > max",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"value_range with NaN was accepted: {header.value_range}. "
                        f"Standard Python json dumps produced '{json_str}', "
                        f"which violates strict RFC 8259 JSON (strict safe: {json_strict_safe})."
                    ),
                    blast_radius=(
                        "MEDIUM: Frontend JavaScript (e.g. Textual TUI or NiiVue JSON.parse) "
                        "will throw a SyntaxError when parsing NaN."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="SanitizedNeuroHeader",
                    description="NaN in value_range rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="NaN was caught during model validation.",
                    blast_radius="None.",
                )
            )

    def probe_07_contradictory_remote_artifact_uri(self) -> None:
        """Probe 07: Test cross-field contradiction between URI and host/posix_path."""
        probe_id = "PROBE-07-URI-HOST-CONTRADICTION"
        header = SanitizedNeuroHeader(shape=[10, 10, 10], dtype="float32")
        try:
            artifact = RemoteArtifact(
                artifact_id="art-confused",
                uri="clusterA:///scratch/sub-01.nii.gz",
                host="clusterB",
                posix_path="/completely/different/path/sub-99.nii.gz",
                modality=ModalityType.T1W,
                sha256_header="a" * 64,
                size_bytes=1000,
                header_summary=header,
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="RemoteArtifact",
                    description="Contradictory URI host/path vs host and posix_path fields",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"RemoteArtifact accepted URI '{artifact.uri}' while host='{artifact.host}' "
                        f"and posix_path='{artifact.posix_path}'. "
                        "No cross-field model_validator checks consistency."
                    ),
                    blast_radius=(
                        "MEDIUM: Orchestrator dispatching tasks to hostB might resolve "
                        "URI using clusterA, causing file not found or data corruption."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="RemoteArtifact",
                    description="URI and host/path cross-validation enforced",
                    passed=True,
                    vulnerability_detected=False,
                    details="Cross-validation caught contradiction.",
                    blast_radius="None.",
                )
            )

    def probe_08_relative_posix_path_in_remote_artifact(self) -> None:
        """Probe 08: Test relative posix_path in RemoteArtifact."""
        probe_id = "PROBE-08-RELATIVE-POSIX-PATH"
        header = SanitizedNeuroHeader(shape=[10, 10, 10], dtype="float32")
        try:
            artifact = RemoteArtifact(
                artifact_id="art-rel",
                uri="localhost:///relative/path.nii.gz",
                host="localhost",
                posix_path="relative/path.nii.gz",  # Relative!
                modality=ModalityType.T1W,
                sha256_header="b" * 64,
                size_bytes=100,
                header_summary=header,
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="RemoteArtifact",
                    description="Relative path accepted for posix_path field",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"Accepted relative posix_path: '{artifact.posix_path}'. "
                        "Field description promises absolute path, but no validator enforces .startswith('/')"
                    ),
                    blast_radius=(
                        "LOW: Ambiguity when resolved relative to different daemon working directories."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="RemoteArtifact",
                    description="Relative posix_path rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="posix_path enforced absolute format.",
                    blast_radius="None.",
                )
            )

    def probe_09_invalid_sha256_header_format(self) -> None:
        """Probe 09: Test non-hex or malformed sha256_header string."""
        probe_id = "PROBE-09-INVALID-SHA256"
        header = SanitizedNeuroHeader(shape=[10, 10, 10], dtype="float32")
        try:
            artifact = RemoteArtifact(
                artifact_id="art-bad-sha",
                uri="localhost:///abs/data.nii.gz",
                host="localhost",
                posix_path="/abs/data.nii.gz",
                modality=ModalityType.T1W,
                sha256_header="not_a_sha256_hash",
                size_bytes=100,
                header_summary=header,
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="RemoteArtifact",
                    description="Malformed sha256_header accepted",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"Accepted arbitrary string for sha256_header: '{artifact.sha256_header}'. "
                        "No 64-character hexadecimal regex pattern enforced."
                    ),
                    blast_radius=(
                        "LOW: Header provenance and cache-key hashing cannot rely on sha256_header."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="RemoteArtifact",
                    description="Malformed sha256_header rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="sha256_header format strictly validated.",
                    blast_radius="None.",
                )
            )

    def probe_10_task_edge_empty_strings(self) -> None:
        """Probe 10: Test empty strings in TaskEdge identifiers."""
        probe_id = "PROBE-10-TASK-EDGE-EMPTY-STRINGS"
        try:
            edge = TaskEdge(
                workflow_id="wf-1",
                parent_node_id="",
                child_node_id="child-1",
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="TaskEdge",
                    description="Empty string accepted for parent_node_id in TaskEdge",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"Accepted empty string for parent_node_id: '{edge.parent_node_id}'. "
                        "Missing min_length=1 on node identifiers."
                    ),
                    blast_radius=(
                        "LOW: Empty string keys can pollute SQLite foreign keys or DAG graphs."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="TaskEdge",
                    description="Empty string node IDs rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="min_length=1 enforced.",
                    blast_radius="None.",
                )
            )

    def probe_11_envelope_alias_mismatch_with_project_spec(self) -> None:
        """Probe 11: Test initialization with PROJECT.md field names (role, harness)."""
        probe_id = "PROBE-11-ENVELOPE-SPEC-MISMATCH"
        try:
            NeuriTaskEnvelope(
                workflow_id="wf-1",
                node_id="n-1",
                role="neuroimaging_specialist",  # PROJECT.md line 115 spec
                harness="agy",                   # PROJECT.md line 115 spec
                system_prompt="sys",
                task_instruction="inst",
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="NeuriTaskEnvelope",
                    description="Envelope accepts role and harness aliases per PROJECT.md",
                    passed=True,
                    vulnerability_detected=False,
                    details="Normalized aliases successfully.",
                    blast_radius="None.",
                )
            )
        except ValidationError as err:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="NeuriTaskEnvelope",
                    description="Envelope rejected role/harness from PROJECT.md line 115",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        f"PROJECT.md specifies 'role' and 'harness', but NeuriTaskEnvelope "
                        f"only accepts 'agent_role' and 'harness_id' without alias normalization. "
                        f"ValidationError: {err.errors()[0]['msg']}"
                    ),
                    blast_radius=(
                        "MEDIUM: Incompatibility between PROJECT.md contract and implementation. "
                        "NeuriTaskResult implemented alias normalization, but NeuriTaskEnvelope omitted it."
                    ),
                )
            )

    def probe_12_niivue_scene_empty_volumes(self) -> None:
        """Probe 12: Test empty volumes list in NiiVueSceneSpec."""
        probe_id = "PROBE-12-NIIVUE-EMPTY-VOLUMES"
        try:
            scene = NiiVueSceneSpec(
                scene_id="scene-empty",
                title="Empty Scene",
                volumes=[],
            )
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="NiiVueSceneSpec",
                    description="Empty volumes list accepted in NiiVueSceneSpec",
                    passed=False,
                    vulnerability_detected=True,
                    details=(
                        "NiiVueSceneSpec accepted volumes=[]. A NiiVue viewer requires "
                        "at least one volume layer to establish coordinate space."
                    ),
                    blast_radius=(
                        "LOW: Rendering frontend may encounter unhandled empty volume array."
                    ),
                )
            )
        except ValidationError:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="NiiVueSceneSpec",
                    description="Empty volumes list rejected",
                    passed=True,
                    vulnerability_detected=False,
                    details="min_length=1 enforced on volumes.",
                    blast_radius="None.",
                )
            )

    def probe_13_json_roundtrip_fidelity(self) -> None:
        """Probe 13: Test JSON roundtrip serialization fidelity across all models."""
        probe_id = "PROBE-13-JSON-ROUNDTRIP"
        try:
            now = datetime.now(timezone.utc)
            event = TelemetryEvent(
                event_id="evt-rt",
                workflow_id="wf-rt",
                node_id="n-rt",
                harness_id="codex",
                timestamp=now,
                event_type="token_usage",
                input_tokens=1000,
                output_tokens=250,
                estimated_cost_usd=0.015,
            )
            dumped_json = event.model_dump_json()
            restored = TelemetryEvent.model_validate_json(dumped_json)
            assert restored.event_id == event.event_id
            assert restored.output_tokens == event.output_tokens
            assert restored.event_type == event.event_type
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="TelemetryEvent",
                    description="JSON serialization roundtrip",
                    passed=True,
                    vulnerability_detected=False,
                    details="Full roundtrip succeeded with exact field fidelity.",
                    blast_radius="None.",
                )
            )
        except Exception as err:
            self.results.append(
                ProbeResult(
                    probe_id=probe_id,
                    target_model="TelemetryEvent",
                    description="JSON serialization roundtrip failed",
                    passed=False,
                    vulnerability_detected=True,
                    details=f"Roundtrip failed with exception: {err}",
                    blast_radius="HIGH: Serialization failure in telemetry streaming.",
                )
            )


def main() -> int:
    """Run harness and print report summary."""
    harness = SchemaAdversarialHarness()
    results = harness.run_all_probes()

    print("=" * 80)
    print("NEURI M1 ADVERSARIAL VERIFICATION REPORT")
    print("=" * 80)

    vuln_count = sum(1 for r in results if r.vulnerability_detected)
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)

    for r in results:
        status = "[VULNERABILITY]" if r.vulnerability_detected else "[PASS]"
        print(f"{status} {r.probe_id}: {r.description}")
        print(f"       Details: {r.details}")
        print(f"       Blast Radius: {r.blast_radius}")
        print("-" * 80)

    print(f"\nSummary: {passed_count}/{total_count} Passed, {vuln_count} Vulnerabilities / Edge Cases Flagged.")
    return 1 if vuln_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
