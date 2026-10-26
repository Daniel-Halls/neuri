---
name: dwi-tractography
description: Diffusion MRI preprocessing, FSL eddy/topup, MRtrix3 constrained spherical deconvolution, and tractography connectome reconstruction.
triggers:
  - eddy correction
  - FOD estimation
  - tractography
  - diffusion preprocessing
modalities:
  - dwi
  - tractography
---

# Diffusion MRI & Tractography Skill

## 1. Core Responsibilities
- Preprocess multi-shell diffusion weighted imaging (DWI): MP-PCA denoising, Gibbs ringing removal, susceptibility distortion correction (FSL topup), and eddy-current / motion correction (FSL eddy).
- Validate b-value and b-vector gradient tables (enforcing unit length and coordinate system alignment with image volume orientation).
- Estimate multi-tissue Fiber Orientation Distributions (FOD) via Constrained Spherical Deconvolution (CSD) using MRtrix3.
- Generate probabilistic tractography streamlines (`tckgen`) and perform spherical-deconvolution informed filtering of tractograms (SIFT2).

## 2. Command Pipeline (MRtrix3 & FSL)

### A. Preprocessing & Distortion Correction
```bash
# 1. MP-PCA Denoising
dwidenoise ${INPUT_DWI} dwi_denoised.mif

# 2. Gibbs Ringing Removal
mrdegibbs dwi_denoised.mif dwi_degibbs.mif

# 3. FSL topup and eddy via dwifslpreproc
dwifslpreproc dwi_degibbs.mif dwi_preproc.mif \
    -rpe_none \
    -pe_dir AP \
    -readout_time 0.05 \
    -eddy_options " --repol --ol_nstd=3"
```

### B. Multi-Tissue CSD & Response Function
```bash
# Estimate response function for white matter, gray matter, and CSF
dwi2response dhollander dwi_preproc.mif \
    wm_response.txt gm_response.txt csf_response.txt

# Estimate fiber orientation distribution
dwi2fod msmt_csd dwi_preproc.mif \
    wm_response.txt wmfod.mif \
    gm_response.txt gmfod.mif \
    csf_response.txt csffod.mif \
    -mask brain_mask.mif
```

### C. Anatomically-Constrained Tractography (ACT) & SIFT2
```bash
# Generate 10M probabilistic streamlines with dynamic seeding
tckgen wmfod.mif 10M.tck \
    -act 5tt.mif \
    -backtrack \
    -crop_at_gmwmi \
    -maxlength 250 \
    -minlength 10 \
    -power 0.25 \
    -select 10M

# Filter streamlines to match diffusion signal
tcksift2 10M.tck wmfod.mif sift2_weights.txt -act 5tt.mif
```

## 3. Diffusion Quality Guardrails
- **B-Vector Flip Verification:** Inspect dec_fa or principal eigenvector maps to confirm that tract orientations in the corpus callosum are left-right (red), corticospinal tract is superior-inferior (blue), and cingulum is anterior-posterior (green).
- **Outlier Slices:** Confirm FSL eddy repol replaced fewer than 3% of total slices.
