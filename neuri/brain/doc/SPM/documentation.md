### **Overview of SPM (Statistical Parametric Mapping)**

**Statistical Parametric Mapping (SPM)** is a software package and computational framework designed for the statistical analysis of neuroimaging data, including functional MRI (fMRI), PET, SPECT, and M/EEG [1-3]. SPM operates primarily on a **mass-univariate approach** rooted in the **General Linear Model (GLM)**, fitting statistical models independently at each voxel across time-series or experimental scans [1, 4].

In SPM, image data are abstracted in MATLAB as `vol struct` objects containing image metadata (such as voxel-to-world affine transformation matrices `vol.mat` and dimensions `vol.dim`) for each 3D volume [5, 6]. SPM computes continuous spatial fields of test statistics to construct **Statistical Parametric Maps (SPMs)** or **Posterior Probability Maps (PPMs)** for statistical inference [1, 4, 7, 8].

---

### **SPM Pipeline Workflow**

The SPM analysis pipeline follows four core stages: **Spatial Preprocessing**, **Model Specification**, **Parameter Estimation**, and **Statistical Inference** [1, 9, 10].

#### **1. Spatial Preprocessing**
Spatial preprocessing prepares raw functional and anatomical MRI scans for voxel-wise statistical modeling by correcting for motion, time delays, and spatial differences [9, 10]:

* **Realignment (`Realign`)**:
  * **What it does**: Corrects for subject head motion across time series scans using a 6-parameter (3 translations, 3 rotations) rigid-body affine transformation [11-13].
  * **Outputs**: Modifies image headers or creates realigned image volumes (prefixed with `r`), generates a mean functional volume (e.g., `mean*.nii` or `mean*.img`), and writes an ASCII text file containing rigid-body motion parameters (e.g., `rp_*.txt`) [12-14].
* **Slice Timing Correction (`Slice timing`)**:
  * **What it does**: Adjusts for temporal acquisition differences across slices acquired within the same interscan interval (TR) [14-16]. Interpolates signal values relative to a designated reference slice using user-defined microtime parameters [15-17].
  * **Outputs**: Produces slice-time corrected volumes (prefixed with `a`) [17].
* **Coregistration (`Coregister`)**:
  * **What it does**: Establishes rigid-body spatial alignment between functional images (or the mean functional image) and the subject's high-resolution T1-weighted anatomical scan [14, 18, 19].
* **Segmentation & Spatial Normalization (`Segment` & `Normalise`)**:
  * **What it does**: Uses unified segmentation to classify the anatomical T1 image into tissue classes (gray matter, white matter, CSF) while simultaneously estimating nonlinear spatial deformations that align the brain to standard stereotactic space (e.g., MNI template) [20-24].
  * **Outputs**: Saves 3D deformation field files (e.g., `y_*.nii` or legacy `*_sn.mat`) containing voxel coordinates [24-26]. Applying these deformations to functional and structural data generates spatially normalized images (prefixed with `w`) [25, 27].
* **Smoothing (`Smooth`)**:
  * **What it does**: Applies an isotropic 3D Gaussian kernel (typically 6–8 mm FWHM for MRI) to normalized functional images [28-30].
  * **Purpose**: Increases signal-to-noise ratio (SNR), reduces inter-subject anatomical discrepancies, and ensures the spatial residual fields conform to Gaussian Random Field theory assumptions [4, 28, 30]. Produces smoothed volumes (prefixed with `s`) [17, 29].

---

