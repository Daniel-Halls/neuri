**AFNI** (**A**nalysis of **F**unctional **N**euro**I**mages) is a leading, open-source software suite consisting of C, Python, and R programs, as well as shell scripts, designed for processing, analyzing, and visualizing multi-modal neuroimaging data [1, 2].

---

### 1. Overview of What AFNI Does

AFNI provides a start-to-finish environment for processing multiple MRI modalities, spanning individual subject level and group statistics [2, 3]:

* **Anatomical & Structural MRI**: Functions for brain extraction/skull-stripping (e.g., `sswarper2`, `@SSwarper`, `3dSkullStrip`), uniformization (`3dUnifize`), spatial normalization to standard templates, and anatomical-to-functional co-registration [4-7].
* **Functional MRI (fMRI)**: Full pipeline support for task-based (block and event-related designs), resting-state, and naturalistic paradigm fMRI across single-echo and multi-echo acquisitions [6, 8].
* **Diffusion Weighted Imaging (DWI)**: Tensor estimation, High Angular Resolution Diffusion Imaging (HARDI) modeling, and tractography visualization using the integrated **FATCAT** toolbox [6, 9].
* **Surface Analysis (SUMA)**: Integrated via **SUMA** (**SU**rface **MA**pping) to allow rendering of 3D cortical surfaces, mapping volumetric data onto surfaces, and simultaneously displaying slice, graph time series, volume, surface, and tractography views with real-time links [10-13].
* **Statistical Analysis**: General Linear Modeling (GLM) via `3dDeconvolve`, temporal autocorrelation modeling with `3dREMLfit`, and group-level statistical tools such as `3dttest++`, `3dMEMA`, `3dANOVA`, `3dMVM`, and `3dLME` [14-18].
* **Quality Control & Visualization**: Interactive data exploration (`afni`, `suma`), automated image generation (`@chauffeur_afni`), and single-subject Quality Control HTML reports (`open_apqc.py`) [19-23].

---

### 2. `afni_proc.py` Pipeline Processing Blocks

`afni_proc.py` is AFNI's primary command-line tool for generating and executing reproducible, single-subject fMRI preprocessing and regression pipelines [4, 24, 25]. Pipelines are constructed by combining modular **processing blocks** via the `-blocks` argument [4, 25, 26]:

* **`tcat`**: Truncates initial unsteady-state time points (TRs) and concatenates raw input runs [4, 26].
* **`despike`**: Detects and truncates transient intensity spikes in voxel time series prior to alignment [5, 27, 28].
* **`ricor`**: Removes physiological noise (cardiac and respiratory cycles) via RETROICOR regressors [27, 29, 30].
* **`tshift`**: Adjusts slice timing across functional volumes to account for non-simultaneous acquisition [4, 26].
* **`blip`**: Corrects \\(B_0\\) field inhomogeneity geometric distortions using reverse phase-encoded (up/down) EPI images [5, 8, 31].
* **`align`**: Co-registers the functional (EPI) image to the anatomical scan (e.g., using `lpc+ZZ` or `lpa` cost functions in `align_epi_anat.py`) [4, 5, 26].
* **`tlrc`**: Transforms anatomical and functional datasets into standard template space (e.g., MNI152, TT_N27) using linear affine or nonlinear warping (`@SSwarper` / `3dQwarp`) [4, 26, 28].
* **`volreg`**: Performs 3D rigid-body (6-DOF) volume registration to correct for head motion relative to a reference volume (e.g., `MIN_OUTLIER`) [4, 8, 26, 32].
* **`combine`**: For multi-echo fMRI, combines individual echo datasets into a single optimized time series (e.g., via Optimal Combination `OC`) [8, 31].
* **`surf`**: Maps volumetric time series onto SUMA surface meshes for surface-based fMRI analysis [33-35].
* **`blur`**: Applies spatial smoothing within a brain mask (`3dBlurInMask`) or to a target FWHM (`3dBlurToFWHM`) to increase signal-to-noise ratio [4, 26-28].
* **`mask`**: Generates and applies a spatial brain mask (intersecting anatomical and EPI coverage) to restrict downstream computations [4, 8, 26].
* **`scale`**: Rescales each voxel time series (e.g., setting the mean to 100) so regression estimates correspond directly to percent BOLD signal change [4, 26].
* **`regress`**: Executes time series regression (using `3dDeconvolve` or `3dREMLfit`) incorporating stimulus timing models, motion parameters, motion/outlier censors, baseline trends, and tissue regressors (e.g., ANATICOR or PC components from ventricles/white matter) [4, 8, 18, 26, 36].

---

### 3. Outputs of the `afni_proc.py` Pipeline

When `afni_proc.py` executes, it creates a dedicated results directory (e.g., `sub-001.results/`) containing all derivative files [4, 28, 37]:

