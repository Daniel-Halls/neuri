**XCP-D** (eXtensible Connectivity Pipeline - DCAN edition) is a flexible BIDS-App postprocessing pipeline designed to process preprocessed functional MRI (fMRI) data from pipelines such as **fMRIPrep**, **Nibabies**, **HCP Pipelines**, **ABCD-BIDS (DCAN)**, and **UK Biobank** [1, 2]. It performs nuisance regression, temporal filtering, scrubbing/interpolation, resting-state derivative calculation, atlas parcellation, functional connectivity estimation, and generates visual quality control (QC) reports [1, 3, 4].

---

### 1. Postprocessing Steps in XCP-D

* **Anatomical Processing & Surface Normalization**: Applies existing spatial transformations from preprocessing to warp T1w/T2w volumes into standard space at original resolution [5]. If `--warp-surfaces-native2std` is flagged, `fsnative` GIFTI surface files are warped to **fsLR-32k** space [5, 6].
* **High-Motion Outlier Detection & Scrubbing**: Calculates framewise displacement (FD) per volume [7]. Volumes exceeding the FD threshold (`--fd-thresh`) are flagged as high-motion outliers [7]. Handling of outliers depends on the processing mode:
  * **Censoring/Scrubbing**: High-motion volumes are removed/censored from the time series (default in `linc` mode) [8-10].
  * **Cubic Spline Interpolation**: High-motion outlier volumes in BOLD time series and confounds are filled using cubic spline interpolation before regression/filtering (used in `abcd` and `hbcd` modes) [11, 12]. Outliers at run boundaries are set to the nearest low-motion volume to avoid extrapolation [12, 13].
* **Despiking (Optional)**: Large amplitude spikes in BOLD time courses are truncated to an imputed reduced magnitude prior to filtering and regression using `--despike` [14, 15].
* **Detrending**: A linear model detrends and mean-centers both BOLD data and confounds across time [16].
* **Temporal Bandpass Filtering**: Applies a Butterworth filter (default passband \\(0.01\text{--}0.08\text{ Hz}\\), filter order 2) [9, 16]. Filtering is performed orthogonally with respect to nuisance regressors so that temporal filter variance is not re-introduced during regression [13].
* **Nuisance Regression & Confound Strategies**: Regresses out non-neuronal sources of variance [7, 17, 18]. XCP-D supports several built-in nuisance strategies (e.g., `24P`, `27P`, `36P`, `acompcor`, `acompcor_gsr`, `aroma`, `aroma_gsr`, `gsr_only`, or `none`) as well as custom YAML configuration files or 4D NIfTI voxel-wise regressors [7, 17, 19].
  * *Note on fMRIPrep \\(\ge 23.1.0\\)*: ICA-AROMA was removed from fMRIPrep; AROMA strategies in XCP-D require running `fMRIPost-AROMA` first and providing its derivatives via `--datasets aroma=...` [20].
* **Re-censoring**: Following bandpass filtering and regression, interpolated high-motion volumes are re-censored to produce the final denoised, censored BOLD time series [10].
* **Resting-State Metric Derivatives**:
  * **ALFF (Amplitude of Low-Frequency Fluctuations)**: Measures low-frequency power. Calculated only when bandpass filtering is enabled [21, 22]. Optional spatial Gaussian smoothing can be applied with `--smoothing` [21, 22].
  * **ReHo (Regional Homogeneity)**: Measures local BOLD temporal synchronization using Kendall's coefficient of concordance (KCC) [22, 23]. For NIfTI/subcortical data, it uses AFNI’s `3dReho` with a 27-voxel neighborhood [23]. For CIFTI surface data, it separates GIFTIs and uses mesh adjacency with 4 neighboring vertices [23].
* **Parcellation**: Extracts parcel-wise time series from denoised BOLD using built-in or user-specified atlases [24]. Built-in atlases include the **Schaefer 4S set** (156 to 1056 parcels), **Glasser**, **Gordon**, **HCP**, **MIDB**, **MyersLabonte**, and **Tian** [25].
* **Functional Connectivity Matrices**: Calculates static functional connectivity matrices using **Pearson correlation coefficients** between parcellated ROI time series [26]. Subsampled correlation matrices matching specific volume durations can be produced using `--create-matrices` (requires run concatenation via `--combine-runs`) [8, 27].

---

### 2. Outputs of the XCP-D Pipeline

XCP-D writes BIDS-compliant derivatives to the designated output folder [3, 28]:

1. **Summary Reports**:
   * **NiPreps-style HTML report** (`sub-<label>.html`) per participant containing summary statistics (TR, mean FD, RMS motion, DVARS vs. FD correlations before/after denoising, volume censoring counts) and pre/post regression carpet plots [29].
   * Executive summaries and DCAN/LINC-style QC files depending on the active processing mode (`abcd`, `hbcd`, or `linc`) [9, 11].