#### **2. Model Specification (`Specify 1st-level` / `Specify 2nd-level`)**
* **Design Matrix Construction**: Constructs the design matrix \\(X\\) where rows correspond to individual scan volumes and columns correspond to experimental conditions, regressors, or covariates [1, 16].
* **Timing & Basis Sets**: Experimental event/block timing is specified in scans or seconds [15, 17]. Regressors are convolved with a Hemodynamic Response Function (HRF) basis set (e.g., canonical HRF, optionally with temporal and dispersion derivatives) [15, 16, 31].
* **Filtering & Nuisance Regressors**: Incorporates high-pass temporal filtering to remove low-frequency signal drift and integrates user-defined multiple regressors (e.g., head motion parameters from `rp_*.txt`) [13, 17, 32, 33].
* **Autocorrelation Model**: Specifies temporal serial correlation handling (e.g., an autoregressive AR(1) noise model or IID assumption) [4, 33].
* **Global Normalization & Masking**: Offers options for global scaling (multiplying each scan by \\(100 / gns\\)) and applies explicit or implicit anatomical threshold masking to restrict model fitting to brain voxels [32, 33].
* **Output**: Saves the complete design structure to an unestimated `SPM.mat` file in a user-selected directory [2, 32, 34].

---

#### **3. Parameter Estimation (`Estimate`)**
* **Algorithms**: Estimates GLM regression parameters \\(\beta\\) voxel-by-voxel [1, 7].
  * **Classical Approach**: Uses **Restricted Maximum Likelihood (ReML)** to estimate error covariance components and account for non-sphericity and serial correlations across voxels [4, 33, 35].
  * **Bayesian Approach**: Fits models using Variational Bayes (VB) for 1st-level analysis or Empirical Bayes for 2nd-level group models [36, 37].
* **Computation**: Estimates error variance maps and adjusts statistical test statistics and effective degrees of freedom based on ReML covariance components (`SPM.xVi`) [33, 35].
* **Output**: Writes estimated parameter images (\\(\beta\\) maps), error variance maps, and updates `SPM.mat` with estimated parameters and hyperparameters [7, 38].

---

#### **4. Statistical Inference (`Results` / Contrast Manager)**
* **Contrast Vectors**: Users define linear contrasts (T-contrasts for directional effects or F-contrasts for main effects/extra sum-of-squares) to evaluate specific hypotheses [1, 4, 38-40].
* **Statistical Maps**: SPM computes voxel-wise \\(T\\) or \\(F\\) statistics, generating \\(SPM\{T\}\\) or \\(SPM\{F\}\\) statistical maps [4, 38, 41].
* **Multiple Comparisons Correction**: Applies **Random Field Theory (RFT)** or **False Discovery Rate (FDR)** / **Family-Wise Error (FWE)** corrections to set height (\\(p\\)-value) and extent (cluster size \\(k\\)) thresholds [4, 39, 41, 42].
* **Visualization**: Displays thresholded activations on a glass brain **Maximum Intensity Projection (MIP)** or superimposed onto anatomical slice overlays [39, 41, 43].

---

### **Outputs of the SPM Pipeline**

Upon completing model specification, estimation, and inference, SPM writes the following standardized files into the active analysis directory [7, 32, 38, 41]:

