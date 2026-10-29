### 1. Overview of HCP Pipelines & Pipeline Functions

The Human Connectome Project (HCP) minimal preprocessing pipelines bring structural, functional, and diffusion MRI data into a unified, automated framework [1, 2]. The core pipeline suite is organized into structural, functional, and diffusion streams, along with downstream surface registration and denoising modules [3, 4]:

#### Structural Preprocessing Pipelines
* **PreFreeSurfer (`hcp_pre_freesurfer`)**: Preprocesses high-resolution T1-weighted (T1w) and T2-weighted (T2w) structural images [2, 5]. Its primary functions include gradient distortion correction, averaging multiple structural scans (if available), AC-PC alignment (rigidly aligning native space to MNI axes), FNIRT-based brain extraction, T2w-to-T1w image registration, readout distortion correction, bias field (B1) correction, and linear + non-linear registration to MNI152 template space [5, 6].
* **FreeSurfer (`hcp_freesurfer`)**: Runs an optimized version of FreeSurfer’s `recon-all` stream customized for high-resolution data [7-9]. It downsamples T1w images to 1 mm isotropic resolution via spline interpolation, performs subcortical structure segmentation, reconstructs white matter (inner) and pial (outer) cortical surface meshes, conducts surface inflation and spherical mapping, fixes topological defects, uses the T2w image to fine-tune pial surface placement, and generates subject-specific cortical parcellations (e.g., Desikan-Killiany and Destrieux atlases) [7-10].
* **PostFreeSurfer (`hcp_post_freesurfer`)**: Converts FreeSurfer volume and surface outputs into NIfTI and GIFTI formats, generates full-resolution cortical ribbon volumes, and resamples surfaces and metric features onto standardized Left-Right symmetric mesh atlases (`fs_LR164k` and `fs_LR32k`) [11-14]. It computes surface-mapped \\(T1w/T2w\\) ratio myelin maps, performs initial surface registration (`MSMSulc`), creates dense scalar CIFTI files (`.dscalar.nii`), and sets up Connectome Workbench specification (`.spec`) files [11, 13-15].

#### Functional Preprocessing Pipelines
* **fMRIVolume (`hcp_fmri_volume`)**: Preprocesses 4D BOLD functional time series in volumetric space [16, 17]. Functions include gradient distortion correction, FLIRT-based motion correction (aligned to a single-band reference/scout image), EPI susceptibility distortion correction (via TOPUP spin-echo field maps or gradient-echo field maps), optional slice timing correction, coregistration of BOLD to T1w structural space using Boundary-Based Registration (BBR), a single concatenated spatial transformation/resampling into MNI152 space, intensity normalization, and B1 bias field removal [16-19].
* **fMRISurface (`hcp_fmri_surface`)**: Maps volumetric preprocessed fMRI data into the grayordinates spatial coordinate system [20-22]. It samples BOLD time series along the cortical ribbon between the white matter and pial surfaces (using "goodvoxels" masking to exclude local intensity anomalies), dilates surface samples to fill gaps, resamples cortical data onto the 32k `fs_LR` surface mesh, combines cortical surface time series with subcortical MNI volume voxels, and outputs dense time series CIFTI files (`.dtseries.nii`) [20-22].

#### Diffusion Preprocessing Pipeline
* **Diffusion (`hcp_diffusion`)**: Preprocesses diffusion-weighted MRI (dMRI) datasets acquired with opposite phase-encoding directions [23-25]. Steps include \\(b0\\) intensity normalization, calculation of B0 susceptibility distortions using opposite phase-encoding \\(b0\\) pairs (`topup`), modeling eddy current distortions and head motion across all volumes (`eddy`), gradient distortion correction, BBR registration of \\(b0\\) to native T1w structural space, rotation of \\(b\\)-vectors and gradient deviation tensors, and final resampling into 1.25 mm native structural space [23, 24, 26].

#### Downstream & Advanced Pipelines
* **ICA-FIX (`hcp_icafix`, `hcp_post_fix`, `hcp_reapply_fix`)**: Automatically classifies ICA components into signal and noise, regressing out noise components to clean 4D fMRI time series [27-29].
* **MSMAll / DeDriftAndResample (`hcp_msmall`, `hcp_dedrift_and_resample`)**: Performs multi-modal surface matching using resting-state functional connectivity, resting-state networks, cortical topography, and myelin maps to achieve alignment beyond sulcal folding [30, 31].

---

### 2. Workflow Stages and Pipeline Execution Order

The minimal preprocessing workflow is structured sequentially across modalities [3, 4, 32]:

```
[Raw Data Onboarding & Mapping]
              │
              ▼
    1. PreFreeSurfer Pipeline
              │
              ▼
      2. FreeSurfer Pipeline
              │
              ▼
    3. PostFreeSurfer Pipeline ───► [Diffusion Pipeline]
              │
              ▼
    4. fMRIVolume Pipeline
              │
              ▼
    5. fMRISurface Pipeline
              │
              ▼
   6. Downstream (ICA-FIX ──► MSMAll ──► Task fMRI / tICA)
```

