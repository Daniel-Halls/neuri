"""Zero-dependency BIDS dataset layout scanner and validation engine.

Scans local and remote BIDS directory hierarchies, inventorying subjects,
sessions, modalities, verifying participants.tsv consistency, and validating
required JSON sidecar metadata fields for neuroimaging workflows.
"""

from collections.abc import Generator
import json
from pathlib import Path
import re
from typing import Any


class BIDSLayoutValidator:
    """Zero-dependency BIDS layout inspector and metadata validator.

    Parameters
    ------------
    None

    Returns
    --------
        BIDSLayoutValidator: BIDSLayoutValidator instance
            Constructed validator instance.
    """

    CORE_MODALITIES: tuple[str, ...] = (
        "anat",
        "func",
        "dwi",
        "fmap",
        "eeg",
        "meg",
        "ieeg",
    )

    REQUIRED_SIDECAR_KEYS: dict[str, list[str]] = {
        "func": ["RepetitionTime", "TaskName"],
        "dwi": ["PhaseEncodingDirection", "TotalReadoutTime"],
        "fmap": ["PhaseEncodingDirection"],
    }

    def scan_dataset(self, bids_root: Path) -> dict[str, Any]:
        """Scan directory tree and return complete inventory and diagnostics.

        Parameters
        ------------
        bids_root: Path
            Path to BIDS dataset root folder.

        Returns
        --------
            dict[str, Any]: dictionary object
                Comprehensive layout inventory, modality tallies, and validation issues.
        """
        resolved: Path = bids_root.resolve()
        errors: list[str] = []
        warnings: list[str] = []

        if not resolved.is_dir():
            errors.append(f"Specified path is not a directory: {resolved}")
            res: dict[str, Any] = {
                "valid": False,
                "dataset_name": "",
                "bids_version": "",
                "subject_count": 0,
                "subjects": [],
                "sessions_found": False,
                "modality_counts": {},
                "cohort_matrix": [],
                "missing_sidecars": [],
                "errors": errors,
                "warnings": warnings,
            }
            return res

        desc_file: Path = resolved / "dataset_description.json"
        dataset_name: str = "Unknown"
        bids_version: str = "Unknown"
        if desc_file.is_file():
            try:
                desc_data = json.loads(desc_file.read_text(encoding="utf-8"))
                dataset_name = str(desc_data.get("Name", "Unnamed"))
                bids_version = str(desc_data.get("BIDSVersion", "Unknown"))
            except Exception as exc:
                warnings.append(
                    f"Failed to parse dataset_description.json: {exc}"
                )
        else:
            errors.append("Missing required dataset_description.json at root.")

        part_file: Path = resolved / "participants.tsv"
        tsv_subjects: set[str] = set()
        if part_file.is_file():
            try:
                lines = part_file.read_text(encoding="utf-8").splitlines()
                if lines:
                    header = lines[0].split("\t")
                    sub_col = (
                        header.index("participant_id")
                        if "participant_id" in header
                        else -1
                    )
                    if sub_col >= 0:
                        for line in lines[1:]:
                            cols = line.split("\t")
                            if len(cols) > sub_col:
                                val = cols[sub_col].strip()
                                if val:
                                    tsv_subjects.add(val)
            except Exception as exc:
                warnings.append(f"Failed to parse participants.tsv: {exc}")
        else:
            warnings.append(
                "participants.tsv is missing; cohort demographics unavailable."
            )

        subject_dirs: list[Path] = sorted(
            [d for d in resolved.iterdir() if d.is_dir() and d.name.startswith("sub-")]
        )
        sub_names: list[str] = [d.name for d in subject_dirs]

        if not sub_names:
            errors.append(f"No sub-* subject directories found in {resolved}.")

        for s_dir in subject_dirs:
            if tsv_subjects and s_dir.name not in tsv_subjects:
                warnings.append(
                    f"Subject directory {s_dir.name} is missing from participants.tsv."
                )

        modality_counts: dict[str, int] = {m: 0 for m in self.CORE_MODALITIES}
        cohort_matrix: list[dict[str, Any]] = []
        missing_sidecars: list[dict[str, str]] = []
        has_sessions_any: bool = False

        for s_dir in subject_dirs:
            sub_id: str = s_dir.name
            sub_sessions: list[Path] = sorted(
                [d for d in s_dir.iterdir() if d.is_dir() and d.name.startswith("ses-")]
            )
            scan_dirs: list[Path] = sub_sessions if sub_sessions else [s_dir]
            if sub_sessions:
                has_sessions_any = True

            sub_mods: set[str] = set()
            t1w_found: bool = False
            bold_found: bool = False
            fmap_found: bool = False
            dwi_found: bool = False

            for s_parent in scan_dirs:
                for mod in self.CORE_MODALITIES:
                    mod_dir = s_parent / mod
                    if mod_dir.is_dir():
                        sub_mods.add(mod)
                        nii_files = [
                            f
                            for f in mod_dir.iterdir()
                            if f.name.endswith((".nii", ".nii.gz"))
                        ]
                        if nii_files:
                            modality_counts[mod] += len(nii_files)
                        if mod == "anat" and any("T1w" in f.name for f in nii_files):
                            t1w_found = True
                        if mod == "func" and any("bold" in f.name for f in nii_files):
                            bold_found = True
                        if mod == "fmap" and nii_files:
                            fmap_found = True
                        if mod == "dwi" and nii_files:
                            dwi_found = True

                        for n_file in nii_files:
                            stem = (
                                n_file.name[:-7]
                                if n_file.name.endswith(".nii.gz")
                                else n_file.name[:-4]
                            )
                            sidecar = mod_dir / f"{stem}.json"
                            if not sidecar.is_file():
                                missing_sidecars.append({
                                    "file": str(n_file.relative_to(resolved)),
                                    "reason": "Missing accompanying JSON sidecar",
                                })
                            else:
                                self._check_sidecar_keys(
                                    sidecar=sidecar,
                                    modality=mod,
                                    resolved_root=resolved,
                                    missing_sidecars=missing_sidecars,
                                )

            cohort_matrix.append({
                "subject": sub_id,
                "sessions": [s.name for s in sub_sessions],
                "modalities": sorted(sub_mods),
                "has_t1w": t1w_found,
                "has_bold": bold_found,
                "has_fmap": fmap_found,
                "has_dwi": dwi_found,
            })

        is_valid: bool = len(errors) == 0
        summary_result: dict[str, Any] = {
            "valid": is_valid,
            "dataset_name": dataset_name,
            "bids_version": bids_version,
            "subject_count": len(sub_names),
            "subjects": sub_names,
            "sessions_found": has_sessions_any,
            "modality_counts": modality_counts,
            "cohort_matrix": cohort_matrix,
            "missing_sidecars": missing_sidecars,
            "errors": errors,
            "warnings": warnings,
        }
        return summary_result

    def _check_sidecar_keys(
        self,
        sidecar: Path,
        modality: str,
        resolved_root: Path,
        missing_sidecars: list[dict[str, str]],
    ) -> None:
        """Inspect JSON sidecar for mandatory acquisition metadata keys.

        Parameters
        ------------
        sidecar: Path
            Path to JSON sidecar.
        modality: str
            BIDS modality folder name.
        resolved_root: Path
            Root BIDS directory path for relative reporting.
        missing_sidecars: list[dict[str, str]]
            Output list tracking sidecar deficiencies.

        Returns
        --------
            None: NoneType object
                Appends issues to missing_sidecars in place.
        """
        required_keys: list[str] = self.REQUIRED_SIDECAR_KEYS.get(modality, [])
        if not required_keys:
            return
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            for req_key in required_keys:
                if req_key not in payload or payload[req_key] is None:
                    missing_sidecars.append({
                        "file": str(sidecar.relative_to(resolved_root)),
                        "reason": f"Missing mandatory field '{req_key}'",
                    })
        except Exception as err:
            missing_sidecars.append({
                "file": str(sidecar.relative_to(resolved_root)),
                "reason": f"Corrupt JSON sidecar ({err})",
            })

    def validate_preflight_cohort(
        self,
        bids_root: Path,
        pipeline_name: str = "fmriprep",
        target_subjects: list[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify pre-flight cohort readiness for BIDS Apps execution.

        Parameters
        ------------
        bids_root: Path
            Root BIDS dataset path.
        pipeline_name: str
            Name of pipeline to validate against (fmriprep, qsiprep, xcp_d).
            Defaults to 'fmriprep'.
        target_subjects: list[str] | None
            Subset of subjects to inspect. Defaults to None (all).

        Returns
        --------
            tuple[bool, list[str]]: tuple object
                Pair of (is_ready, list_of_blocking_reasons).
        """
        scan: dict[str, Any] = self.scan_dataset(bids_root)
        reasons: list[str] = []

        if not scan["valid"]:
            reasons.extend(scan["errors"])
            return False, reasons

        cohort: list[dict[str, Any]] = scan.get("cohort_matrix", [])
        if target_subjects:
            cohort = [c for c in cohort if c["subject"] in target_subjects]

        if not cohort:
            reasons.append("No matching subjects found in cohort.")
            return False, reasons

        pipe: str = pipeline_name.lower()
        for row in cohort:
            sub = row["subject"]
            if not row["has_t1w"]:
                reasons.append(
                    f"Subject {sub} lacks anatomical T1w reference image."
                )
            if pipe in ("fmriprep", "xcp_d"):
                if not row["has_bold"]:
                    reasons.append(
                        f"Subject {sub} lacks functional BOLD image "
                        f"for {pipeline_name}."
                    )
                if not row["has_fmap"]:
                    reasons.append(
                        f"Subject {sub} lacks fieldmap (fmap); "
                        f"distortion correction may be skipped."
                    )
            elif pipe in ("qsiprep",):
                if not row["has_dwi"]:
                    reasons.append(
                        f"Subject {sub} lacks diffusion DWI image for QSIPrep."
                    )

        has_critical_blockers: bool = any(
            "lacks anatomical" in r
            or "lacks functional" in r
            or "lacks diffusion" in r
            for r in reasons
        )
        return not has_critical_blockers, reasons


__all__: list[str] = [
    "BIDSLayoutValidator",
]
