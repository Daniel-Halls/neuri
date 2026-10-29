### What QSIRecon Does

**QSIRecon** is a modular, containerized BIDS App built in Python 3.10 using Nipype [1]. It performs post-processing, model fitting, q-space reconstruction, fiber tractography, scalar mapping, and structural connectome construction on preprocessed diffusion MRI (dMRI) data [1-4]. While primarily designed to ingest preprocessed outputs from **QSIPrep**, it can also process datasets from the UK Biobank (`ukb`) or Human Connectome Project (`hcpya`) minimal preprocessing pipelines via the `--input-type` parameter [5, 6].

Key core functions include:
* **Framework Interoperability**: Converts outputs between package-native file formats (e.g., MRtrix3 `.mif` spherical harmonics) and standardized formats like DSI Studio `.fib` files [7, 8].
* **Standardized Connectomics**: Generates structural connectivity matrices across multiple built-in parcellation atlases in a unified structure [9, 10].
* **Configurable Workflows**: Uses YAML-based reconstruction specs (`--recon-spec`) to chain together algorithms across different software tools [6, 11, 12].

---

### Reconstruction Workflows by Framework

QSIRecon integrates developer-recommended workflows across major neuroimaging toolkits [4, 6, 13]:

#### 1. DIPY (Diffusion Imaging in Python)
* **`dipy_mapmri`**: Fits the Mean Apparent Propagator (MAP) MRI model analytically on multi-shell, Cartesian, or random q-space sampling data [14, 15]. It estimates Ensemble Average Propagators (EAPs), ODFs, and EAP-derived scalars (RTOP, RTAP, RTPP, QIV, MSD) [14, 15]. ODFs are exported in DSI Studio format and optionally as spherical harmonic coefficients in MRtrix3 format [15].
* **`dipy_3dshore`**: Uses the BrainSuite 3dSHORE basis set to model EAPs and compute scalar maps (RTOP, RTAP, RTPP, MSD, CNR, and alpha) [14, 15]. Reconstructed ODFs are passed to DSI Studio for deterministic tractography [14, 15].
* **`dipy_dki`**: Performs Diffusion Kurtosis Imaging fitting to estimate axial, radial, and mean kurtosis metrics from multi-shell data [16, 17].
* **`csdsi_3dshore`**: An experimental workflow for DSI/CS-DSI data [18, 19]. It fits an L2-regularized 3dSHORE model to compute ODFs for DSI Studio tractography and imputes multi-shell signal to feed into MRtrix3 MSMT-CSD pipelines [18, 19].

#### 2. MRtrix3
* **Multi-Shell & Single-Shell CSD**: Offers Multi-Tissue Constrained Spherical Deconvolution (`mrtrix_multishell_msmt`) for multi-shell data and Single-Shell 3-Tissue CSD (`mrtrix_singleshell_ss3t`) for single-shell data to extract white matter Fiber Orientation Distributions (fODFs) [17, 20, 21].
* **Anatomical Constraints & Filtering**: Incorporates Anatomically-Constrained Tractography (ACT) using either FAST-based tissue segmentation or FreeSurfer-derived Hybrid Surface-Volume Segmentation (`mrtrix_5tt_hsvs`) [17, 22, 23]. Employs probabilistic `iFOD2` tractography followed by SIFT/SIFT2 filtering to eliminate tractogram density biases [24-26].

#### 3. DSI Studio
* **`dsi_studio_gqi`**: Reconstructs water diffusion ODFs using Generalized Q-Sampling Imaging (GQI) [27, 28]. Computes Quantitative Anisotropy (QA), Generalized Fractional Anisotropy (GFA), and isotropic diffusion (ISO) across shelled, non-shelled, or Cartesian sampling schemes [27, 28]. Deterministic tractography generates 5 million streamlines [28].
* **`dsi_studio_autotrack`**: Performs Q-Space Diffeomorphic Reconstruction (QSDR, MNI-space GQI) followed by automated tractography (`autotrack`) to segment 56 predefined white matter pathways based on an HCP population tractography atlas [2, 29].
* **`ss3t_fod_autotrack`**: Replaces GQI fitting in `dsi_studio_autotrack` with MRtrix3 `ss3t_csd_beta1` white matter fODFs while maintaining automated bundle tracking [20].

#### 4. AMICO
* **`amico_noddi`**: Accelerated fitting of the Neurite Orientation Dispersion and Density Imaging (NODDI) model [30, 31]. Generates intracellular volume fraction (ICVF), isotropic volume fraction (ISOVF), orientation dispersion (OD), tissue-fraction-modulated ICVF/OD, and model error (RMSE) maps [27, 30]. A DSI Studio `.fib` file is also created using peak directions and ICVF for tracking/visualization [27, 30].

