### 1. SPM Batch Architecture & Core Utilities

* **`spm_jobman`**: The primary job execution manager for SPM's batch system [1, 2]. It interfaces with `cfg_util` to fill undefined inputs, configure processing chains, and execute jobs sequentially or in parallel [1, 3, 4].
  * **Key Parameters**: `spm_jobman('run', job, inputs{:})`, `spm_jobman('serial', jobfile, '', inputs{:})`, `spm_jobman('interactive', matlabbatch)`, or `spm_jobman('initcfg')` [1, 3, 5].
  * **Use Case**: Automating multi-subject or multi-session processing pipelines without interactive GUI prompts [2, 6, 7].

* **`spm('defaults', MODALITY)`**: Sets up the global defaults structure and environment for a chosen imaging modality [1, 8].
  * **Key Parameters**: `MODALITY` string, such as `'FMRI'`, `'EEG'`, or `'PET'` [1, 8].
  * **Use Case**: Required initialization call in standalone MATLAB scripts prior to invoking SPM functions or batch routines [1, 9].

* **Configuration Modules (`spm_cfg_*.m` & `spm_run_*.m`)**: The building blocks of the SPM batch interface [10]. `spm_cfg_*.m` defines configuration classes, GUI elements, and validation functions (`.check`, `.vout`), while `spm_run_*.m` executes the job structure at runtime [10]. `spm_cfg.m` acts as the top-level configuration aggregator and toolbox detector [11].
  * **Use Case**: Defining and running batch modules within `matlabbatch` [10].

* **`spm_select`**: File selection utility used to search, filter, and return file lists matching specific regular expressions [3, 5, 12].
  * **Key Parameters**: Selection mode (e.g., `'FPList'` for full paths), target directory, and filter pattern (e.g., `'^swf.*\.nii$'`) [3, 5, 8].
  * **Use Case**: Programmatically passing image sets (e.g., functional volumes, structural scans, contrast maps) into batch job pipelines [3, 8].

* **`gencode`**: Code generation utility that converts MATLAB variables into executable MATLAB `.m` code [13].
  * **Use Case**: Saving batch structures and generating script templates automatically [13].

---

### 2. Spatial Preprocessing Routines & Modules

* **Realignment (`Realign` / `spm_realign`)**: Computes a 6-parameter rigid-body transformation (3 translations, 3 rotations) to align time series images to a reference volume and correct for head motion [14-16]. It updates the image header affines or writes out realigned volumes (`r*`) and saves estimated motion parameters to `rp_*.txt` [15-17].
  * **Key Parameters**:
    * **Quality**: Trade-off between speed and sampling precision (default `1` for maximum precision) [18].
    * **Separation**: Distance between sampled points in mm (e.g., `4 mm` or `5 mm`) [19].
    * **Smoothing (FWHM)**: Gaussian filter applied before parameter estimation (typically `5 mm` for fMRI, `7 mm` for PET) [19].
    * **Num Passes**: `Register to first` or `Register to mean` (a two-pass realignment) [19].
    * **Reslice Options**: Reslice target (`All Images + Mean Image`, `Mean Image Only`), Interpolation (`Nearest Neighbour`, `Trilinear`, or `B-splines`) [14, 20, 21].
  * **Use Case**: Head motion correction in fMRI time series and generation of a mean functional image for coregistration [15, 19, 22].

* **Slice Timing Correction (`Slice Timing` / `spm_slice_timing`)**: Corrects for differences in slice acquisition times within a 3D volume by interpolating voxel time series relative to a chosen reference slice [16, 23].
  * **Key Parameters**:
    * **Number of Slices**: Total axial/coronal slices (\\(N\\)) [23].
    * **TR & TA**: Interscan interval (\\(TR\\)) and acquisition time (\\(TA = TR - TR/N\\)) [23].
    * **Slice Order**: Vector defining acquisition sequence (e.g., `[24 23 ... 1]` descending) [23].
    * **Reference Slice**: Reference slice index or reference time (ms) to align data toward [16, 24].
    * **Filename Prefix**: String prepended to outputs (default `'a'`) [16].
  * **Use Case**: Aligning temporal sampling across slices in interleaved or sequential fMRI acquisitions [23, 24].

