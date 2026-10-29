**fMRIPrep** is an automated, robust neuroimaging preprocessing pipeline developed under the **NiPreps (NeuroImaging PREProcessing toolS)** framework for task-based and resting-state functional MRI (fMRI) [1, 2].

---

### 1. Overview and Core Principles

* **Purpose & Minimal Preprocessing Scope**: fMRIPrep performs **minimal preprocessing**, which is explicitly defined as motion correction, susceptibility field unwarping, spatial normalization, intensity non-uniformity (bias field) correction, and brain extraction [3, 4]. It intentionally **omits spatial smoothing or temporal denoising** so that the preprocessed output remains agnostic to downstream analysis choices [5].
* **Software Integration**: Rather than re-inventing neuroimaging algorithms, fMRIPrep integrates specialized tools from established neuroimaging suites, including **FSL** (MCFLIRT, FAST), **ANTs** (N4BiasFieldCorrection, antsBrainExtraction, antsRegistration), **FreeSurfer** (recon-all, bbregister), **AFNI** (3dTShift), and **Nilearn** [3, 4, 6].
* **Core Principles**:
  1. **Robustness**: Dynamically adapts its pipeline to variations in acquisition protocols, scanner manufacturers, and available fieldmaps or distortion correction scans [7, 8].
  2. **Ease of Use**: Relies on the **BIDS standard** to automatically parse dataset structure and metadata, reducing manual parameter tuning to a minimum [7, 8].
  3. **"Glass Box" Philosophy**: Automatically generates comprehensive visual HTML quality control reports for each subject, ensuring visual inspection and operational transparency [9, 10].

---

### 2. Required Input File Structures (BIDS Layout)

fMRIPrep strictly requires input data formatted according to the **Brain Imaging Data Structure (BIDS)** specification [7, 11].

* **Top-Level Dataset Root**:
  * `dataset_description.json`: Mandatory JSON metadata file specifying BIDS version and dataset details [12, 13].
  * `README`: High-level text/Markdown description of the study [12, 14].
  * `participants.tsv` (optional): Tabular demographic and participant-level metadata [15].
  * Top-level folders such as `code/`, `derivatives/`, `sourcedata/`, and `phenotype/` [16].
* **Subject & Session Hierarchy**:
  * Data must be housed within participant directories (`sub-<label>/`), with an optional session level (`ses-<label>/`) for multi-visit studies [17, 18].
* **Modality / Datatype Subdirectories**:
  * `anat/`: Structural MRI scans—at least one T1-weighted image (`sub-<label>_T1w.nii.gz`), along with optional T2-weighted (`_T2w.nii.gz`) or FLAIR volumes [19, 20].
  * `func/`: 4D BOLD functional series (`sub-<label>_task-<label>_bold.nii.gz`) and an accompanying JSON sidecar (`*_bold.json`) containing compulsory metadata fields, specifically `RepetitionTime` (TR) and `SliceTiming` array [19, 21].
  * `fmap/` (optional): Fieldmap acquisitions (e.g., phase-encoding reversed EPI pairs, spiral fieldmaps) used for susceptibility distortion correction [22, 23].

---

### 3. Processing Stages

#### A. Anatomical Processing Workflow
1. **Conformation & Reference Template**: Conforms input T1w images to RAS orientation and a uniform voxel grid. If multiple T1w images are present, an unbiased reference template is constructed [24, 25].
2. **Intensity Non-Uniformity (INU) Correction**: Bias field correction is performed on the T1w reference using ANTs `N4BiasFieldCorrection` [26, 27].
3. **Brain Extraction (Skull-Stripping)**: Skull-strips the T1w volume using ANTs `antsBrainExtraction.sh` with the OASIS30ANTs template [26, 27].
4. **Tissue Segmentation**: Segments the brain into Cerebrospinal Fluid (CSF), White Matter (WM), and Gray Matter (GM) using FSL `FAST` [26, 27].
5. **Spatial Normalization**: Performs non-linear volume registration via ANTs `antsRegistration` to map the skull-stripped T1w volume to a standard template space (default: `MNI152NLin2009cAsym` via TemplateFlow) [26, 27].

#### B. Surface Reconstruction Workflow
1. **FreeSurfer Cortical Surface Reconstruction**: Reconstructs cortical surface meshes using FreeSurfer's `recon-all` (unless disabled with `--fs-no-reconall`) [26, 28]. Generates native surface meshes (`white`, `pial`, `midthickness`) and spherical registration targets (`sphere.reg`, `fsLR`) [29, 30].
2. **Brain Mask Refinement**: Refines the initial ANTs brain mask by reconciling ANTs and FreeSurfer cortical GM segmentations via a custom Mindboggle variation [26, 31].
3. **Surface Morphometrics**: Calculates vertex-wise cortical thickness, curvature, and sulcal depth maps exported as GIFTI shape files (`.shape.gii`) and CIFTI dscalar files (`.dscalar.nii`) [32].

