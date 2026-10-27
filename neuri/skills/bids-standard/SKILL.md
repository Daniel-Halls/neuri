---
name: bids-standard
description: BIDS validation, NIfTI/EDF metadata IO, zero-token PHI sanitization, fmap IntendedFor mapping, and affine orientation checks.
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

* Validate dataset compliance against Brain Imaging Data Structure (BIDS) v1.9+.
* Extract structural, functional, diffusion, fieldmap, and electrophysiology headers without loading raw multi-gigabyte voxel arrays into LLM context.
* Enforce strict Protected Health Information (PHI) sanitization: strip free-text comment fields, patient names, dates of birth, recording dates, and device serial numbers.
* Verify fieldmap associations (fmap) and IntendedFor linkages across functional (bold) and diffusion (dwi) scans.
* Verify 4x4 affine transformation matrices, preventing catastrophic left-right spatial flips (RAS+ neurological vs LPS+ radiological coordinates).

## 2. Directory Hierarchy & Entity Conventions

BIDS datasets must adhere to standard entity order and subdirectory structures:

<dataset_root>/
├── dataset_description.json
├── participants.tsv
├── participants.json
└── sub-<label>/
    ├── [ses-<label>/]
    │   ├── anat/
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_rec-<label>][_run-<index>]_T1w.nii.gz
    │   │   └── sub-<label>[_ses-<label>][_acq-<label>][_rec-<label>][_run-<index>]_T1w.json
    │   ├── func/
    │   │   ├── sub-<label>[_ses-<label>]_task-<taskname>[_acq-<label>][_rec-<label>][_dir-<label>][_run-<index>][_echo-<index>]_bold.nii.gz
    │   │   ├── sub-<label>[_ses-<label>]_task-<taskname>[_acq-<label>][_rec-<label>][_dir-<label>][_run-<index>][_echo-<index>]_events.tsv
    │   │   └── sub-<label>[_ses-<label>]_task-<taskname>[_acq-<label>][_rec-<label>][_dir-<label>][_run-<index>][_echo-<index>]_bold.json
    │   ├── dwi/
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_dir-<label>][_run-<index>]_dwi.nii.gz
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_dir-<label>][_run-<index>]_dwi.bval
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_dir-<label>][_run-<index>]_dwi.bvec
    │   │   └── sub-<label>[_ses-<label>][_acq-<label>][_dir-<label>][_run-<index>]_dwi.json
    │   ├── fmap/
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_dir-<label>][_run-<index>]_epi.nii.gz
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_dir-<label>][_run-<index>]_epi.json
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_magnitude1.nii.gz
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_magnitude2.nii.gz
    │   │   ├── sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phasediff.nii.gz
    │   │   └── sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phasediff.json
    │   └── eeg/
    │       ├── sub-<label>[_ses-<label>]_task-<taskname>[_run-<index>]_eeg.edf
    │       ├── sub-<label>[_ses-<label>]_task-<taskname>[_run-<index>]_channels.tsv
    │       └── sub-<label>[_ses-<label>]_task-<taskname>[_run-<index>]_eeg.json


### Mandatory Entity Key Ordering

When multiple entity keys are used in a filename, they MUST follow strict BIDS precedence: sub-<label> → ses-<label> → task-<label> → acq-<label> → ce-<label> → rec-<label> → dir-<label> → run-<index> → echo-<index> → part-<label> → <suffix>

## 3. Fieldmap (fmap) Sidecar & IntendedFor Rules

Fieldmap JSON sidecars under fmap/ must define which anatomical, functional, or diffusion runs they correct:

### 1. IntendedFor Targeting: Use standard BIDS URIs or relative paths from the participant root:

{
  "PhaseEncodingDirection": "j-",
  "TotalReadoutTime": 0.05,
  "IntendedFor": [
    "bids::sub-01/ses-01/func/sub-01_ses-01_task-rest_dir-AP_run-01_bold.nii.gz",
    "bids::sub-01/ses-01/func/sub-01_ses-01_task-rest_dir-AP_run-02_bold.nii.gz"
  ]
}


#### 1. Required Distortion Parameters:
  * EPI distortion fieldmaps (*_epi.json) MUST contain PhaseEncodingDirection (e.g., j, j-, i, i-) and TotalReadoutTime (in seconds).
  * Phase-difference fieldmaps (*_phasediff.json) MUST specify EchoTime1 and EchoTime2.
#### 2. Identifier Linking (B0FieldIdentifier / B0FieldSource):
  * Fieldmaps can specify B0FieldIdentifier (e.g., "pepolar_fmap0"), and target functional/diffusion sidecars specify matching B0FieldSource.

## 4. Orientation & Coordinate Conventions

* NIfTI Coordinate Frame: Verify whether the affine matrix reflects RAS+ (Right, Anterior, Superior) or LPS+ (Left, Posterior, Superior).
* Nibabel Canonical Reorientation:

import nibabel as nib
img = nib.load("sub-01_ses-01_task-rest_run-01_bold.nii.gz")
canonical_img = nib.as_closest_canonical(img)


* qform / sform Validation: Check sform_code and qform_code. A code of 1 indicates scanner anatomical; 2 indicates aligned to another file; 4 indicates MNI152 standard space.

## 5. Mandatory PHI Sanitization Gate

Before emitting any header summary to another agent or logging to the Blackboard:

1. Strip NIfTI descrip, aux_file, and intent_name.
2. Strip EDF/BDF subject ID (patient_id), recording comments, and date stamps.
3. Strip JSON sidecar fields: InstitutionName, InstitutionalDepartmentName, DeviceSerialNumber, PatientName, PatientBirthDate.
4. Return only the compact <150 token SanitizedNeuroHeader JSON payload.