1. **Structural Processing Stage**: `PreFreeSurfer` \\(\rightarrow\\) `FreeSurfer` \\(\rightarrow\\) `PostFreeSurfer` [32-34].
2. **Functional Processing Stage**: Depends on structural outputs. Runs `fMRIVolume` \\(\rightarrow\\) `fMRISurface` \\(\rightarrow\\) `ICA-FIX` \\(\rightarrow\\) `MSMAll` \\(\rightarrow\\) `Task fMRI Analysis` or `Temporal ICA` [32, 35-38].
3. **Diffusion Processing Stage**: Depends on `PreFreeSurfer` outputs for T1w structural space alignment [24, 39].

---

### 3. Pipeline Outputs

The HCP pipelines generate standard surface, volume, and grayordinate file formats [1, 40]:

* **CIFTI Files (`.nii` / `.dtseries.nii`, `.dscalar.nii`, `.dlabel.nii`, `.dconn.nii`)**: CIFTI is a container format based on NIfTI-2 that uses the **grayordinate** spatial coordinate system, combining surface vertices for the cerebral cortex with volumetric voxels for subcortical structures [1, 11, 40, 41].
  * **`.dtseries.nii`**: Dense time series (e.g., preprocessed fMRI runs) [21, 41].
  * **`.dscalar.nii`**: Dense scalar maps (e.g., myelin maps, cortical thickness, curvature, sulcal depth) [15, 42].
  * **`.dlabel.nii`**: Dense label maps for cortical/subcortical parcellations [43].
  * **`.dconn.nii`**: Dense functional or structural connectivity matrices [44].
* **GIFTI Surfaces (`.gii`)**: Contains surface geometry topology (`.surf.gii`) and surface metrics/shape data (`.func.gii`, `.shape.gii`, `.label.gii`) separated by hemisphere (Left `L` and Right `R`) [15, 45, 46]. Topologies generated include `white`, `midthickness`, `pial`, `inflated`, `very_inflated`, `sphere`, `sphere.reg`, and `sphere.rot` [45, 47, 48].
* **fs_LR Meshes**: Left-Right symmetric atlas spaces developed for surface-based alignment [11]:
  * **`164k_fs_LR`**: High-resolution mesh (~164,000 vertices per hemisphere) corresponding to structural resolution data [11, 49].
  * **`32k_fs_LR`**: Standard low-resolution mesh (~32,492 vertices per hemisphere) used for resampling fMRI, dMRI, myelin maps, and functional connectivity to optimize computational efficiency and file size [11, 49, 50].
* **Myelin Maps**: \\(T1w/T2w\\) signal intensity ratio maps mapped onto cortical surfaces, providing in vivo estimates of cortical myelination [12, 51]. Outputs include uncorrected `MyelinMap`, spatially smoothed `SmoothedMyelinMap`, bias-corrected `MyelinMap_BC`, and smoothed bias-corrected `SmoothedMyelinMap_BC` [12, 15].

---

### 4. Required File Structures and Acquisition Modes

#### Directory Layout (QuNex / HCP Framework)
HCP processing relies on a strict directory structure for inputs, working files, and results [52-54]:

```
<study_folder>/
├── processing/                   # Batch files (batch.txt), logs, parameter files
└── sessions/
    └── <session_id>/
        ├── nii/                  # Raw NIfTI converted images
        ├── session_hcp.txt       # Session pipeline mapping file
        └── hcp/<session_id>/     # Main HCP session root
            ├── unprocessed/      # Input raw scans organized by modality (hcpls structure)
            │   ├── T1w/
            │   ├── T2w/
            │   ├── BOLD_1/
            │   └── Diffusion/
            ├── T1w/              # Native structural outputs, FreeSurfer directory
            ├── T2w/              # Native T2w outputs
            ├── MNINonLinear/     # Final MNI standard space outputs
            │   ├── fsaverage_LR32k/  # 32k fs_LR mesh surfaces & maps
            │   ├── Native/           # Resampled native surfaces
            │   └── Results/          # BOLD run results (e.g. BOLD_1/) & CIFTI files
            └── Diffusion/        # Diffusion outputs (eddy/, topup/, data/)
```

#### Folder Structure Variants (`hcpya` vs `hcpls`)
* **`hcpls` (HCP Life Span - Default)**: Source input files are stored inside a joint `unprocessed/` subfolder within the session root `hcp/<session_id>/` [55-57].
* **`hcpya` (HCP Young Adult)**: Source input files are stored in individual modality folders directly inside the main `hcp/<session_id>/` folder, parallel to working directories, using `fncb` and `strc` tags [55-57].

#### Processing Modes (`HCPStyleData` vs `LegacyStyleData`)
* **`HCPStyleData`**: Enforces strict compliance with full HCP acquisition guidelines [58, 59]:
  * Requires high-resolution T1w **and** T2w (or FLAIR) structural scans [59].
  * Requires spin-echo field maps (opposite phase-encoding pairs) for BOLD EPI distortion correction [59].
  * Requires multiband fMRI acquisitions [59].
  * Requires diffusion MRI acquired in opposite phase-encoding pairs [59].
* **`LegacyStyleData`**: Relaxes strict acquisition requirements to enable processing of clinical or legacy datasets that do not satisfy full HCP specifications [58, 60]:
  * Allows processing without T2w structural images (`--hcp_t2=NONE`) [61, 62].
  * Allows BOLD processing without field maps or using legacy gradient-echo field maps [58, 60].
  * Enables optional slice timing correction for single-band fMRI [58, 60, 63].
  * Allows processing single phase-encoding direction diffusion scans (`DiffusionLegacy`) [25, 64].

---