#### C. Functional Processing Workflow
1. **BOLD Reference Estimation**: Generates a BOLD reference volume and brain mask by detecting and averaging non-steady-state (dummy) volumes [33, 34].
2. **Slice Timing Correction (STC)**: Realigns slice acquisition times to the TR midpoint using AFNI `3dTShift` if `SliceTiming` metadata is provided [33, 35].
3. **Head Motion Correction (HMC)**: Realigns 4D BOLD volumes to the BOLD reference using FSL `MCFLIRT`, generating 6 rigid-body motion parameters per time point before temporal filtering [33, 36].
4. **Susceptibility Distortion Correction (SDC)**: Calculates geometric unwarping transforms if fieldmaps are provided in `fmap/` (or estimates fieldmap-less SyN distortion correction if requested) [22, 33].
5. **EPI-to-T1w Coregistration**: Coregisters the BOLD reference to the subject's T1w anatomical image using FreeSurfer `bbregister` (Boundary-Based Registration with 6 degrees of freedom) [33, 37].
6. **Single-Step Composite Resampling**: Concatenates motion correction matrices, SDC warps, BOLD-to-T1w affine transforms, and T1w-to-template non-linear warps into a single composite transformation. Resamples the BOLD time series in **one single interpolation step** using ANTs `antsApplyTransforms` (configured with Lanczos interpolation for volumetric data) or `mri_vol2surf` (for surface mapping) to minimize spatial blurring [38, 39].

---

### 4. Outputs of the Pipeline

#### A. Visual Quality Assessment (QA) Reports
* Standalone HTML report (`sub-<label>.html`) generated per subject [5, 40, 41].
* Includes visual diagnostic figures: input T1w conformation, brain mask / tissue segmentation overlays, FreeSurfer surface reconstructions, `bbregister` EPI-to-T1w alignment, CompCor cumulative variance plots, and BOLD carpetplots (summarizing voxelwise time series grouped by cortical GM, deep GM, WM/CSF, and brain-edge "crown" alongside Framewise Displacement and DVARS traces) [24, 37, 42-45].

#### B. Derivatives Folder Layout
Outputs conform to BIDS Derivatives standards (`--output-layout bids`, default in v21+) [40, 46]:

```text
<output_dir>/
├── dataset_description.json
├── logs/
├── sub-<label>.html
├── sub-<label>/
│   ├── anat/
│   │   ├── sub-<label>_desc-brain_mask.nii.gz
│   │   ├── sub-<label>_desc-preproc_T1w.nii.gz
│   │   ├── sub-<label>_space-MNI152NLin2009cAsym_desc-preproc_T1w.nii.gz
│   │   ├── sub-<label>_hemi-[LR]_[white|pial|midthickness].surf.gii
│   │   ├── sub-<label>_hemi-[LR]_[thickness|curv|sulc].shape.gii
│   │   └── sub-<label>_from-orig_to-MNI152NLin2009cAsym_mode-image_xfm.h5
│   └── func/
│       ├── sub-<label>_task-<task>_desc-brain_mask.nii.gz
│       ├── sub-<label>_task-<task>_desc-hmc_boldref.nii.gz
│       ├── sub-<label>_task-<task>_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz
│       ├── sub-<label>_task-<task>_hemi-[LR]_space-fsaverage_bold.func.gii
│       ├── sub-<label>_task-<task>_space-fsLR_den-91k_bold.dtseries.nii (if --cifti-output enabled)
│       ├── sub-<label>_task-<task>_desc-confounds_timeseries.tsv
│       └── sub-<label>_task-<task>_desc-confounds_timeseries.json
└── sourcedata/
    └── freesurfer/
        └── sub-<label>/
```
*(Note: In `--output-layout legacy`, derivatives are nested inside `<output_dir>/fmriprep/sub-<label>/` and `<output_dir>/freesurfer/` [47]).*

#### C. Confounds Time-Series
Generated for each BOLD run as a TSV table (`*_desc-confounds_timeseries.tsv`) and JSON sidecar (`*_desc-confounds_timeseries.json`) [48, 49]. Extracted regressors include:
* **Head Motion Parameters**: 6 rigid-body parameters (`trans_x/y/z`, `rot_x/y/z`), temporal derivatives, quadratic terms (24 motion parameters total), Framewise Displacement (`framewise_displacement`), and standardized/non-standardized DVARS (`dvars`, `std_dvars`) [38, 50].
* **Global Signals**: Mean BOLD signals extracted from whole-brain (`global_signal`), CSF (`csf`), and white matter (`white_matter`) masks [38].
* **CompCor Components**:
  * **aCompCor** (Anatomical CompCor): Principal components extracted from high-pass filtered BOLD signals in eroded anatomical CSF and WM masks (excluding GM voxels) [38].
  * **tCompCor** (Temporal CompCor): Principal components extracted from the top 2% most variable voxels across time within the brain mask [38].
  * Components explaining the top 50% cumulative variance are retained by default [45].
* **Cosine Basis Set**: Discrete Cosine Transform (`cosine_XX`) basis regressors for high-pass filtering (128s cutoff) [38, 50].
* **Outliers**: Regressors indicating non-steady-state initial volumes (`non_steady_state_XX`) and motion spikes exceeding FD/DVARS thresholds [38, 50].
* **Brain-Edge / Crown Regressors**: Regressors derived from voxels along the outer boundary ("crown") of the brain [45, 51].

#### D. Transformed BOLD Outputs
Preprocessed BOLD time series resampled into requested target spaces (`--output-spaces`):
* **Native T1w Space**: Volumetric BOLD in individual anatomical space (`space-T1w`) [33, 52].
* **Standard Volumetric Space**: Resampled volumetric BOLD in MNI template space (`space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz`) [33, 53].
* **Surface GIFTI**: BOLD time-series resampled to FreeSurfer surfaces (e.g., `fsaverage` or `fsnative` GIFTI files) [38, 52].
* **CIFTI Dense Time-Series**: CIFTI-2 grayordinate time series (`*_bold.dtseries.nii`) sampled onto the `fsLR` mesh (91k or 170k density) combining subcortical volumes and cortical surface data [30, 48, 54].