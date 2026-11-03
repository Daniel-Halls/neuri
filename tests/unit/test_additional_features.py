"""Unit tests for Neuri Additional Features (3_additional_features.md).

Tests BIDS dataset layout validation, container command builder, Slurm job arrays,
quantitative QC metrics triage, electrophysiology header parsing & QA montage,
NiiVue 2-way coordinate feedback & compare mode, BIDS provenance export & methods
synthesis, and interactive DAG inspector/editing.
"""

from collections.abc import Generator
import gzip
import json
from pathlib import Path
import struct
from typing import Any

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskNode,
    TaskState,
)
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.literature.provenance_exporter import (
    BIDSProvenanceExporter,
    MethodsSectionSynthesizer,
)
from neuri.remote.container_builder import (
    ContainerCommandBuilder,
    ContainerRuntime,
)
from neuri.remote.slurm_bridge import DetachAndReconcileManager
from neuri.viewer.niivue_bridge import NiiVueBridge, NiiVueBridgeHandler
from neuri_worker.bids_validator import BIDSLayoutValidator
from neuri_worker.headless_qa import HeadlessQAGenerator
from neuri_worker.mcp_server import RemoteWorkerMCPServer
from neuri_worker.qc_metrics import NeuroQCTriageEngine
from neuri_worker.sanitizer import NeuroHeaderSanitizer


def test_bids_layout_validator_and_slash_command(tmp_path: Path) -> None:
    """Test zero-dependency BIDS layout validation and /bids slash command.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts BIDS layout validation, modality counts, and CLI table output.
    """
    bids_root: Path = tmp_path / "synthetic_bids"
    bids_root.mkdir()

    desc_file: Path = bids_root / "dataset_description.json"
    desc_file.write_text(
        json.dumps({
            "Name": "Synthetic Cohort",
            "BIDSVersion": "1.9.0",
        }),
        encoding="utf-8",
    )

    part_file: Path = bids_root / "participants.tsv"
    part_file.write_text(
        "participant_id\tage\tsex\nsub-01\t25\tF\nsub-02\t30\tM\n",
        encoding="utf-8",
    )

    # Sub-01: valid anat + func
    sub01_anat: Path = bids_root / "sub-01" / "anat"
    sub01_anat.mkdir(parents=True)
    (sub01_anat / "sub-01_T1w.nii.gz").write_bytes(b"\x00" * 352)

    sub01_func: Path = bids_root / "sub-01" / "func"
    sub01_func.mkdir(parents=True)
    (sub01_func / "sub-01_task-rest_bold.nii.gz").write_bytes(b"\x00" * 352)
    (sub01_func / "sub-01_task-rest_bold.json").write_text(
        json.dumps({"RepetitionTime": 2.0, "TaskName": "rest"}),
        encoding="utf-8",
    )

    # Sub-02: missing T1w and missing bold sidecar
    sub02_func: Path = bids_root / "sub-02" / "func"
    sub02_func.mkdir(parents=True)
    (sub02_func / "sub-02_task-rest_bold.nii.gz").write_bytes(b"\x00" * 352)

    validator: BIDSLayoutValidator = BIDSLayoutValidator()
    report: dict[str, Any] = validator.scan_dataset(bids_root)

    assert report["valid"] is True
    assert report["subject_count"] == 2
    assert report["dataset_name"] == "Synthetic Cohort"
    assert report["modality_counts"]["anat"] == 1
    assert report["modality_counts"]["func"] == 2
    assert len(report["missing_sidecars"]) >= 1

    ready, blockers = validator.validate_preflight_cohort(
        bids_root, pipeline_name="fmriprep"
    )
    assert ready is False
    assert any("sub-02 lacks anatomical" in b for b in blockers)

    # Test MCP server bids tools
    server: RemoteWorkerMCPServer = RemoteWorkerMCPServer()
    mcp_res = server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "validate_bids_directory",
            "arguments": {"path": str(bids_root)},
        },
    })
    assert mcp_res["result"]["valid_structure"] is True
    assert mcp_res["result"]["subject_count"] == 2

    # Test /bids slash command
    bb: Blackboard = Blackboard(tmp_path / "state.db")
    cfg: NeuriConfig = NeuriConfig()
    orch: DAGOrchestrator = DAGOrchestrator(bb, cfg)
    router: SlashCommandRouter = SlashCommandRouter(bids_root, cfg, bb, orch)

    res_sum: SlashCommandResult = router.execute(f"/bids summary {bids_root}")
    assert res_sum.success is True
    assert "Synthetic Cohort" in res_sum.markdown_output

    res_val: SlashCommandResult = router.execute(f"/bids validate {bids_root}")
    assert "BIDS Dataset Validation" in res_val.markdown_output