| Output File Name | Format | Description / Purpose |
| :--- | :--- | :--- |
| **`SPM.mat`** | MATLAB MAT-file | **Central pipeline file**: Contains the complete experimental design matrix, image file paths, TR/timing settings, high-pass filter cutoffs, covariance matrices (`SPM.xVi`), contrast definitions, and estimated model parameters [7, 32, 38, 44]. |
| **`beta_000k.nii`** (or `.img`) | 3D Image | **Estimated Regression Parameters**: Image of the estimated GLM parameter/beta coefficient (\\(\beta_k\\)) for the \\(k\\)-th regressor in the design matrix [38, 45]. *(Prefixed as `Cbeta_000k.nii` in Bayesian models)* [45, 46]. |
| **`con_000i.nii`** (or `.img`) | 3D Image | **Contrast Effect Map**: Weighted parameter estimates (\\(c^T \beta\\)) computed for the \\(i\\)-th T-contrast [38, 41, 45, 47]. |
| **`ess_000i.nii`** (or `.img`) | 3D Image | **Extra Sum-of-Squares Map**: Image generated for the \\(i\\)-th F-contrast [38]. |
| **`spmT_000i.nii`** (or `.img`) | 3D Image | **T-Statistic Map**: Voxel-wise \\(T\\)-statistic values for contrast \\(i\\) [38, 41, 47]. |
| **`spmF_000i.nii`** (or `.img`) | 3D Image | **F-Statistic Map**: Voxel-wise \\(F\\)-statistic values for contrast \\(i\\). |
| **`ResMS.nii`** (or `.img`) | 3D Image | **Residual Mean Squares**: Map of the estimated error variance (\\(\sigma^2\\)) across voxels [38]. |
| **`mask.nii`** (or `.img`) | 3D Binary Image | **Analysis Mask**: Identifies which voxels met threshold criteria and were included in model estimation [38, 45, 46]. |
| **`RPV.nii`** (or `.img`) | 3D Image | **Resels Per Voxel**: Map of estimated resolution elements (resels) per voxel used for RFT corrections [38]. |
| **`rp_*.txt`** | ASCII Text | **Realignment Parameters**: 6 columns of estimated rigid-body motion parameters (3 translations in mm, 3 rotations in degrees) across volumes [13, 17]. |
| **`y_*.nii`** | 5D NIfTI Vector Image | **Deformation Fields**: Encodes the \\(x, y, z\\) mm coordinates generated during spatial normalization or segmentation [24-26]. |

---

### **Required File Structures & Conventions**

#### **1. File Formats & Uncompressed Requirement**
* **NIfTI Formats**: SPM supports NIfTI-1.1 and NIfTI-2 3D/4D single-file (`.nii`) or dual-file (`.hdr`/`.img` Analyze) formats [38, 48, 49].
* **No Direct Direct Gzip (`.nii.gz`) Support**: SPM **cannot read gzipped (`.nii.gz`) files directly** because its routines perform random-access read/write operations on individual slice/voxel byte offsets on disk [49-51]. Files must be uncompressed (`gunzip`ped) before processing [49-51].
* **Orientation Headers**: SPM relies on NIfTI `sform` or `qform` affine matrices to map voxel indices to world space coordinates [52]. Supplemental rigid-body reorientation matrices are written to sidecar MATLAB `.mat` files [53].

#### **2. Sequential Prefix Naming Convention**
SPM uses a strict, cumulative single-letter prefix convention prepended to output filenames to track each step of processing [17, 25, 29, 54]:

* **`a`**: Slice-time corrected image (e.g., `afM001.nii`) [17]
* **`r`**: Realigned image (e.g., `rfM001.nii`)
* **`u`**: Distortion-corrected / unwarped EPI volume [55, 56]
* **`w`**: Spatially normalized volume in MNI space (e.g., `wfM001.nii`) [25, 27]
* **`s`**: Spatially smoothed volume (e.g., `swfM001.nii` indicates a slice-timed, realigned, normalized, and smoothed scan) [17, 29]
* **`m`** or **`mean`**: Mean image volume generated during realignment or coregistration (e.g., `meanfM001.nii`) [12, 14, 57]

#### **3. Directory Organization**
SPM requires dedicated, separate directories for each step or analysis level to prevent overwriting critical files [7, 9, 32, 58]:

```text
study_directory/
├── jobs/                 # Saved SPM batch specification files (*.mat or *.m)
├── structural/           # Raw T1-weighted anatomical DICOM/NIfTI scans
├── functional/           # Raw EPI functional time-series volumes
│   ├── fM0001.nii
│   ├── ...
│   ├── swafM0001.nii     # Fully preprocessed functional volumes
│   └── rp_fM0001.txt     # Head motion realignment parameter file
└── 1st_level_analysis/   # Dedicated GLM output directory
    ├── SPM.mat           # Model specification & estimation metadata
    ├── beta_0001.nii     # Beta parameter maps
    ├── con_0001.nii      # Contrast images
    ├── spmT_0001.nii     # Statistical T maps
    └── ResMS.nii         # Error variance map
```