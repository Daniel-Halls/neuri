**Nilearn** is an open-source Python library within the **NiPy ecosystem** designed for statistical and machine-learning analyses on neuroimaging volumes and surfaces [1-4]. It leverages **scikit-learn** to apply multivariate statistical methods—such as predictive modeling, classification, decoding, and functional connectivity—directly to brain imaging data [1, 4, 5].

---

### 1. Core Capabilities

Nilearn provides specialized tools covering the complete post-preprocessing neuroimaging analysis pipeline [6, 7]:

* **General Linear Model (GLM) Analysis**: Enables single-subject (first-level) and group-level (second-level) mass-univariate statistical analyses for fMRI data [5, 7-9].
* **Decoding & Multivariate Pattern Analysis (MVPA)**: Uses supervised machine learning to predict cognitive states, tasks, or clinical phenotypes from brain patterns [5, 6, 10, 11].
* **Functional Connectivity & Connectomics**: Calculates interaction matrices across brain regions using seed-based correlation, sparse inverse covariance, or tangent space embeddings [6, 12-15].
* **Brain Parcellation & Region Extraction**: Learns data-driven spatial decompositions and parcels via clustering methods (such as Ward, \\(k\\)-means, ReNA) or spatial decomposition techniques like Independent Component Analysis (ICA) and Dictionary Learning [6, 10, 16-18].
* **Image Preprocessing & Feature Extraction**: Performs spatial smoothing, temporal bandpass filtering, detrending, confound regression, and volume censoring/scrubbing [7, 8, 19, 20].
* **Visualization & Interactive Reporting**: Provides plotting routines for statistical maps, glass brain projections, connectome graphs, surface renders, and interactive 3D HTML reports [5, 21-26].

---

### 2. Supported Neuroimaging Data Representations

Nilearn supports both volumetric and surface-based neuroimaging data representations [2, 27, 28]:

1. **Volumetric Data**: Represents 3D anatomical images or 4D time-series volumes stored in NIfTI format (`.nii`, `.nii.gz`) through **NiBabel** `Niimg-like` objects [7, 8, 28, 29].
2. **Surface Data**: Represents cortical surface meshes and vertex data (e.g., FreeSurfer `fsaverage` templates) using objects such as `SurfaceImage`, `PolyMesh`, and `SurfaceMesh` to handle separate left and right hemisphere meshes [27, 28, 30-33].
3. **Data Matrices via Masker Objects**: Nilearn converts spatial images into 2D NumPy arrays (\\(\text{samples} \times \text{features}\\)) required by machine-learning algorithms via the `nilearn.maskers` module [7, 28, 34, 35]:
   * **Volumetric Maskers**: `NiftiMasker`, `MultiNiftiMasker`, `NiftiLabelsMasker`, `MultiNiftiLabelsMasker`, `NiftiMapsMasker`, `MultiNiftiMapsMasker`, and `NiftiSpheresMasker` [8, 13, 19, 28, 36, 37].
   * **Surface Maskers**: `SurfaceMasker`, `MultiSurfaceMasker`, `SurfaceLabelsMasker`, `MultiSurfaceLabelsMasker`, `SurfaceMapsMasker`, and `MultiSurfaceMapsMasker` [28].

---

### 3. Statistical and Machine Learning Workflows

#### **A. General Linear Model (GLM) Workflows**
* **First-Level Analysis (`FirstLevelModel`)**: Fits a linear regression at each voxel or vertex to model task-evoked BOLD responses [8, 31, 38]. 
  * Convolves task event onsets with Hemodynamic Response Functions (HRFs), such as Glover or SPM models (with optional time/dispersion derivatives) [8, 20, 31, 38].
  * Models temporal autocorrelation using Generalized Least Squares (GLS) with an AR(1) noise model and removes low-frequency drifts using cosine bases [20, 38].
  * Integrates nuisance regressors (e.g., motion parameters, CompCor high-variance confounds) and volume censoring sample masks [20, 39].
  * Computes run-specific contrast maps (\\(t\\)- or \\(F\\)-tests) and fixed-effects combinations across multiple runs using `compute_fixed_effects` [8, 40].
* **Second-Level Analysis (`SecondLevelModel`)**: Performs group-level analyses across subjects (one-sample t-tests, two-sample t-tests, or linear regressions) to produce group \\(Z\\)-score maps [9, 41-43].
* **Multiple Comparisons Correction**: Provides false discovery rate (FDR) thresholding, family-wise error rate (FWER) control, and cluster-level inference (such as All-Resolution Inference) [9, 41].

