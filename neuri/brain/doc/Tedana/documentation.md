**Tedana** (**TE-Dependent ANAlysis**) is an open-source Python library designed for denoising multi-echo functional magnetic resonance imaging (fMRI) data [1]. Originally derived from the multi-echo ICA (ME-ICA) pipeline developed by Dr. Prantik Kundu, Tedana has evolved into a modular, standalone package focused specifically on TE-dependent signal decomposition and noise removal [1-3]. 

Tedana does not perform initial volume preprocessing (such as head-motion correction, slice-timing correction, or spatial normalization) [1, 4, 5]. Instead, it accepts **previously preprocessed multi-echo functional time series** in structured voxel space and leverages physical signal decay across echo times (TEs) to distinguish neural BOLD signals from non-BOLD noise artifacts [1, 5-7].

---

### Multi-Echo fMRI Denoising Pipeline Stages

The canonical Tedana workflow (`tedana_workflow`) processes multi-echo fMRI data through six primary sequential stages [8-10]:

#### 1. Adaptive Mask Generation
* **Signal Dropout Mitigation**: Longer echo times are prone to signal decay and dropout in regions with high magnetic susceptibility gradients (such as the orbitofrontal cortex and temporal poles) [11, 12].
* **Voxel-wise Echo Masking**: Using `make_adaptive_mask()`, Tedana evaluates each voxel to determine how many consecutive echoes (starting from the first) contain reliable ("good") signal, generating an integer-valued adaptive mask [10, 11, 13].
* **Two-Stage Procedure**:
  * A **liberal mask** (voxels with good signal in \\(\ge 1\\) echo) is used for \\(T_2^*/S_0\\) decay fitting, optimal combination, and final output denoising [11, 14].
  * A **conservative mask** (restricted to voxels with good signal in \\(\ge 3\\) echoes) is passed to the component decomposition and classification algorithms [11, 14].
* If an explicit brain mask (`--mask`) is not provided, Nilearn’s `compute_epi_mask()` is run on the first echo data to establish an initial brain boundary prior to adaptive masking [10, 12].

#### 2. Monoexponential \\(T_2^*\\) and \\(S_0\\) Decay Fitting
* **Physical Decay Model**: BOLD signal intensity across echo times follows a monoexponential decay curve described by \\(S(TE) = S_0 \cdot e^{-TE / T_2^*}\\), where \\(S_0\\) is initial signal intensity and \\(T_2^*\\) is the transverse relaxation time [6, 15, 16].
* **Fitting Methods**:
  * **Log-Linear Fit (`fittype='loglin'`, default)**: Data are transformed as \\(\log(|S| + 1)\\) and echo times are negated, enabling rapid parameter estimation via weighted linear regression [10, 15, 16].
  * **Nonlinear Curve Fit (`fittype='curvefit'`)**: Fits a monoexponential model directly to untransformed BOLD signals; it is computationally more demanding but can achieve higher accuracy [10, 15, 17].
* Tedana computes full 3D spatial maps of average \\(T_2^*\\) and \\(S_0\\) across time [16, 18].

#### 3. Optimal Combination
* **Weighted Averaging**: Using the calculated \\(T_2^*\\) map, time series across all collected echoes are combined into a single, high-contrast time series (`desc-optcom_bold.nii.gz`) [18-20].
* **Weighting Formula**: Echoes are weighted according to:
  \\[w(TE) = TE \cdot e^{-TE / T_2^*}\\]
  Normalized weights maximize signal-to-noise ratio (SNR) by emphasizing earlier echoes where signal is high and later echoes where \\(T_2^*\\) sensitivity peaks [19, 20]. (An alternative parallel-acquired inhomogeneity desensitized/PAID method is also supported via `combmode='paid'`) [19, 21].

#### 4. TEDPCA (Principal Component Analysis Dimensionality Reduction)
* **Thermal Noise Isolation**: Applies TE-dependent PCA to the optimally combined time series to reduce dimensionality and facilitate subsequent ICA convergence [9, 22, 23].
* **Selection Criteria (`--tedpca`)**:
  * Information-theoretic criteria: Akaike Information Criterion (`aic`, default; least aggressive), Minimum Description Length (`mdl`; most aggressive), or Kullback-Leibler Information Criterion (`kic`) [10, 22, 24, 25].
  * Fixed thresholding: User-specified fraction of cumulative variance explained (float `0.0–1.0`) [10, 26].
  * Echo-based criteria (`kundu` or `kundu-stabilize`): Decision-tree filtering that retains components exhibiting \\(T_2^*\\) or \\(S_0\\) signal structure [10, 25, 26].
* Reconstructs a dimensionally reduced dataset and saves the PCA mixing matrix (`desc-PCA_mixing.tsv`) [20, 22, 26].

#### 5. TEDICA (Independent Component Analysis Decomposition)
* **Spatial Component Estimation**: Subject the dimensionally reduced data to spatial ICA via `tedica()` using either a single FastICA run (`ica_method='fastica'`) or repeated runs with clustering via RobustICA (`ica_method='robustica'`) [10, 26-28].
* **Outputs**: Extracts independent component time series (`desc-ICA_mixing.tsv`) and spatial loading maps (`desc-ICA_components.nii.gz`) [18, 26, 29].