* **Coregistration (`Coregister` / `spm_coreg`)**: Executes rigid-body inter-modal registration (e.g., structural T1 to mean functional fMRI) by maximizing mutual information [22, 25, 26].
  * **Key Parameters**:
    * **Reference Image**: Target image held fixed (e.g., mean fMRI volume) [22, 25].
    * **Source Image**: Moving image to align (e.g., structural T1) [22, 25].
    * **Other Images**: Secondary images moved alongside the source image [27].
    * **Jobtype**: `'estimate'`, `'write'`, or `'estwrite'` [26, 28, 29].
  * **Use Case**: Mapping structural and functional images into the same subject-specific space [22, 25, 27].

* **Segmentation (`Segment` / Unified Segmentation / `spm_preproc`)**: Integrates tissue classification (GM, WM, CSF), intensity bias field correction, and non-linear spatial normalization into a single generative model using Tissue Probability Maps (TPMs) [30-32].
  * **Key Parameters**:
    * **Volumes**: Input anatomical scan [32, 33].
    * **Save Bias Corrected**: Option to export bias-corrected anatomical scans (`m*`) [32, 33].
    * **Deformation Fields**: Exports forward (`y_*.nii`) or inverse (`iy_*.nii`) deformation warps [32, 33].
    * **Tissue Classes**: Number of Gaussians and spatial resolution per tissue class [32].
  * **Use Case**: Generating tissue tissue probability maps, correcting MRI intensity inhomogeneity, and obtaining warps for spatial normalization [31-33].

* **Spatial Normalisation (`Normalise` / `spm_normalise`)**: Warps images from individual native space into a standard stereotactic space (MNI) using affine transformations and non-linear deformations derived from Unified Segmentation, DARTEL, or Shoot [34-37].
  * **Key Parameters**:
    * **Data / Image to Align**: Native space images or deformation fields [8, 27].
    * **Voxel Sizes**: Target isotropic voxel dimensions (e.g., `2x2x2 mm`) [38, 39].
    * **Bounding Box**: Spatial boundaries of output images in MNI space [38].
    * **Preserve Option**: `Preserve Concentrations` (unmodulated, for fMRI `sw*`) vs `Preserve Amount` (modulated, `smw*` for VBM) [40].
  * **Use Case**: Transforming single-subject anatomical and functional data into standard template space for group statistics [36, 37, 41].

* **Smoothing (`Smooth` / `spm_smooth`)**: Convolves 3D image volumes with an isotropic or anisotropic 3D Gaussian smoothing kernel [26, 41].
  * **Key Parameters**:
    * **Images to Smooth**: Target normalized volumes (e.g., `w*` or `wf*`) [41, 42].
    * **FWHM**: Full-Width at Half-Maximum of the Gaussian kernel in mm (e.g., `` or ``) [41, 42].
    * **Filename Prefix**: String prepended to outputs (default `'s'`) [41, 42].
  * **Use Case**: Boosting SNR, satisfying Random Field Theory assumptions, and blurring residual structural differences across subjects [41, 43].

---

### 3. General Linear Model (GLM) Specification, Estimation & Results

* **fMRI Model Specification (`Specify 1st-level` / `spm_fmri_spec`)**: Builds the 1st-level (single-subject) GLM design matrix (\\(X\\)) for task or resting-state fMRI analyses and outputs `SPM.mat` [24, 43-45].
  * **Key Parameters**:
    * **Directory**: Destination folder for `SPM.mat` [24, 46, 47].
    * **Timing Parameters**: Units (`'scans'` or `'secs'`), Interscan interval (\\(TR\\)), Microtime resolution (default `16`), and Microtime onset (default `8`) [24, 46, 47].
    * **Data & Design**: Scans per session, condition names, onsets, durations, and optional multiple conditions `.mat` file [24, 46, 48].
    * **Basis Functions**: Canonical HRF with optional time and dispersion derivatives [47, 48].
    * **Multiple Regressors**: File containing motion parameters (`rp_*.txt`) or custom nuisance covariates (\\(R\\)) [24, 44, 48].
    * **High-pass Filter Cutoff**: Cutoff period in seconds for removing low-frequency drifts (e.g., `128s`) [44, 49].
    * **Masking Threshold & Explicit Mask**: Relative/absolute threshold masking (default `0.8`) or user-supplied anatomical mask [47, 50].
  * **Use Case**: Setting up design matrices for task activation or covariate regression in fMRI [24, 43, 51].

