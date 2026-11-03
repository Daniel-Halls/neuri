"""Containerized neuroimaging pipeline command builder for Neuri.

Constructs deterministic Apptainer, Singularity, and Docker invocation
commands with isolated bind mounts, environment variable propagation,
FreeSurfer license mappings, and TemplateFlow caches.
"""

from enum import Enum
from pathlib import Path
import shlex
from typing import Any


class ContainerRuntime(str, Enum):
    """Supported container runtime engines."""

    APPTAINER = "apptainer"
    SINGULARITY = "singularity"
    DOCKER = "docker"


class ContainerCommandBuilder:
    """Builder for BIDS Apps execution inside containerized environments.

    Parameters
    ------------
    pipeline: str
        Target BIDS App pipeline name (e.g. 'fmriprep', 'qsiprep', 'mriqc').
    bids_dir: Path
        Host path to input BIDS dataset root.
    output_dir: Path
        Host path to output derivatives directory.
    sif_image: Path | str
        Path to Singularity/Apptainer image (.sif) or Docker image tag.
    work_dir: Path | None
        Host scratch working directory. Defaults to None.
    fs_license: Path | None
        Host path to FreeSurfer license.txt. Defaults to None.
    templateflow_home: Path | None
        Host path to TemplateFlow archive. Defaults to None.
    runtime: ContainerRuntime | str
        Target container engine. Defaults to APPTAINER.
    participant_label: list[str] | str | None
        Subject identifiers to process. Defaults to None.
    extra_args: list[str] | None
        Additional pipeline arguments. Defaults to None.

    Returns
    --------
        ContainerCommandBuilder: ContainerCommandBuilder instance
            Constructed command builder.
    """

    CONTAINER_BIDS_DIR: str = "/data"
    CONTAINER_OUT_DIR: str = "/out"
    CONTAINER_WORK_DIR: str = "/work"
    CONTAINER_FS_LICENSE: str = "/opt/freesurfer/license.txt"
    CONTAINER_TF_HOME: str = "/opt/templateflow"

    def __init__(
        self,
        pipeline: str,
        bids_dir: Path,
        output_dir: Path,
        sif_image: Path | str,
        work_dir: Path | None = None,
        fs_license: Path | None = None,
        templateflow_home: Path | None = None,
        runtime: ContainerRuntime | str = ContainerRuntime.APPTAINER,
        participant_label: list[str] | str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        """Initialize pipeline container command builder parameters.

        Parameters
        ------------
        pipeline: str
            Target pipeline name.
        bids_dir: Path
            Input BIDS root path.
        output_dir: Path
            Output derivatives path.
        sif_image: Path | str
            Container image reference.
        work_dir: Path | None
            Working directory path. Defaults to None.
        fs_license: Path | None
            FreeSurfer license path. Defaults to None.
        templateflow_home: Path | None
            TemplateFlow directory path. Defaults to None.
        runtime: ContainerRuntime | str
            Container engine. Defaults to APPTAINER.
        participant_label: list[str] | str | None
            Subject identifiers. Defaults to None.
        extra_args: list[str] | None
            Extra command-line flags. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes builder fields.
        """
        self.pipeline: str = pipeline.lower().strip()
        self.bids_dir: Path = bids_dir
        self.output_dir: Path = output_dir
        self.sif_image: str = str(sif_image)
        self.work_dir: Path | None = work_dir
        self.fs_license: Path | None = fs_license
        self.templateflow_home: Path | None = templateflow_home
        self.runtime: ContainerRuntime = (
            runtime
            if isinstance(runtime, ContainerRuntime)
            else ContainerRuntime(str(runtime).lower())
        )
        self.participant_label: list[str] = (
            [participant_label]
            if isinstance(participant_label, str)
            else (participant_label if participant_label is not None else [])
        )
        self.extra_args: list[str] = extra_args if extra_args is not None else []

    def build_bind_mounts(self) -> list[str]:
        """Construct bind mount arguments according to selected container runtime.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                CLI bind flags (e.g. -B host:container or -v host:container).
        """
        mounts: list[str] = []
        is_docker: bool = self.runtime == ContainerRuntime.DOCKER

        # 1. BIDS input directory (read-only)
        bids_path: str = str(self.bids_dir)
        if is_docker:
            mounts.extend(["-v", f"{bids_path}:{self.CONTAINER_BIDS_DIR}:ro"])
        else:
            mounts.extend(["-B", f"{bids_path}:{self.CONTAINER_BIDS_DIR}:ro"])

        # 2. Output derivatives directory (read-write)
        out_path: str = str(self.output_dir)
        if is_docker:
            mounts.extend(["-v", f"{out_path}:{self.CONTAINER_OUT_DIR}:rw"])
        else:
            mounts.extend(["-B", f"{out_path}:{self.CONTAINER_OUT_DIR}"])

        # 3. Work directory (read-write)
        if self.work_dir is not None:
            w_path: str = str(self.work_dir)
            if is_docker:
                mounts.extend(["-v", f"{w_path}:{self.CONTAINER_WORK_DIR}:rw"])
            else:
                mounts.extend(["-B", f"{w_path}:{self.CONTAINER_WORK_DIR}"])

        # 4. FreeSurfer license (read-only)
        if self.fs_license is not None:
            lic_path: str = str(self.fs_license)
            if is_docker:
                mounts.extend([
                    "-v",
                    f"{lic_path}:{self.CONTAINER_FS_LICENSE}:ro",
                ])
            else:
                mounts.extend(["-B", f"{lic_path}:{self.CONTAINER_FS_LICENSE}:ro"])

        # 5. TemplateFlow home (read-write / read-only)
        if self.templateflow_home is not None:
            tf_path: str = str(self.templateflow_home)
            if is_docker:
                mounts.extend(["-v", f"{tf_path}:{self.CONTAINER_TF_HOME}:ro"])
            else:
                mounts.extend(["-B", f"{tf_path}:{self.CONTAINER_TF_HOME}"])

        return mounts

    def build_environment_flags(self) -> list[str]:
        """Generate runtime environment variable injection flags.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                CLI environment variable options.
        """
        env_flags: list[str] = []
        if self.runtime == ContainerRuntime.DOCKER:
            if self.fs_license is not None:
                env_flags.extend(["-e", f"FS_LICENSE={self.CONTAINER_FS_LICENSE}"])
            if self.templateflow_home is not None:
                env_flags.extend([
                    "-e",
                    f"TEMPLATEFLOW_HOME={self.CONTAINER_TF_HOME}",
                ])
        elif self.runtime == ContainerRuntime.APPTAINER:
            if self.fs_license is not None:
                env_flags.extend([
                    "--env",
                    f"APPTAINERENV_FS_LICENSE={self.CONTAINER_FS_LICENSE}",
                ])
            if self.templateflow_home is not None:
                env_flags.extend([
                    "--env",
                    f"APPTAINERENV_TEMPLATEFLOW_HOME={self.CONTAINER_TF_HOME}",
                ])
        elif self.runtime == ContainerRuntime.SINGULARITY:
            if self.fs_license is not None:
                env_flags.extend([
                    "--env",
                    f"SINGULARITYENV_FS_LICENSE={self.CONTAINER_FS_LICENSE}",
                ])
            if self.templateflow_home is not None:
                env_flags.extend([
                    "--env",
                    f"SINGULARITYENV_TEMPLATEFLOW_HOME={self.CONTAINER_TF_HOME}",
                ])

        return env_flags

    def build_command(self) -> str:
        """Assemble full sanitized shell command sequence.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Executable shell command line.
        """
        parts: list[str] = []

        if self.runtime in (
            ContainerRuntime.APPTAINER,
            ContainerRuntime.SINGULARITY,
        ):
            bin_name: str = self.runtime.value
            parts.append(bin_name)
            parts.append("run")
            parts.append("--cleanenv")
            parts.append("--containall")
            parts.extend(self.build_bind_mounts())
            parts.extend(self.build_environment_flags())
            parts.append(shlex.quote(self.sif_image))
        else:
            parts.append("docker")
            parts.append("run")
            parts.append("--rm")
            parts.extend(self.build_bind_mounts())
            parts.extend(self.build_environment_flags())
            parts.append(shlex.quote(self.sif_image))

        # Positional arguments expected by standard BIDS Apps
        parts.append(self.CONTAINER_BIDS_DIR)
        parts.append(self.CONTAINER_OUT_DIR)
        parts.append("participant")

        if self.participant_label:
            cleaned_labels: list[str] = [
                lbl.replace("sub-", "") for lbl in self.participant_label
            ]
            parts.extend([
                "--participant-label",
                " ".join(cleaned_labels),
            ])

        if self.work_dir is not None:
            parts.extend(["-w", self.CONTAINER_WORK_DIR])

        if self.fs_license is not None:
            parts.extend(["--fs-license-file", self.CONTAINER_FS_LICENSE])

        if self.extra_args:
            parts.extend(self.extra_args)

        cmd_string: str = " ".join(parts)
        return cmd_string


__all__: list[str] = [
    "ContainerCommandBuilder",
    "ContainerRuntime",
]
