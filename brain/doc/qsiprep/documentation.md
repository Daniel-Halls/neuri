### Overview of QSIPrep

**QSIPrep** is a BIDS-App built on the **Nipype** framework that automatically configures and executes preprocessing workflows for diffusion MRI (dMRI) data [1-3]. It is designed to handle virtually all \\(q\\)-space sampling schemes, including:
* **Single-shell DTI** [4, 5]
* **Multi-shell HARDI / NODDI** [4-6]
* **Cartesian grid Diffusion Spectrum Imaging (DSI)** [4, 5]
* **Compressed-sensing random DSI (CS-DSI)** [4, 5]

QSIPrep standardizes data across diverse scanning hardware and parameter choices into an interoperable format, leveraging tools from top neuroimaging software packages including **FSL**, **DSI Studio**, **DIPY**, **ANTs**, and **MRtrix3** [2].

---

### Preprocessing Stages

QSIPrep dynamically constructs a pipeline based on the provided BIDS inputs and user-specified command-line arguments [7, 8]. The pipeline progresses through five primary stages:

#### 1. Denoising & Gibbs Unringing
* **Image Denoising**: Applied directly to uninterpolated, raw dMRI series using either **MP-PCA** (`dwidenoise` from MRtrix3) or **Patch2Self** (from DIPY) [9-12].
* **Gibbs Ringing Removal**: Performed via `mrdegibbs` (MRtrix3) or `rpg` (TORTOISE, recommended for partial Fourier acquisitions) [9-11].
* **B1 Bias Correction & \\(b=0\\) Harmonization**: B1 bias field correction is applied via `dwibiascorrect` (or disabled via `--b1-biascorrect-stage none`), followed by intensity harmonization scaling \\(b=0\\) volumes across scans [10-13].
* **Execution Options**: By default, scans in the same warped space are denoised individually before concatenation, but users can specify `--denoise-after-combining` to denoise concatenated series [11, 14-16].

#### 2. Distortion Correction (Unwarping / SDC)
QSIPrep selects the appropriate Susceptibility Distortion Correction (SDC) method based on available fieldmap metadata (`IntendedFor`) [17, 18]:
* **PEPOLAR (Blip-up / Blip-down)**: Uses reverse phase-encoded \\(b=0\\) or dMRI scans processed with **FSL TOPUP** or **3dQwarp / DRBUDDI** [17, 19-21]. To optimize TOPUP runtime, QSIPrep selects the most representative \\(b=0\\) images per warped group using pairwise spatial correlation scores [21, 22].
* **Phase-Difference / Direct \\(B_0\\) Mapping**: Utilizes \\(B_0\\) fieldmap sequences (magnitude and phasediff/phase images) [18, 20].
* **Fieldmap-less SyN Estimation**: Estimates distortion using **ANTs SyN** based on an average fieldmap in MNI space when `--use-syn-sdc` is specified [18, 20, 23].

#### 3. Head Motion & Eddy Current Correction (HMC / ECC)
* **Shelled Acquisitions**: Uses **FSL `eddy`** to simultaneously model head motion, eddy current distortions, and susceptibility distortions (integrating TOPUP outputs) [23-26].
* **Non-Shelled Acquisitions (DSI / CS-DSI)**: Uses QSIPrep's **SHORELine** algorithm, which iteratively builds target reference images using **3dSHORE** or **MAPMRI** fits to estimate rigid motion parameters for Cartesian and random schemes [21, 27, 28].

#### 4. \\(b=0\\) to Anatomical Coregistration
* **Anatomical Processing**: Brain extraction and tissue segmentation on T1w or T2w anatomical reference images are performed using FreeSurfer's **SynthStrip** and **SynthSeg** [29, 30].
* **Coregistration**: The \\(b=0\\) reference image is rigidly registered to the skull-stripped anatomical image using `antsRegistration` to establish AC-PC alignment [26, 30, 31].
* **Intramodal Templates**: If multiple dMRI series or sessions exist, an intramodal \\(b=0\\) template can be constructed using ANTs template construction prior to T1w coregistration [26, 32].
* **DWI-Only Mode**: When `--dwi-only` is flagged, the pipeline skips T1w workflows and registers the \\(b=0\\) template directly to an AC-PC aligned template (e.g., MNI152NLin2009cAsym) [26, 33, 34].

#### 5. Resampling & Gradient Rotation
* **Single-Shot Transformation**: All spatial transformations (motion correction, eddy current correction, SDC, anatomical coregistration, and optional template normalization) are concatenated and applied in a **single resampling step** to minimize spatial smoothing and preserve high-frequency features [26, 33, 34].
* **Interpolation & Resolution**: Uses **Lanczos-windowed Sinc** interpolation (or **BSpline / Linear** if upsampling resolution by \\(>10\%\\)) to resample images to the isotropic voxel size set by `--output-resolution` [26, 33].
* **Gradient Rotation**: Rotates diffusion gradient vectors to reflect linear transformations, outputting updated **FSL-style `.bval` / `.bvec`** files, **MRtrix3 `.b`** gradient tables, and optional voxelwise `local_bvecs` [34, 35]. Outputs are oriented in **LPS+** coordinate space [36].

---

### Pipeline Outputs & Derivatives Layout