---

### Outputs Generated

QSIRecon structures its outputs into self-contained BIDS-Derivative datasets under `results/qsirecon/` or method-specific subdirectories (e.g., `qsirecon-DSIStudio/`, `qsirecon-DKI/`) [32-34]:

* **ODF / fODF Files**: Exported in software-native formats (e.g., MRtrix3 `.mif` spherical harmonics) and converted into standardized DSI Studio `.fib.gz` files (`*space-ACPC|T1w*_dwimap.fib.gz`) containing ODF geometries and peak directions [2, 8, 15, 27].
* **Tractograms & Bundle Statistics**:
  * Whole-brain streamline tractograms (`.tck`) and individual white matter bundles (`*model-<model>_streamlines.tck.gz`) aligned to ACPC/T1w space [20, 29, 35].
  * Tabular stats: Bundle scalar statistics (`*_scalarstats.csv`/`.tsv`) summarizing mean length, span, volume, and scalar metrics along pathways, as well as streamline density stats (`*_tdistats.tsv`) [20, 29, 35].
* **Connectivity Matrices**:
  * Bundled inside binary MATLAB `.mat` files (`<source_entities>_connectivity.mat`) located in the subject's `dwi/` directory [9, 36]. These contain dictionary keys for parcel region IDs, labels, and matrices across multiple atlases [25, 36].
  * **MRtrix3 Matrix Weightings**: Raw streamline count (`count`), SIFT-weighted count (`sift.count`), mean length (`meanlength`), and SIFT-weighted mean length (`sift.meanlength`) across specified search radii [25].
  * **DSI Studio Matrix Weightings**: End-point (`end`) vs. pass-through (`pass`) connectivity, with metrics for raw count (`count`), length-normalized count (`ncount`), mean length (`mean_length`), and mean GFA along streamlines [37].
  * **Atlases Included**: Schaefer (100–1000 parcels), Brainnetome246, AICHA384, Gordon333, AAL116, and the synchronized 4S atlas [9, 38]. Custom atlases can be supplied via `--atlases` [9].
* **Scalar Maps**: 3D NIfTI files (`*_dwimap.nii.gz`) and JSON sidecars for all model-derived scalar metrics (FA, MD, AD, RD, GFA, QA, ISO, ICVF, ISOVF, OD, RTOP, RTAP, RTPP, MSD, etc.) [14, 27, 34, 35, 39].
* **Visual Reports**: Subject-level HTML files (`sub-<label>.html`) containing summary figures, sampling scheme plots, and ODF fit quality checks [32-34].

---

### Required File Structures (QSIPrep Derivatives)

QSIRecon expects the input directory (`input_dir`) to contain preprocessed BIDS-Derivative outputs organized under the standard QSIPrep layout (`<input_dir>/qsiprep/sub-<label>/[ses-<label>/]`) [5, 11, 40, 41]:

```text
qsiprep/
├── dataset_description.json
└── sub-<label>/
    └── [ses-<label>/]
        ├── anat/
        │   ├── <source_entities>_space-ACPC_desc-preproc_T1w.nii.gz    # ACPC-aligned T1w image
        │   ├── <source_entities>_space-ACPC_desc-brain_mask.nii.gz     # ACPC brain mask
        │   ├── <source_entities>_space-ACPC_label-CSF_probseg.nii.gz  # Tissue probability maps
        │   ├── <source_entities>_space-ACPC_label-GM_probseg.nii.gz
        │   ├── <source_entities>_space-ACPC_label-WM_probseg.nii.gz
        │   ├── <source_entities>_space-ACPC_dseg.nii.gz               # Tissue segmentation map
        │   └── <source_entities>_from-ACPC_to-<space>_mode-image_xfm.h5 # Template transform files
        └── dwi/
            ├── <source_entities>_space-ACPC_desc-preproc_dwi.nii.gz  # Resampled preprocessed DWI
            ├── <source_entities>_space-ACPC_dwiref.nii.gz             # Diffusion reference image
            ├── <source_entities>_space-ACPC_desc-preproc_dwi.bval     # FSL bval/bvec & MRtrix .b
            ├── <source_entities>_space-ACPC_desc-preproc_dwi.bvec     # (rotated gradient vectors)
            └── <source_entities>_desc-confounds_timeseries.tsv        # Motion & confound table
```

#### External Requirements:
* **FreeSurfer Directory** (Optional): If utilizing surface-based parcellations or MRtrix3 HSVS (`mrtrix_5tt_hsvs`), pre-computed FreeSurfer outputs must be supplied using the `--fs-subjects-dir` argument [6, 12, 23].