#### 6. TE-Dependence Classification & Final Denoising
* **Metric Calculation**: Evaluates how component spatial loadings scale across echo times to calculate two key goodness-of-fit parameters [23, 30, 31]:
  * **\\(\kappa\\) (Kappa)**: Measures \\(T_2^*\\) dependence, characteristic of neural BOLD signal [2, 30, 31].
  * **\\(\rho\\) (Rho)**: Measures \\(S_0\\) dependence, characteristic of non-BOLD noise (e.g., participant movement, scanner drift, or vascular artifacts) [2, 30, 31].
* **Decision Tree Classification (`--tree`)**: Passes metrics through a decision tree (`tedana_orig` by default, `meica`, `minimal`, or a custom user-defined JSON tree) to classify each component as **accepted** (BOLD signal), **rejected** (non-BOLD noise), or **ignored** (low-variance) [2, 10, 30, 32].
* **Denoising Regression**: The time series of all rejected noise components are regressed out from the optimally combined dataset, yielding the clean time series (`desc-denoised_bold.nii.gz`) [9, 18, 29, 32, 33].
* **Optional Diffuse Noise Control (`--gscontrol`)**: Post-processing options such as Global Signal Regression (`gsr`) or Minimum Image Regression (`mir`) can be applied to remove spatially diffuse respiration-related noise [28, 34-36].

---

### Pipeline Outputs

Tedana outputs structured derivatives, metadata sidecars, and interactive visual reports [18, 37, 38]:

| Output Type | Key / Filename Pattern | Description |
| :--- | :--- | :--- |
| **Core Datasets** | `desc-optcom_bold.nii.gz` | Optimally combined multi-echo 4D time series [18, 19]. |
| | `desc-denoised_bold.nii.gz` | Final denoised 4D BOLD time series (noise components regressed) [18, 29]. |
| **Masks & Maps** | `desc-adaptiveGoodSignal_mask.nii.gz` | Voxel-wise integer map indicating number of good echoes [18]. |
| | `T2starmap.nii.gz` | Full estimated 3D \\(T_2^*\\) relaxation time map (in ms) [18, 39]. |
| | `S0map.nii.gz` | Full estimated 3D \\(S_0\\) signal intensity map [18]. |
| **Tables & Matrices** | `desc-PCA_mixing.tsv` | PCA mixing matrix time series [18, 20, 22]. |
| | `desc-ICA_mixing.tsv` | ICA component mixing matrix (time series for each component) [18, 26]. |
| | `desc-ICA_components.nii.gz` | 4D image containing spatial component weight maps [18, 26, 29]. |
| | `desc-tedana_metrics.tsv` | Table tracking \\(\kappa\\), \\(\rho\\), variance explained, final status (`accepted`/`rejected`), and classification rationale tags for each component [30, 31, 40, 41]. |
| **Diagnostics & Reports** | `tedana_report.html` | Interactive HTML report displaying Kappa/Rho elbow plots, variance pie charts, component maps, and time series [18, 31, 37]. |
| | `open_rica_report.py` / `/rica/` | Launcher script and web-based interactive 3D viewer using NiiVue for component inspection [42]. |
| | `report.txt` | Plain-text citable summary detailing workflow steps, parameters, and references [14]. |
| | `desc-tedana_registry.json` | Registry mapping internal output keys to generated output file paths [18, 38, 43]. |

*(Note: Setting `verbose=True` outputs additional intermediate files, such as echo-split denoised/rejected time series `echo-[echo]_desc-Denoised_bold.nii.gz`)* [37, 44, 45].

---

### Required File Structures & Requirements

#### Input Requirements
1. **Functional Datasets (`-d` / `--data`)**:
   * Functional NIfTI time series files listed in ascending echo order (e.g., `echo-1_bold.nii.gz`, `echo-2_bold.nii.gz`, `echo-3_bold.nii.gz`), or a single \\(z\\)-concatenated dataset [10, 46, 47].
   * Requires a **minimum of 3 echoes** for TE-dependent ICA denoising [11, 48].
2. **Echo Times (`-e` / `--tes`)**:
   * Echo times matching the input datasets in ascending order, supplied in seconds per BIDS convention (e.g., `-e 0.014 0.028 0.042`) [10, 46, 47].
3. **Preprocessing Standards**:
   * All echoes must be preprocessed together [4, 49]. Motion correction transforms **must be calculated from a single echo (typically the earliest echo)** and applied uniformly across all echoes to avoid mean-shifting or differential scaling [49].

#### File Naming Conventions (`--convention`)
* **`bids` (default)**: Adheres to BIDS Derivatives specification v1.5.0 format (e.g., `sub-01_task-rest_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz`) [10, 38, 47]. BIDS dataset metadata (`_bold.json`) contains the `EchoTime` headers [24].
* **`orig`**: Uses legacy file naming conventions [10, 38, 47].

#### Integration with Standard Pipelines
* **fMRIPrep Integration**: In `fMRIPrep` versions \\(\ge 21.0.0\\), using the `--me-output-echos` flag saves individual preprocessed per-echo time series, allowing users to pass them directly to Tedana for multi-echo denoising before applying spatial normalization transforms [46, 50].
* **AFNI Integration**: AFNI provides an internal wrapper (`tedana_wrapper.py`) that can be invoked directly inside `afni_proc.py` pipelines (such as Example 12) [4, 51, 52].

---