QSIPrep outputs are written to `<output_dir>/qsiprep/` and follow BIDS Derivatives conventions [14, 16, 37]:

1. **Visual QA Reports (HTML)**:
   * Generated as `<output_dir>/qsiprep/sub-<label>.html` [37].
   * Contains interactive reportlets, including animations of \\(q\\)-space sampling schemes before and after preprocessing, anatomical coregistration overlays, SDC unwarping checks, and framewise displacement/motion plots [37, 38].

2. **Preprocessed Imaging Data (`dwi/`)**:
   * **Preprocessed DWI**: `<source_entities>_space-ACPC_desc-preproc_dwi.nii.gz` [35]
   * **Brain Mask**: `<source_entities>_space-ACPC_desc-brain_mask.nii.gz` [35]
   * **\\(b=0\\) Reference Image**: `<source_entities>_space-ACPC_dwiref.nii.gz` [35]
   * **Gradient Files**: FSL-style `.bval` and `.bvec` files, as well as MRtrix3-compatible `.b` gradient tables [34, 35].
   * **Signal Model Maps**: Contrast-to-Noise Ratio (CNR) maps (`<source_entities>_space-ACPC_stat-cnr_desc-<label>_dwimap.nii.gz` and `.json`) [35].

3. **Confounds & Quantitative QA**:
   * **Timeseries TSV**: `<output_dir>/qsiprep/sub-<label>/func/<source_entities>_desc-confounds_timeseries.tsv` containing framewise displacement, motion estimates, and slice outlier indicators [22, 38].
   * **Quantitative Summary**: A single-line CSV file per subject summarizing motion metrics, coregistration quality, and image quality metrics (IQMs) [16, 37].

4. **Derivatives Directory Layout**:
```text
<output_dir>/qsiprep/
├── sub-<label>.html
├── sub-<label>/
│   ├── anat/
│   │   ├── sub-<label>_desc-brain_mask.nii.gz
│   │   ├── sub-<label>_desc-preproc_T1w.nii.gz
│   │   ├── sub-<label>_from-anat_to-ACPC_mode-image_xfm.mat
│   │   └── sub-<label>_from-ACPC_to-MNI152NLin2009cAsym_mode-image_xfm.h5
│   └── [ses-<label>/]
│       └── dwi/
│           ├── <source_entities>_space-ACPC_dwiref.nii.gz
│           ├── <source_entities>_space-ACPC_desc-brain_mask.nii.gz
│           ├── <source_entities>_space-ACPC_desc-preproc_dwi.nii.gz
│           ├── <source_entities>_space-ACPC_desc-preproc_dwi.bval
│           ├── <source_entities>_space-ACPC_desc-preproc_dwi.bvec
│           ├── <source_entities>_space-ACPC_desc-preproc_dwi.b
│           ├── <source_entities>_space-ACPC_stat-cnr_desc-<label>_dwimap.json
│           └── <source_entities>_space-ACPC_stat-cnr_desc-<label>_dwimap.nii.gz
```
*[14, 35-37, 39]*

---

### Required BIDS Directory Layout & Input Formatting

QSIPrep requires the input directory (`bids_dir`) to be a valid BIDS dataset containing at least one dMRI series [15, 40]:

#### 1. Standard Dataset Organization
```text
bids_root/
├── dataset_description.json
├── participants.tsv
└── sub-<label>/
    └── [ses-<label>/]
        ├── anat/
        │   ├── sub-<label>_T1w.nii.gz
        │   └── sub-<label>_T1w.json
        ├── dwi/
        │   ├── sub-<label>_dir-AP_dwi.nii.gz
        │   ├── sub-<label>_dir-AP_dwi.bval
        │   ├── sub-<label>_dir-AP_dwi.bvec
        │   └── sub-<label>_dir-AP_dwi.json
        └── fmap/
            ├── sub-<label>_dir-PA_epi.nii.gz
            ├── sub-<label>_dir-PA_epi.bval
            ├── sub-<label>_dir-PA_epi.bvec
            └── sub-<label>_dir-PA_epi.json
```
*[40-42]*

#### 2. Key Formatting Requirements & Caveats
* **Reverse Phase-Encoded Scans (`fmap/`)**: Short dMRI runs acquired for distortion correction (e.g., reverse phase-encoding \\(b=0\\) or low-\\(b\\) scans) **must** be placed in the `fmap/` directory with the `epi` suffix, rather than in `dwi/` [42-44]. The accompanying JSON sidecar in `fmap/` must contain the `IntendedFor` field pointing to the target dMRI file in `dwi/` using relative paths [42, 45-47]. If organized under `dwi/`, QSIPrep will incorrectly attempt to denoise and concatenate them as primary diffusion runs [44].
* **Complex-Valued Data**: Must be split into magnitude (`part-mag`) and phase (`part-phase`) NIfTI files [42, 48]. Furthermore, `.bval` and `.bvec` files must be explicitly retained for both magnitude and phase files (QSIPrep does not support BIDS inheritance for gradient files) [42, 46, 48]. Real/imaginary formatted data is not supported [48].
* **Participant Age Metadata**: For infant processing pipelines (`--infant`), age in months is automatically extracted from `<bids_root>/participants.tsv` or `<bids_root>/sub-<label>/sub-<label>_sessions.tsv` [49].

---