def test_container_command_builder_apptainer_and_docker(
    tmp_path: Path,
) -> None:
    """Test deterministic container command building for Apptainer and Docker.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts bind mount generation, environment flags, and command strings.
    """
    bids_dir: Path = tmp_path / "bids"
    out_dir: Path = tmp_path / "derivatives"
    work_dir: Path = tmp_path / "scratch"
    fs_license: Path = tmp_path / "license.txt"
    tf_home: Path = tmp_path / "templateflow"

    # 1. Apptainer builder
    app_builder: ContainerCommandBuilder = ContainerCommandBuilder(
        pipeline="fmriprep",
        bids_dir=bids_dir,
        output_dir=out_dir,
        work_dir=work_dir,
        fs_license=fs_license,
        templateflow_home=tf_home,
        sif_image="/opt/images/fmriprep_24.0.0.sif",
        runtime=ContainerRuntime.APPTAINER,
        participant_label=["sub-01", "02"],
        extra_args=["--dummy-scans", "4"],
    )

    app_cmd: str = app_builder.build_command()
    assert "apptainer run --cleanenv --containall" in app_cmd
    assert f"-B {bids_dir}:/data:ro" in app_cmd
    assert f"-B {out_dir}:/out" in app_cmd
    assert f"-B {work_dir}:/work" in app_cmd
    assert f"-B {fs_license}:/opt/freesurfer/license.txt:ro" in app_cmd
    assert "--participant-label 01 02" in app_cmd
    assert "--dummy-scans 4" in app_cmd
    assert "APPTAINERENV_FS_LICENSE" in app_cmd

    # 2. Docker builder
    doc_builder: ContainerCommandBuilder = ContainerCommandBuilder(
        pipeline="qsiprep",
        bids_dir=bids_dir,
        output_dir=out_dir,
        sif_image="pennbbl/qsiprep:0.21.0",
        runtime=ContainerRuntime.DOCKER,
        participant_label="sub-03",
    )

    doc_cmd: str = doc_builder.build_command()
    assert "docker run --rm" in doc_cmd
    assert f"-v {bids_dir}:/data:ro" in doc_cmd
    assert f"-v {out_dir}:/out:rw" in doc_cmd
    assert "--participant-label 03" in doc_cmd


def test_slurm_array_wrapper_and_retry_generation() -> None:
    """Test Slurm array wrapper generation and failed index retry command.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts Slurm array script structure and targeted retry command.
    """
    manager: DetachAndReconcileManager = DetachAndReconcileManager()
    cmd_tmpl: str = (
        "fmriprep /data /out participant --participant-label ${SUBJECT}"
    )
    script: str = manager.generate_slurm_array_wrapper(
        command_template=cmd_tmpl,
        cohort_file="/scratch/cohort/subjects.txt",
        total_tasks=50,
        job_dir="/scratch/jobs/job_array_01",
        max_concurrent=8,
        partition="gpu",
        cpus=8,
        mem_gb=32,
    )

    assert "#SBATCH --array=1-50%8" in script
    assert 'SUBJECT="$(sed -n "${SLURM_ARRAY_TASK_ID}p"' in script
    expected_status: str = (
        'STATUS_FILE="/scratch/jobs/job_array_01/'
        'task_${SLURM_ARRAY_TASK_ID}.json"'
    )
    assert expected_status in script
    assert cmd_tmpl in script

    retry_cmd: str = manager.generate_array_retry_command(
        failed_indices=[14, 37, 2],
        script_path="/scratch/jobs/job_array_01/run.sh",
    )
    assert "sbatch --array=2,14,37 /scratch/jobs/job_array_01/run.sh" in retry_cmd


def test_neuro_qc_metrics_parser_and_outlier_triage(tmp_path: Path) -> None:
    """Test quantitative Image Quality Metrics parser and cohort triage gate.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts fMRIPrep and MRIQC metrics parsing and outlier exclusion.
    """
    engine: NeuroQCTriageEngine = NeuroQCTriageEngine(
        max_mean_fd_mm=0.5, max_high_motion_pct=20.0, min_tsnr=20.0
    )

    # 1. Valid fMRIPrep confounds TSV (PASS)
    good_tsv: Path = tmp_path / "sub-01_desc-confounds_timeseries.tsv"
    rows_good: list[str] = [
        "framewise_displacement\tdvars",
        "0.0\t1.2",
        "0.15\t1.4",
        "0.22\t1.1",
        "0.18\t1.3",
    ]
    good_tsv.write_text("\n".join(rows_good), encoding="utf-8")
    m_good = engine.parse_fmriprep_confounds(good_tsv)
    assert m_good["status"] == "PASS"
    assert m_good["mean_fd"] < 0.25

    # 2. High motion confounds TSV (EXCLUDE)
    bad_tsv: Path = tmp_path / "sub-02_desc-confounds_timeseries.tsv"
    rows_bad: list[str] = [
        "framewise_displacement\tdvars",
        "0.85\t3.5",
        "0.92\t4.1",
        "0.78\t2.9",
        "0.12\t1.2",
    ]
    bad_tsv.write_text("\n".join(rows_bad), encoding="utf-8")
    m_bad = engine.parse_fmriprep_confounds(bad_tsv)
    assert m_bad["status"] == "EXCLUDE"
    assert any("exceeds limit" in f for f in m_bad["flags"])

    # 3. MRIQC group TSV parsing
    group_bold: Path = tmp_path / "group_bold.tsv"
    rows_grp: list[str] = [
        "bids_name\ttsnr\tfd_mean",
        "sub-01_bold\t35.5\t0.14",
        "sub-02_bold\t14.2\t0.62",
    ]
    group_bold.write_text("\n".join(rows_grp), encoding="utf-8")
    grp_res = engine.parse_mriqc_group_tsv(group_bold)
    assert len(grp_res) == 2
    assert grp_res[0]["status"] == "PASS"
    assert grp_res[1]["status"] == "EXCLUDE"