* **Model Estimation (`Estimate` / `spm_spm`)**: Estimates GLM regression parameters (\\(\hat{\beta}\\)) and error variance (\\(\hat{\sigma}^2\\)) using Restricted Maximum Likelihood (ReML) for classical estimation or Variational Bayes (`spm_spm_vb`) for Bayesian estimation [45, 52-54].
  * **Key Parameters**:
    * **Select SPM.mat**: Path to the generated `SPM.mat` file [46, 52, 55].
    * **Method**: Classical (ReML) or Bayesian (1st-level AR order) [52, 53].
  * **Outputs Produced**: Updated `SPM.mat`, parameter estimates (`beta_000k.nii`), residual mean squares (`ResMS.nii`), analysis mask (`mask.nii`), and resels per voxel (`RPV.nii`) [53, 56].
  * **Use Case**: Fitting GLM models voxelwise across the brain [45, 52].

* **Contrast Manager (`spm_conman` / Contrast Manager)**: Evaluates linear hypotheses over estimated regression parameters using T- or F-contrasts [55, 57-59].
  * **Key Parameters**:
    * **Select SPM.mat**: Path to estimated `SPM.mat` [55, 57, 58].
    * **Contrast Type**: T-contrast (one-tailed) or F-contrast (multivariate effects) [58, 59].
    * **Contrast Vector/Matrix**: Weights assigned to columns of the design matrix [58, 59].
  * **Outputs Produced**: Contrast images (`con_000i.nii`), extra sum-of-squares images (`ess_000i.nii`), and statistical map volumes (`spmT_000i.nii`, `spmF_000i.nii`) [56, 60].
  * **Use Case**: Testing experimental contrasts and generating statistical parametric maps [52, 55, 59].

* **Factorial Design Specification (`Specify 2nd-level`)**: Configures 2nd-level (group/random-effects) GLMs using 1st-level contrast images (`con_*.nii`) as input data [45, 50, 61, 62].
  * **Key Parameters**:
    * **Design Options**: One-sample t-test, Two-sample t-test, Paired t-test, Full/Flexible Factorial, or Multiple Regression [50, 61, 62].
    * **Variance & Independence**: Specifies sphericity settings (equal/unequal variance, dependent/independent levels) [50, 54].
  * **Use Case**: Carrying single-subject effects forward to group-level population inference [45, 50, 63].

* **Volume of Interest (`spm_regions` / VOI)**: Extracts first eigenvariate or mean signal time series from spherical or mask-defined regions of interest [64-66].
  * **Key Parameters**:
    * **Select SPM.mat**: Path to estimated 1st-level GLM [65].
    * **ROI Definition**: Sphere center coordinates, radius (mm), or mask image [65].
    * **Adjustment**: Adjusts data relative to an experimental contrast null space [66].
  * **Outputs**: `VOI_*.mat` file containing the extracted time series variable `Y` [64, 66].
  * **Use Case**: Extracting regional time courses for Dynamic Causal Modelling (DCM), Psychophysiological Interactions (PPI), or nuisance signal extraction (e.g., WM/CSF) [64, 66, 67].

---

### 4. M/EEG Preprocessing Routines & Object Methods

* **`spm_eeg_load`**: Loads an M/EEG `.mat` header into memory as an `@meeg` object and memory-maps the associated binary `.dat` file [68-70].
  * **Use Case**: Accessing M/EEG headers and data arrays programmatically in MATLAB [69, 70].

* **`spm_eeg_ft2spm`**: Converts FieldTrip raw data structures into SPM `@meeg` objects [71, 72].
  * **Use Case**: Ingesting FieldTrip datasets into the SPM M/EEG pipeline [71, 72].

* **`spm_eeg_epochs`**: Epochs continuous M/EEG data into time windows centered on specified events or trial definition structures (`trl`) [73-76]. Output prefixed with `'e'` [74, 76].
  * **Use Case**: Segmenting continuous streams into stimulus-locked trials [74-76].

* **`spm_eeg_filter`**: Applies a zero-phase forward-backward Butterworth filter (low-pass, high-pass, band-pass, or stop-band) [73, 76, 77]. Output prefixed with `'f'` [76, 77].
  * **Use Case**: Removing low-frequency drift or high-frequency muscle and line noise [76, 77].

