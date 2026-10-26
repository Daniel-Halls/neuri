---
name: bids-standard
description: BIDS validation, NIfTI/EDF metadata IO, zero-token PHI sanitization, and affine orientation checks.
triggers:
  - validate BIDS
  - inspect header
  - sanitize PHI
  - bids dataset
modalities:
  - T1w
  - T2w
  - bold
  - dwi
  - eeg
  - meg
---

# BIDS & Neuro File IO Skill

## 1. Core Responsibilities
- Validate dataset compliance against Brain Imaging Data Structure (BIDS) v1.9+.
- Extract structural, functional, diffusion, and electrophysiology headers without loading raw multi-gigabyte voxel arrays into LLM context.
- Enforce strict Protected Health Information (PHI) sanitization: strip free-text comment fields, patient names, dates of birth, recording dates, and device serial numbers.
- Verify 4x4 affine transformation matrices, preventing catastrophic left-right spatial flips (RAS+ neurological vs LPS+ radiological coordinates).

## 2. Directory Hierarchy & Entity Conventions
BIDS datasets must adhere to standard entity order:
```text
<dataset_root>/
├── dataset_description.json
├── participants.tsv
├── participants.json
└── sub-<label>/
    ├── [ses-<label>/]
    │   ├── anat/
    │   │   ├── sub-<label>[_ses-<label>]_T1w.nii.gz
    │   │   └── sub-<label>[_ses-<label>]_T1w.json
    │   ├── func/
    │   │   ├── sub-<label>[_ses-<label>]_task-<taskname>_bold.nii.gz
    │   │   └── sub-<label>[_ses-<label>]_task-<taskname>_bold.json
    │   ├── dwi/
    │   │   ├── sub-<label>[_ses-<label>]_dwi.nii.gz
    │   │   ├── sub-<label>[_ses-<label>]_dwi.bval
    │   │   ├── sub-<label>[_ses-<label>]_dwi.bvec
    │   │   └── sub-<label>[_ses-<label>]_dwi.json
    │   └── eeg/
    │       ├── sub-<label>[_ses-<label>]_task-<taskname>_eeg.edf
    │       ├── sub-<label>[_ses-<label>]_task-<taskname>_channels.tsv
    │       └── sub-<label>[_ses-<label>]_task-<taskname>_eeg.json
```

## 3. Orientation & Coordinate Conventions
- **NIfTI Coordinate Frame:** Always verify whether the affine matrix reflects **RAS+** (Right, Anterior, Superior) or **LPS+** (Left, Posterior, Superior).
- **Nibabel Canonical Reorientation:**
  ```python
  import nibabel as nib
  img = nib.load("sub-01_T1w.nii.gz")
  canonical_img = nib.as_closest_canonical(img)
  ```
- **qform / sform Validation:** Check `sform_code` and `qform_code`. A code of `1` indicates scanner anatomical; `2` indicates aligned to another file; `4` indicates MNI152 standard space.

## 4. Mandatory PHI Sanitization Gate
Before emitting any header summary to another agent or logging to the Blackboard:
1. Strip NIfTI `descrip`, `aux_file`, and `intent_name`.
2. Strip EDF/BDF subject ID (`patient_id`), recording comments, and date stamps.
3. Strip JSON sidecar fields: `InstitutionName`, `InstitutionalDepartmentName`, `DeviceSerialNumber`, `PatientName`, `PatientBirthDate`.
4. Return only the compact `<150` token `SanitizedNeuroHeader` JSON payload.