2. **Anatomical Derivatives**:
   * Resampled standard-space T1w/T2w volumes [4].
   * Warped surface mesh files in `fsLR_den-32k` space (`*.surf.gii`) [6].
   * Parcellated surface morphometric TSV files for curvature, sulcal depth, and cortical thickness (`*_space-fsLR_atlas-<label>_stat-mean_desc-<metric>_morph.tsv`) [30, 31].
3. **Functional Outputs**:
   * **Denoised/Residual BOLD Data**: Volumetric NIfTI (`_desc-denoised_bold.nii.gz`) or dense CIFTI (`_desc-denoised_bold.dtseries.nii`) time series [9, 10, 31].
   * **Parcellated Timeseries & Connectivity Matrices**:
     * Parcellated time series TSV files (`_atlas-<label>_timeseries.tsv`) and CIFTI `.ptseries.nii` files [26].
     * Static Pearson correlation matrices saved as TSV (`_atlas-<label>_measure-pearsoncorrelation_conmat.tsv`) and CIFTI `.pconn.nii` files [26].
   * **Resting-State Derivatives**:
     * Voxel-wise/vertex-wise ReHo and ALFF maps (`_stat-reho_boldmap.nii.gz`, `_stat-alff_boldmap.nii.gz`, `_stat-alff_desc-smooth_boldmap.dscalar.nii`) [21].
     * Atlas-parcellated ReHo and ALFF TSV files (`_atlas-<label>_stat-reho_bold.tsv`, `_atlas-<label>_stat-alff_bold.tsv`) [21].
   * **Framewise Displacement & Confounds**: Scrubbing files, filtered FD TSVs, and quality control metrics [3, 21].

---

### 3. Required File Structures & Minimal Inputs

To postprocess **fMRIPrep** or **Nibabies** derivatives, XCP-D requires input datasets containing a valid `dataset_description.json` file and images in one of its supported standard spaces (**MNI152NLin6Asym**, **MNI152NLin2009cAsym**, **MNIInfant**, or **fsLR** at 91k density for CIFTIs) [2, 32, 33].

#### Minimal Required Input Files [32, 34]:
* **Native Anatomical Volume**: Preprocessed T1w or T2w image in native space (`sub-x_desc-preproc_T1w.nii.gz` + JSON) [32, 34].
* **Preprocessed BOLD Volume/CIFTI**: BOLD image in target standard space (`sub-x_task-<name>_space-<space>_desc-preproc_bold.nii.gz` or `.dtseries.nii` + JSON) [32, 34].
* **BOLD Reference & Brain Mask**: `boldref` image and functional brain mask in the same standard space as BOLD data [32, 34].
* **Confounds Time Series**: Confound regressor TSV file and accompanying JSON metadata (`sub-x_task-<name>_desc-confounds_timeseries.tsv` + `.json`) [32, 34].
* **Anatomical Brain Mask**: Brain mask in standard/BOLD space [32, 34].
* **Spatial Transforms**: Forward and inverse rigid/nonlinear transformation files between native anatomical space and target standard space (e.g., `sub-x_from-MNI152NLin6Asym_to-T1w_mode-image_xfm.h5` and `sub-x_from-T1w_to-MNI152NLin6Asym_mode-image_xfm.h5`) [32, 34].

#### Representative Directory Layout (NIfTI BIDS Derivatives Input) [34]:
```text
fmriprep/
├── dataset_description.json
└── sub-01/
    ├── anat/
    │   ├── sub-01_desc-preproc_T1w.nii.gz
    │   ├── sub-01_desc-preproc_T1w.json
    │   ├── sub-01_space-MNI152NLin6Asym_desc-brain_mask.nii.gz
    │   ├── sub-01_space-MNI152NLin6Asym_desc-brain_mask.json
    │   ├── sub-01_from-MNI152NLin6Asym_to-T1w_mode-image_xfm.h5
    │   └── sub-01_from-T1w_to-MNI152NLin6Asym_mode-image_xfm.h5
    └── func/
        ├── sub-01_task-rest_desc-confounds_timeseries.tsv
        ├── sub-01_task-rest_desc-confounds_timeseries.json
        ├── sub-01_task-rest_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
        ├── sub-01_task-rest_space-MNI152NLin6Asym_desc-preproc_bold.json
        ├── sub-01_task-rest_space-MNI152NLin6Asym_boldref.nii.gz
        ├── sub-01_task-rest_space-MNI152NLin6Asym_boldref.json
        ├── sub-01_task-rest_space-MNI152NLin6Asym_desc-brain_mask.nii.gz
        └── sub-01_task-rest_space-MNI152NLin6Asym_desc-brain_mask.json
```

---