---
name: neuroimaging-preproc
description: Structural MRI preprocessing, brain extraction, FreeSurfer cortical reconstruction, and ANTs spatial normalization.
triggers:
  - brain extraction
  - surface reconstruction
  - spatial normalization
  - structural preprocessing
modalities:
  - T1w
  - T2w
---

# Structural MRI Preprocessing Skill

## 1. Core Responsibilities
- Execute high-fidelity skull stripping / brain extraction using FSL BET, HD-BET, or ANTs BrainExtraction.
- Perform intensity non-uniformity correction (N4 bias field correction).
- Run spatial normalization and non-linear registration to standard stereotaxic templates (TemplateFlow `MNI152NLin2009cAsym` or `MNI152NLin6Asym`).
- Reconstruct cortical surfaces and subcortical segmentations via FreeSurfer (`recon-all`).

## 2. Command Templates & Standard Flags

### A. FSL BET (Brain Extraction Tool)
```bash
# Robust brain extraction with bias reduction and center-of-gravity estimation
bet ${INPUT_T1W} ${OUTPUT_BRAIN} -f 0.45 -g 0 -R -m
```

### B. ANTs N4 Bias Field Correction
```bash
N4BiasFieldCorrection \
    -d 3 \
    -i ${INPUT_T1W} \
    -o [${CORRECTED_T1W},${BIAS_FIELD}] \
    -c [50x50x30x20,1e-6] \
    -s 2 \
    -b [200]
```

### C. ANTs Symmetric Diffeomorphic Registration (SyN)
```bash
antsRegistrationSyN.sh \
    -d 3 \
    -f ${TEMPLATE_MNI152} \
    -m ${CORRECTED_BRAIN} \
    -o ${OUTPUT_PREFIX} \
    -n 8 \
    -t s
```

### D. FreeSurfer Cortical Reconstruction
```bash
recon-all \
    -subject sub-${SUB_ID} \
    -i ${INPUT_T1W} \
    -all \
    -sd ${SUBJECTS_DIR} \
    -parallel \
    -threads 8
```

## 3. Spatial Alignment & Orientation Guardrails
- **Pre-Registration Check:** Verify that both source volume and standard template share RAS+ orientation before non-linear warping.
- **Affine Check:** Ensure the affine determinant is positive (preserving right-handed parity) to prevent mirrored hemispatial outputs.
- **QA Snapshot:** Generate 3-slice orthographic slices (Axial, Coronal, Sagittal) overlaying the brain mask or MNI template edges onto the skull-stripped anatomy.
