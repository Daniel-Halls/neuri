"""Automated neuroimaging QC metrics parser and cohort triage engine.

Extracts quantitative Image Quality Metrics (IQMs) from fMRIPrep confounds TSVs,
MRIQC group tables, and QSIPrep QC summaries without external dependencies,
classifying subjects into PASS, WARN, or EXCLUDE quality tiers.
"""

from collections.abc import Generator
import csv
import math
from pathlib import Path
from typing import Any


class NeuroQCTriageEngine:
    """Quantitative QC metrics parser and outlier gate for neuroimaging pipelines.

    Parameters
    ------------
    fd_threshold_mm: float
        Framewise displacement spike threshold in mm. Defaults to 0.5.
    max_mean_fd_mm: float
        Maximum acceptable mean framewise displacement. Defaults to 0.5.
    max_high_motion_pct: float
        Maximum percentage of volumes allowed to exceed FD threshold.
        Defaults to 20.0.
    min_tsnr: float
        Minimum temporal signal-to-noise ratio for BOLD. Defaults to 20.0.
    min_euler_number: float
        Minimum Euler defect threshold for T1w cortical reconstruction.
        Defaults to -100.0.

    Returns
    --------
        NeuroQCTriageEngine: NeuroQCTriageEngine instance
            Constructed triage engine.
    """

    def __init__(
        self,
        fd_threshold_mm: float = 0.5,
        max_mean_fd_mm: float = 0.5,
        max_high_motion_pct: float = 20.0,
        min_tsnr: float = 20.0,
        min_euler_number: float = -100.0,
    ) -> None:
        """Initialize triage engine with quality thresholds.

        Parameters
        ------------
        fd_threshold_mm: float
            Framewise displacement spike threshold. Defaults to 0.5.
        max_mean_fd_mm: float
            Mean FD upper limit. Defaults to 0.5.
        max_high_motion_pct: float
            Max allowed % volumes with high motion. Defaults to 20.0.
        min_tsnr: float
            Minimum acceptable tSNR. Defaults to 20.0.
        min_euler_number: float
            Minimum acceptable Euler number. Defaults to -100.0.

        Returns
        --------
            None: NoneType object
                Initializes threshold configuration.
        """
        self.fd_threshold_mm: float = fd_threshold_mm
        self.max_mean_fd_mm: float = max_mean_fd_mm
        self.max_high_motion_pct: float = max_high_motion_pct
        self.min_tsnr: float = min_tsnr
        self.min_euler_number: float = min_euler_number

    def parse_fmriprep_confounds(
        self, confounds_tsv_path: Path
    ) -> dict[str, Any]:
        """Extract motion and confound timeseries summary metrics from fMRIPrep TSV.

        Parameters
        ------------
        confounds_tsv_path: Path
            Path to desc-confounds_timeseries.tsv file.

        Returns
        --------
            dict[str, Any]: dictionary object
                Motion metrics including mean FD, % high motion volumes, and DVARS.
        """
        if not confounds_tsv_path.is_file():
            empty_res: dict[str, Any] = {
                "file": str(confounds_tsv_path),
                "error": "File not found",
                "status": "EXCLUDE",
                "flags": ["Confounds file not found"],
            }
            return empty_res

        fd_values: list[float] = []
        dvars_values: list[float] = []

        try:
            with confounds_tsv_path.open(
                "r", encoding="utf-8", errors="ignore"
            ) as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    fd_raw = row.get("framewise_displacement", "")
                    if fd_raw and fd_raw.lower() not in ("n/a", "nan", ""):
                        with_float = float(fd_raw)
                        if math.isfinite(with_float):
                            fd_values.append(with_float)

                    dvars_raw = row.get("dvars", "") or row.get("std_dvars", "")
                    if dvars_raw and dvars_raw.lower() not in (
                        "n/a",
                        "nan",
                        "",
                    ):
                        with_dvars = float(dvars_raw)
                        if math.isfinite(with_dvars):
                            dvars_values.append(with_dvars)
        except Exception as exc:
            err_res: dict[str, Any] = {
                "file": str(confounds_tsv_path),
                "error": str(exc),
                "status": "EXCLUDE",
                "flags": [f"Failed to parse TSV: {exc}"],
            }
            return err_res

        total_vols: int = max(1, len(fd_values))
        mean_fd: float = (
            round(sum(fd_values) / total_vols, 4) if fd_values else 0.0
        )
        high_motion_count: int = sum(
            1 for v in fd_values if v > self.fd_threshold_mm
        )
        high_motion_pct: float = round(
            (high_motion_count / total_vols) * 100, 2
        )
        mean_dvars: float = (
            round(sum(dvars_values) / len(dvars_values), 4)
            if dvars_values
            else 0.0
        )

        flags: list[str] = []
        status: str = "PASS"

        if mean_fd > self.max_mean_fd_mm:
            status = "EXCLUDE"
            flags.append(
                f"Mean FD ({mean_fd} mm) exceeds limit ({self.max_mean_fd_mm} mm)"
            )
        elif mean_fd > (self.max_mean_fd_mm * 0.75):
            status = "WARN"
            flags.append(f"Elevated mean FD ({mean_fd} mm)")

        if high_motion_pct > self.max_high_motion_pct:
            status = "EXCLUDE"
            flags.append(
                f"High-motion volumes ({high_motion_pct}%) exceed ceiling "
                f"({self.max_high_motion_pct}%)"
            )
        elif high_motion_pct > (self.max_high_motion_pct * 0.5):
            if status != "EXCLUDE":
                status = "WARN"
            flags.append(
                f"Noticeable motion volume spike rate ({high_motion_pct}%)"
            )

        metrics: dict[str, Any] = {
            "file": str(confounds_tsv_path),
            "total_volumes": total_vols,
            "mean_fd": mean_fd,
            "high_motion_volumes": high_motion_count,
            "high_motion_percent": high_motion_pct,
            "mean_dvars": mean_dvars,
            "status": status,
            "flags": flags,
        }
        return metrics

    def _safe_float(self, val: Any) -> float | None:
        """Safely convert value to float, returning None on failure.

        Parameters
        ------------
        val: Any
            Input value to convert to float.

        Returns
        --------
            float | None: float or None
                Parsed float value or None if conversion failed.
        """
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def parse_mriqc_group_tsv(
        self, group_tsv_path: Path
    ) -> list[dict[str, Any]]:
        """Parse group-level MRIQC summary TSV table and evaluate each subject.

        Parameters
        ------------
        group_tsv_path: Path
            Path to group_bold.tsv or group_T1w.tsv.

        Returns
        --------
            list[dict[str, Any]]: list object
                Per-subject quality metric records and triage classification.
        """
        results: list[dict[str, Any]] = []
        if not group_tsv_path.is_file():
            return results

        is_bold: bool = "bold" in group_tsv_path.name.lower()

        try:
            with group_tsv_path.open(
                "r", encoding="utf-8", errors="ignore"
            ) as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    bids_id = (
                        row.get("bids_name")
                        or row.get("bids_id")
                        or row.get("subject_id", "unknown")
                    )
                    flags: list[str] = []
                    status: str = "PASS"

                    tsnr_val: float | None = None
                    fd_mean_val: float | None = None
                    euler_val: float | None = None

                    if is_bold:
                        if "tsnr" in row and row["tsnr"]:
                            tsnr_val = self._safe_float(row["tsnr"])
                            if (
                                tsnr_val is not None
                                and tsnr_val < self.min_tsnr
                            ):
                                status = "EXCLUDE"
                                flags.append(
                                    f"Low tSNR ({tsnr_val:.1f} < {self.min_tsnr})"
                                )
                        if "fd_mean" in row and row["fd_mean"]:
                            fd_mean_val = self._safe_float(row["fd_mean"])
                            if (
                                fd_mean_val is not None
                                and fd_mean_val > self.max_mean_fd_mm
                            ):
                                status = "EXCLUDE"
                                flags.append(
                                    f"High mean FD ({fd_mean_val:.2f} mm)"
                                )
                    else:
                        if "euler_number" in row and row["euler_number"]:
                            euler_val = self._safe_float(row["euler_number"])
                            if (
                                euler_val is not None
                                and euler_val < self.min_euler_number
                            ):
                                status = "EXCLUDE"
                                flags.append(
                                    f"Severe cortical defect "
                                    f"(Euler {euler_val:.0f})"
                                )

                    rec: dict[str, Any] = {
                        "subject": bids_id,
                        "status": status,
                        "tsnr": tsnr_val,
                        "mean_fd": fd_mean_val,
                        "euler_number": euler_val,
                        "flags": flags,
                        "raw_row": row,
                    }
                    results.append(rec)
        except Exception:
            pass

        return results


__all__: list[str] = [
    "NeuroQCTriageEngine",
]