* **`spm_eeg_bc`**: Performs baseline subtraction over a specified pre-stimulus time window [73, 77]. Output prefixed with `'b'` [77].
  * **Use Case**: Correcting baseline offsets in ERP/ERF epoch data [77].

* **`spm_eeg_artefact`**: Automatically detects and marks artifactual trials or channels using thresholding, peak-to-peak amplitude, jump, or flat-line detection algorithms [73, 77].
  * **Use Case**: Automated trial and channel quality control [77].

* **`spm_eeg_montage`**: Applies a linear combination matrix to re-reference sensor channels (e.g., average reference or virtual channels) [73, 78]. Output prefixed with `'M'` [78].
  * **Use Case**: Re-referencing EEG channels or constructing virtual sensor networks [78].

* **`spm_eeg_grandmean`**: Calculates unweighted or trial-weighted grand averages of evoked responses across subjects or sessions [73, 79].
  * **Use Case**: Group-level ERP/ERF averaging [73, 79].

* **`spm_eeg_merge`**: Concatenates multiple M/EEG datasets along the time or trial dimensions [73, 80]. Output prefixed with `'c'` [80].
  * **Use Case**: Merging experimental runs or sessions for joint display and analysis [80].

* **`spm_eeg_fuse`**: Combines non-overlapping sensor channels (e.g., simultaneously recorded MEG and EEG) into a single dataset [73, 81].
  * **Use Case**: Multimodal MEG/EEG integration for joint source reconstruction [81].

* **`spm_eeg_crop`**: Cuts specified time intervals, frequency ranges, or channel sets from datasets [73, 82].
  * **Use Case**: Trimming filter ringing artifacts or windowing time-frequency data [82].

* **`spm_eeg_combineplanar`**: Combines orthogonal planar gradiometer sensor pairs by calculating Root Mean Square (RMS) in the time domain or summing power in the time-frequency domain [73, 82, 83]. Output prefixed with `'P'` [82, 83].
  * **Use Case**: Simplifying planar MEG sensor interpretation [82, 83].

* **`spm_eeg_reduce`**: Projects data onto a smaller set of spatial components using dimensionality reduction techniques such as PCA [73, 83].
  * **Use Case**: Reducing spatial dimensionality prior to advanced modeling [83].

* **`spm_eeg_tf`**: Computes time-frequency spectral decomposition using Morlet wavelets or Hilbert transforms [73, 83]. Output prefixed with `'tf'` [83].
  * **Use Case**: Analyzing induced power and phase synchronization [83].

* **`spm_eeg_avgtime` & `spm_eeg_avgfreq`**: Averages time-frequency representations over specified time or frequency bins [73, 83, 84].
  * **Use Case**: Summarizing spectral components into 2D time or frequency datasets [83, 84].

* **`spm_eeg_average`**: Computes conditional trial averages to extract evoked or induced responses [73, 83, 84]. Output prefixed with `'m'` [84].
  * **Use Case**: Generating standard ERP/ERF waveforms [73, 84].

* **`spm_eeg_copy`**: Duplicates M/EEG dataset header (`.mat`) and binary (`.dat`) files while updating internal header filenames [73, 85].
  * **Use Case**: Making safe copies of datasets without breaking header-to-binary links [85].

* **`spm_eeg_remove_bad_trials`**: Physically deletes trials flagged as bad from the `.dat` file [73, 85].
  * **Use Case**: Memory optimization before time-frequency processing [85].

---

### 5. FieldMap Distortion Correction Utilities

* **`FieldMap_preprocess` / `FieldMap_create`**: Processes phase and magnitude fieldmaps, unwraps phase maps, generates voxel displacement maps (VDM), and unwarps geometric distortion in fMRI EPI images [86-89].
  * **Key Parameters**: `VDM = FieldMap_preprocess(fm_dir, epi_dir, [te1, te2, epifm, tert, kdir, mask, match])`, with configuration defaults read from `pm_defaults*.m` [86, 88].
  * **Use Case**: Correcting B0 magnetic field inhomogeneity distortions during realignment/unwarping [86-88].

---

🧠 **Would you like me to build a complete Matlab script using `spm_jobman` to automate a full processing pipeline (preprocessing through GLM estimation) for your fMRI or M/EEG dataset?**