#### **B. Decoding and MVPA Workflows**
* **High-Level Composite Estimators**:
  * `Decoder` / `DecoderRegressor`: Automates cross-validated classification or regression, including feature selection (ANOVA) and hyperparameter tuning [10, 11, 44, 45].
  * `FREMClassifier` / `FREMRegressor`: Implements **Fast Ensembling of Regularized Models** (FREM), which uses spatial clustering and multi-fold model aggregation for robust predictions [46, 47].
  * `SpaceNetClassifier` / `SpaceNetRegressor`: Employs spatial penalties like TV-L1 or Graph-Net to yield structured, interpretable coefficient maps [46].
  * **Searchlight**: Runs a local classifier across spherical neighborhoods to identify informative brain regions [3, 48].
* **Scikit-Learn Integration**: Custom pipelines can combine Nilearn maskers with `scikit-learn` objects (e.g., `Pipeline`, `SelectPercentile`, `LinearSVC`, `Ridge`, `KFold`, `StratifiedShuffleSplit`) [11, 49-52].

#### **C. Functional Connectivity & Parcellation Workflows**
* **Signal Extraction**: Extracts cleaned time-series from region-of-interest (ROI) spheres (`NiftiSpheresMasker`), deterministic atlases (`NiftiLabelsMasker`), or probabilistic maps (`NiftiMapsMasker`) [13, 19, 36, 37].
* **Connectome Estimation (`ConnectivityMeasure`)**: Computes functional connectivity matrices using Pearson correlation, partial correlation, or tangent space embedding [15, 51, 52].
* **Sparse Graph Estimation**: Uses `GraphicalLassoCV` and `GroupSparseCovarianceCV` to estimate direct connections by recovering sparse precision (inverse covariance) matrices [13, 14, 21, 53].
* **Parcellation Algorithms (`Parcellations`, `ReNA`, `RegionExtractor`)**: Groups voxels into parcellations using spatially constrained Ward hierarchical clustering, \\(k\\)-means, or Recursive Neighbor Agglomeration [10, 16-18].

#### **D. Encoding Models**
* Fits voxel-wise regression models (e.g., Ridge regression) to predict brain activity patterns directly from external stimulus properties, such as binary visual pixel patterns [50, 54, 55].

---

### 4. Outputs Generated

* **Statistical Maps**: Volumetric or surface 3D/4D maps representing \\(Z\\)-scores, \\(t\\)-statistics, parameter estimates (\\(\beta\\) maps), effect sizes, and variance estimates [8, 9, 40, 46, 56].
* **Weight/Coefficient Maps**: Spatial maps generated by decoding models (`coef_img_`), revealing voxels or vertices contributing to classification or regression predictions [44, 46, 49].
* **Parcellation & Component Maps**: 3D/4D brain maps representing functional clusters, ICA spatial components, or learned brain dictionaries [10, 16, 18, 57].
* **Connectome Matrices**: 2D square matrices containing covariance, correlation, partial correlation, or precision values between ROIs [13, 21, 53].
* **Reports and Visual Artifacts**: Static glass brain plots, 2D slice overlays, connectome graph diagrams, and interactive HTML reports generated via `generate_report()`, `view_img()`, or `view_connectome()` [8, 11, 22, 23, 25, 56].
* **BIDS-Compliant Statistical Derivatives**: Output directories created via `save_glm_to_bids()`, structured according to BIDS conventions [56].

---

### 5. Required File Structures and BIDS Integration

Nilearn natively integrates with the **Brain Imaging Data Structure (BIDS)** format [39, 58, 59]:

* **BIDS Input Datasets**: Expects standard BIDS directory layouts containing functional volumes (`*_bold.nii.gz`), event timing tables (`*_events.tsv` with `onset`, `duration`, and `trial_type` columns), and metadata files (`dataset_description.json`, `bold.json`) [39, 58-60].
* **BIDS Derivatives (e.g., fMRIPrep)**: Automatically parses derivative folders (e.g., `derivatives/fmriprep`) to fetch preprocessed functional scans in standard spaces (`*_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz`) and confound regressors (`*_desc-confounds_timeseries.tsv` or `*_desc-reducedConfounds_regressors.tsv`) [39, 58, 61].
* **Automated BIDS Model Ingestion**: The `first_level_from_bids()` helper function scans a BIDS directory and automatically constructs ready-to-fit `FirstLevelModel` instances with associated run images, event matrices, and confound tables [39, 58].
* **BIDS Output Export**: Using `save_glm_to_bids()`, fitted model contrasts and reports are written out to a standard BIDS derivatives hierarchy under `derivatives/nilearn_glm/` [56].

---