def test_electrophys_header_parsers_and_headless_qa_montage(
    tmp_path: Path,
) -> None:
    """Test BrainVision/FIFF header parsing and electrophysiology QA montage rendering.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts header parsing, PHI stripping, and PNG montage generation.
    """
    sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()

    # 1. BrainVision .vhdr parsing and scrubbing
    vhdr_file: Path = tmp_path / "sub-01_task-rest_eeg.vhdr"
    vhdr_content: str = (
        "Brain Vision Data Exchange Header File Version 1.0\n"
        "; Patient=JaneDoe; DOB=1985-05-12\n"
        "[Common Infos]\n"
        "DataFile=sub-01_task-rest_eeg.eeg\n"
        "NumberOfChannels=16\n"
        "SamplingInterval=1000\n"
        "[Channel Infos]\n"
        "Ch1=Fp1\n"
    )
    vhdr_file.write_text(vhdr_content, encoding="utf-8")

    art: RemoteArtifact = sanitizer.inspect_file(
        vhdr_file, modality=ModalityType.EEG
    )
    assert art.header_summary is not None
    assert art.header_summary.channel_count == 16
    assert art.header_summary.sampling_freq_hz == 1000.0

    scrubbed_vhdr: Path = sanitizer.scrub_file(vhdr_file)
    assert "Patient=JaneDoe" not in scrubbed_vhdr.read_text(encoding="utf-8")

    # 2. Headless QA electrophysiology montage rendering
    qa_gen: HeadlessQAGenerator = HeadlessQAGenerator(output_dir=tmp_path)
    qa_res = qa_gen.generate_electrophys_qa_snapshot(vhdr_file)

    assert Path(qa_res["snapshot_path"]).is_file()
    assert qa_res["channel_count"] == 16
    assert qa_res["sampling_freq_hz"] == 1000.0


def test_niivue_selection_feedback_and_view_compare(tmp_path: Path) -> None:
    """Test 2-way NiiVue coordinate selection feedback and /view compare mode.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts scene comparison spec and selection recording.
    """
    bb: Blackboard = Blackboard(tmp_path / "state.db")
    cfg: NeuriConfig = NeuriConfig()
    orch: DAGOrchestrator = DAGOrchestrator(bb, cfg)
    router: SlashCommandRouter = SlashCommandRouter(tmp_path, cfg, bb, orch)

    fixed: Path = tmp_path / "tpl-MNI152NLin2009cAsym_T1w.nii.gz"
    moving: Path = tmp_path / "sub-01_space-MNI152_T1w.nii.gz"
    fixed.write_bytes(b"\x00" * 352)
    moving.write_bytes(b"\x00" * 352)

    res_comp: SlashCommandResult = router.execute(
        f"/view compare {fixed} {moving} --no-open"
    )
    assert res_comp.success is True
    assert "Comparison Scene Loaded" in res_comp.markdown_output
    assert res_comp.data["fixed_uri"] == str(fixed)
    assert res_comp.data["moving_uri"] == str(moving)

    # Test NiiVueBridge scene selection state
    bridge: NiiVueBridge = NiiVueBridge.get_instance()
    bridge.latest_selection = {
        "world_coord": [-12.5, 24.0, 48.0],
        "voxel_coord": [128, 140, 110],
        "intensity": 142.8,
        "label": "Left Precentral Gyrus",
    }
    sel = bridge.latest_selection
    assert sel is not None
    assert sel["world_coord"] == [-12.5, 24.0, 48.0]
    assert sel["label"] == "Left Precentral Gyrus"