1. **BRIK / HEAD Datasets**:
   * Preprocessed, motion-corrected, and template-aligned 4D BOLD time series datasets [4, 26].
   * Residual time series (`errts.<subj>+tlrc` or `errts.<subj>+orig`) containing signal after removing baseline, motion, and task effects [4, 26, 38].
2. **1D Motion and Stimulus Files**:
   * **Motion parameters**: Text time series containing 6 rigid-body parameters (`dfile.r*.1D`), demeaned motion (`motion_demean.1D`), motion derivatives (`motion_deriv.1D`), Euclidean norm of motion (`motion_<subj>_enorm.1D`), and binary censor vectors (`censor_<subj>_combined_2.1D`) [4, 26, 38, 39].
   * **Stimulus regressors**: Convolved ideal HRF model curves (`stim_*.1D`) and sum of ideal regressors (`sum_ideal.1D`) [4, 26, 39].
3. **Statistical Datasets**:
   * Output bucket datasets (`stats.<subj>+tlrc` or `stats.<subj>+orig`) containing multiple sub-bricks for regression coefficients (betas), t-statistics, overall model F-statistics, General Linear Test (GLT) contrasts, degrees of freedom, and False Discovery Rate (FDR) q-value curves stored in dataset headers [4, 26, 40-42].
4. **Quality Control (APQC) HTML Report**:
   * Automatically generated interactive HTML document (`QC_<subj>/index.html`) organized into modular **QC blocks** [20, 21, 37, 43, 44]:
     * **`vorig`**: Volumetric check of initial input datasets [45].
     * **`ve2a`**: Overlay images evaluating EPI-to-anatomical alignment [45, 46].
     * **`va2t`**: Overlay images evaluating anatomical-to-template alignment [40, 45].
     * **`vstat`**: Statistical overlay maps showing spatial distribution of model F-stats [40, 45].
     * **`mot`**: Time series plots of head motion parameters, framewise displacement, censoring bars, and outlier volume fractions [39, 45, 47].
     * **`regr`**: Regressor plots, fitted responses, and Temporal Signal-to-Noise Ratio (TSNR) maps [39, 45, 48].
     * **`warn`**: Automated runtime warnings (e.g., severe motion, high correlation between regressors, low degrees of freedom) [22, 24, 45].
     * **`radcor`**: Radial correlation plots for detecting scanner artifacts [4, 26, 45].
     * **`qsumm`**: Summary table and interactive text box for saving user review ratings and comments [45, 49].
5. **Text Review Scripts & Summaries**:
   * `out.ss_review.<subj>.txt`: Machine-readable text file summarizing key pipeline metrics (e.g., maximum motion, number of censored TRs, mean TSNR) created by `@ss_review_basic` [20, 22, 50, 51].
   * `@ss_review_driver`: Interactive script that drives the AFNI GUI to inspect data visually alongside warning outputs [22].

---

### 4. Required File Structures and Formats

AFNI supports several standardized data formats and input/output directory structures [52, 53]:

* **AFNI Dual-File Format (`.HEAD` / `.BRIK` or `.BRIK.gz`)**:
  * **`.HEAD`**: Header file in ASCII/NIML format containing metadata (dimensions, orientation, affine transformations, sub-brick labels, statistical parameters) [14, 52, 54].
  * **`.BRIK` / `.BRIK.gz`**: Raw uncompressed or gzipped binary array storing voxel values across 3D or 4D space [14, 52, 54].
* **NIfTI Format (`.nii` / `.nii.gz`)**: NIfTI-1 and NIfTI-2 3D/4D single-file formats are fully supported as inputs and outputs across all AFNI command-line tools and GUIs [53, 55-57].
* **1D ASCII Text Format (`.1D`)**: Simple tabular text files used for 1D time series, stimulus timing, motion parameters, and spatial transformation matrices (e.g., 12-parameter affine matrices in `.aff12.1D`) [15, 58-60].
* **NIML & GIFTI Formats (`.niml`, `.gii`)**: XML-based file formats used for storing surface-based metric data, region-of-interest (ROI) label tables, and inter-process communication between AFNI and SUMA [54, 58, 61-63].
* **Expected Directory Layout**:
  * **Raw inputs**: Anatomical scans (`T1w.nii.gz` or DICOM converted via `dcm2niix` / `to3d`) and functional BOLD runs (`bold.nii.gz`) stored in structured subject directories [4, 26, 64-66].
  * **Pre-processing inputs**: Anatomical skull-stripping and template alignment files from `@SSwarper` / `sswarper2` (e.g., `anatSS.<subj>.nii`, `anatQQ.<subj>.nii`, `anatQQ.<subj>_WARP.nii`) [4, 7, 8, 26].
  * **Output results directory (`<subj>.results/`)**: Contains intermediate execution volumes (`pb00.*`, `pb01.*`, etc.), final processed dataset BRIKs, motion 1D files, statistical datasets, review files, and the `QC_<subj>/` HTML folder [4, 26, 37, 67, 68].