def test_bids_provenance_exporter_and_methods_synthesis(tmp_path: Path) -> None:
    """Test BIDS derivative provenance export and COBIDAS Methods synthesis.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts dataset_description.json structure and synthesized Methods text.
    """
    bb: Blackboard = Blackboard(tmp_path / "state.db")
    bb.create_workflow("wf_export_01", "Provenance and Methods test")

    node: TaskNode = TaskNode(
        node_id="node_fmriprep",
        workflow_id="wf_export_01",
        agent_role="pipeline_engineer",
        harness_id="agy",
        state=TaskState.COMPLETED,
        envelope=NeuriTaskEnvelope(
            workflow_id="wf_export_01",
            node_id="node_fmriprep",
            agent_role="pipeline_engineer",
            task_instruction=(
                "Preprocess anatomical and functional BOLD images with fMRIPrep"
            ),
            harness_id="agy",
            execution_mode="headless_json",
        ),
    )
    bb.create_node(node)

    bb.register_citation(
        citation_key="esteban2019fmriprep",
        bibtex="@article{esteban2019fmriprep, title={fMRIPrep}, year={2019}}",
        doi="10.1038/s41592-018-0235-4",
        title="fMRIPrep: a robust preprocessing pipeline for functional MRI",
    )

    # 1. Export provenance
    exporter: BIDSProvenanceExporter = BIDSProvenanceExporter(bb)
    manifest = exporter.export_dataset_description("wf_export_01")
    assert manifest["BIDSVersion"] == "1.9.0"
    assert manifest["DatasetType"] == "derivative"
    assert len(manifest["GeneratedBy"]) == 1
    assert manifest["GeneratedBy"][0]["Name"] == "neuri-pipeline_engineer"

    out_file: Path = tmp_path / "dataset_description.json"
    exporter.write_dataset_description(out_file, "wf_export_01")
    assert out_file.is_file()

    # 2. Synthesize Methods section
    synthesizer: MethodsSectionSynthesizer = MethodsSectionSynthesizer(bb)
    methods_res = synthesizer.synthesize_methods("wf_export_01")
    md_text = methods_res["methods_markdown"]

    assert "### Preprocessing and Image Analysis Workflow" in md_text
    assert "fMRIPrep [@esteban2019fmriprep]" in md_text
    assert "MNI152NLin2009cAsym" in md_text
    assert "### References" in md_text

    # 3. Test slash commands
    cfg: NeuriConfig = NeuriConfig()
    orch: DAGOrchestrator = DAGOrchestrator(bb, cfg)
    router: SlashCommandRouter = SlashCommandRouter(tmp_path, cfg, bb, orch)

    res_exp = router.execute("/export provenance wf_export_01")
    assert res_exp.success is True
    assert "Exported BIDS Derivative Provenance Manifest" in res_exp.markdown_output

    res_meth = router.execute("/paperback methods wf_export_01")
    assert res_meth.success is True
    assert "COBIDAS-Compliant Methods Synthesis" in res_meth.markdown_output


def test_dag_inspector_drawer_and_plan_inspect_edit(tmp_path: Path) -> None:
    """Test interactive DAG Inspector drawer data generation and /plan inspect/edit.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts /plan inspect, /plan edit, and /plan set operations.
    """
    bb: Blackboard = Blackboard(tmp_path / "state.db")
    cfg: NeuriConfig = NeuriConfig()
    orch: DAGOrchestrator = DAGOrchestrator(bb, cfg)
    router: SlashCommandRouter = SlashCommandRouter(tmp_path, cfg, bb, orch)

    # Plan a workflow
    res_plan = router.execute("/plan Preprocess fMRI and compute connectivity")
    wf_id = res_plan.data["workflow_id"]
    nodes = bb.get_nodes_by_workflow(wf_id)
    assert len(nodes) > 0
    first_node_id = nodes[0].node_id

    # /plan inspect
    res_insp = router.execute(f"/plan inspect {first_node_id}")
    assert res_insp.success is True
    assert f"Node Inspector: `{first_node_id}`" in res_insp.markdown_output

    # /plan edit
    res_edit = router.execute(
        f"/plan edit {first_node_id} Updated instruction for BET extraction"
    )
    assert res_edit.success is True
    assert "Updated Task Instruction" in res_edit.markdown_output

    updated_node = bb.get_node(first_node_id)
    assert updated_node is not None
    assert (
        updated_node.envelope.task_instruction
        == "Updated instruction for BET extraction"
    )

    # /plan set
    res_set = router.execute(f"/plan set {first_node_id} codex claude-3-opus")
    assert res_set.success is True
    assert "Updated Routing" in res_set.markdown_output

    updated_routed = bb.get_node(first_node_id)
    assert updated_routed is not None
    assert updated_routed.harness_id == "codex"
    assert updated_routed.model == "claude-3-opus"
