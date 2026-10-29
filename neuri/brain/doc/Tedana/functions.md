The **`tedana`** (TE-Dependent ANAlysis) Python package provides a modular framework for preprocessing, model fitting, echo combination, dimensionality reduction, component selection, and denoising of multi-echo fMRI data [1, 2].

Below is an overview of the modules, workflows, functions, classes, key parameters, and practical applications documented in the sources.

---

### 1. `tedana.workflows` — Primary Pipelines & CLI Utilities
This module provides high-level execution pipelines that wrap the lower-level processing steps into standard workflows [3].

* **`tedana_workflow(data, tes, out_dir='.', mask=None, convention='bids', prefix='', dummy_scans=0, masktype=['dropout'], fittype='loglin', combmode='t2s', tree='tedana_orig', ica_method='fastica', n_robust_runs=30, tedpca='aic', fixed_seed=42, maxit=500, maxrestart=10, tedort=False, gscontrol=None, low_mem=False, n_threads=1, ...)`**
  * **What it does**: Executes the canonical end-to-end TE-dependent analysis pipeline: adaptive mask creation, \\(T_2^*/S_0\\) decay model fitting, optimal echo combination, TEDPCA dimensionality reduction, TEDICA, component metric calculation, decision tree classification, and non-aggressive denoising [2, 4-6].
  * **Key Parameters**:
    * `data`: Input NIfTI image path(s) (either echo-specific files or a single concatenated file) [7].
    * `tes`: Echo times in seconds (BIDS convention) or milliseconds [7, 8].
    * `fittype`: `'loglin'` (fast log-linear regression) or `'curvefit'` (non-linear monoexponential curve fitting) [9, 10].
    * `tedpca`: Dimensionality reduction criterion (`'aic'`, `'kic'`, `'mdl'`, `'kundu'`, `'kundu-stabilize'`, or a variance percentage float/int) [10, 11].
    * `tree`: Decision tree strategy for component classification (`'tedana_orig'`, `'meica'`, `'minimal'`, or a custom JSON path) [10, 12].
    * `ica_method`: `'fastica'` (single FastICA run) or `'robustica'` (repeated ICA runs with clustering) [10, 13].
    * `gscontrol`: Global signal control method (`'mir'`, `'gsr'`, or `None`) [14, 15].
  * **Use Case**: Standard automated multi-echo fMRI denoising after spatial preprocessing [1, 4].

* **`t2smap_workflow(data, tes, out_dir='.', mask=None, dummy_scans=0, exclude=None, masktype=['dropout'], fittype='loglin', ...)`**
  * **What it does**: Estimates voxel-wise \\(T_2^*\\) and \\(S_0\\) parameter maps and generates an optimally combined time series dataset without performing full ICA decomposition or component-based denoising [16, 17].
  * **Use Case**: Obtaining \\(T_2^*\\) maps or optimally combined multi-echo fMRI data when component denoising is not required [16, 17].

* **`ica_reclassify_workflow(registry, accept=None, reject=None, ...)`**
  * **What it does**: Takes the registry/outputs from a previous `tedana` run, applies manual component classification adjustments (e.g., from interactive tools like RICA), and re-generates denoised time series and reports [18, 19].
  * **Use Case**: Manual quality control or overriding automatic decision tree classifications [18, 19].

* **`parser_utils` Submodule**:
  * **`check_tedpca_value(value)`**: Validates the `--tedpca` CLI input [8].
  * **`check_n_robust_runs_value(string)`**: Validates the number of RobustICA iterations [20].
  * **`is_valid_file(parser, arg)`**, **`parse_manual_list_int()`**, **`parse_manual_list_str()`**: Parse and validate manual component lists and input paths [21-24].

---

### 2. `tedana.decay` — Signal Decay Modeling
Functions in this module fit monoexponential decay models (\\(S(TE) = S_0 \cdot e^{-TE / T_2^*}\\)) across echoes to derive voxel-wise \\(T_2^*\\) and \\(S_0\\) estimates [2, 21, 25, 26].

* **`fit_decay(data, tes, adaptive_mask, fittype, report=True, n_threads=1)`**
  * **What it does**: Fits voxel-wise monoexponential decay models across echoes using either log-linear (`'loglin'`) or non-linear (`'curvefit'`) regression [21, 27, 28].
  * **Parameters**: Multi-echo data array, echo times, adaptive mask, and fitting method [27]. Returns \\(T_2^*\\) and \\(S_0\\) maps, variance maps, and failure masks [28].
  * **Use Case**: Main decay fitting step across the entire brain volume [26].

* **`fit_decay_ts(data, tes, adaptive_mask, fittype, n_threads=1)`**
  * **What it does**: Fits \\(T_2^*\\) and \\(S_0\\) models on a volume-by-volume (voxel- and timepoint-wise) basis [21, 29].
  * **Use Case**: Volume-wise \\(T_2^*\\) fluctuation analysis (`--fitmode ts`) [16, 30].

* **`fit_loglinear(data_cat, echo_times, adaptive_mask, report=True)`**
  * **What it does**: Transforms raw BOLD signal (\\(\log(|S| + 1)\\)) and uses ordinary least squares linear regression against negative echo times to compute \\(T_2^* = 1 / \text{slope}\\) and \\(S_0 = e^{\text{intercept}}\\) [16, 29, 31].
  * **Use Case**: Fast linear estimation of decay parameters [29].

* **`fit_monoexponential(data_cat, echo_times, adaptive_mask, report=True, n_threads=1)`**
  * **What it does**: Fits a non-linear monoexponential curve directly to raw untransformed data using non-linear curve fitting [16, 32].
  * **Use Case**: Computationally demanding but highly accurate \\(T_2^*\\) and \\(S_0\\) estimation [16, 32].

* **`monoexponential(tes, s0, t2star)`**
  * **What it does**: Evaluates the monoexponential signal decay formula \\(S = S_0 \cdot e^{-TE / T_2^*}\\) for given echo times [25, 33].
  * **Use Case**: Objective function passed to `scipy.optimize.curve_fit` [25].

* **`modify_t2s_s0_maps(t2s, s0, adaptive_mask, tes)`**
  * **What it does**: Adjusts full \\(T_2^*\\) and \\(S_0\\) maps to handle voxels where good signal exists in only one or two echoes [16, 33].
  * **Use Case**: Preventing invalid or undefined fits in dropout regions [16, 33].

* **`rmse_of_fit_decay_ts(data, tes, adaptive_mask, t2s, s0, fitmode)`**
  * **What it does**: Computes the mean Root Mean Squared Error (RMSE) map and time series metrics evaluating the quality of the decay model fit [30, 34, 35].
  * **Use Case**: Generating diagnostic decay model fit plots and summary statistics [22, 36].

---

### 3. `tedana.combine` — Echo Combination
Methods in this module combine multi-echo time series into a single optimized dataset [2, 37].

* **`make_optcom(data, tes, adaptive_mask, t2s=None, combmode='t2s')`**
  * **What it does**: Calculates echo-specific weights for each voxel based on estimated \\(T_2^*\\) values (\\(w(T_2^*)_n = \frac{TE_n \cdot e^{-TE_n / T_2^*}}{\sum TE_m \cdot e^{-TE_m / T_2^*}}\\)) and computes a weighted average time series across echoes [37-39].
  * **Parameters**: Multi-echo data, echo times, adaptive mask, \\(T_2^*\\) map, and combination scheme (`'t2s'` or `'paid'`) [39].
  * **Use Case**: Maximizing functional contrast-to-noise ratio while preserving early-echo signal in dropout zones [37, 39].

---

### 4. `tedana.decomposition` — Data Decomposition (TEDPCA & TEDICA)
Handles dimensionality reduction and independent component decomposition [2, 40, 41].

* **`tedpca(data_cat, data_optcom, mask, adaptive_mask, io_generator, tes, n_independent_echos=None, algorithm='aic', kdaw=10.0, rdaw=1.0, low_mem=False)`**
  * **What it does**: Applies Principal Component Analysis (PCA) to the optimally combined data to filter thermal noise and determine the target number of components for subsequent ICA [40, 42, 43].
  * **Algorithms**: Moving average information criteria (`'aic'`, `'kic'`, `'mdl'`), cumulative variance thresholding (float), fixed integer, or decision-tree approaches (`'kundu'`, `'kundu-stabilize'`) based on \\(\kappa\\) (Kappa) and \\(\rho\\) (Rho) metrics [11, 43, 44].
  * **Use Case**: Pre-ICA dimensionality reduction [40].

* **`tedica(data, n_components, fixed_seed, ica_method='fastica', n_robust_runs=30, maxit=500, maxrestart=10, n_threads=1)`**
  * **What it does**: Runs spatial Independent Component Analysis (ICA) on the dimensionally reduced data to separate spatial components and time courses [41, 45, 46].
  * **Use Case**: Decomposing fMRI data into independent spatial maps and mixing time series [41, 45].

* **`ica.f_ica(data, n_components, fixed_seed, maxit, maxrestart)`**
  * **What it does**: Wrapper executing a single iteration of FastICA via `scikit-learn` [47-49].

* **`ica.r_ica(data, n_components, fixed_seed, n_robust_runs=30, maxit=500, n_threads=1)`**
  * **What it does**: Runs multiple iterations (`n_robust_runs`) of FastICA using `RobustICA` and clusters the resulting component estimates for improved stability and convergence [13, 50, 51].

---

### 5. `tedana.metrics` — TE-Dependence & Component Metrics
Computes diagnostic statistical metrics for each decomposed component to evaluate TE-dependence (BOLD signal) versus TE-independence (non-BOLD noise) [2, 52, 53].

#### `tedana.metrics.collect`
* **`generate_metrics(data_cat, data_optcom, mixing, adaptive_mask, tes, ...)`**: Primary driver that fits \\(T_2^*\\) (TE-dependent) and \\(S_0\\) (TE-independent) regression models across echoes for each component time course and outputs a populated component metric table (`component_table`) [54-56].
* **`get_metadata(component_table)`**: Retrieves metadata descriptions for columns in `component_table` [54, 57].

#### `tedana.metrics.dependence`
* **`calculate_f_maps(data_cat, mixing, adaptive_mask, tes, ...)`**: Calculates voxel-wise pseudo-\\(F\\)-statistic maps for \\(T_2^*\\) (\\(F_{T2^*}\\)) and \\(S_0\\) (\\(F_{S0}\\)) models across echoes [58-60].
* **`calculate_dependence_metrics(f_t2_maps, f_s0_maps, z_maps)`**: Computes **\\(\kappa\\) (Kappa)** (weighted average \\(F\\)-stat for \\(T_2^*\\) dependence) and **\\(\rho\\) (Rho)** (weighted average \\(F\\)-stat for \\(S_0\\) independence) across voxels [52, 58, 59, 61].
* **`calculate_betas(data, mixing)`** & **`calculate_weights(data_optcom, mixing)`**: Compute unstandardized parameter estimates and standardized weight maps [58, 62, 63].
* **`calculate_z_maps(weights, z_max=8)`**: Converts standardized spatial weights into \\(Z\\)-statistic spatial maps [58, 64, 65].
* **`calculate_marginal_r2`**, **`calculate_partial_r2`**, **`calculate_semipartial_r2`**, **`calculate_total_r2`**: Calculate voxel-averaged variance explained metrics for components [58, 61, 66-68].
* **`calculate_psc(data_optcom, optcom_betas)`**: Calculates percent signal change spatial maps [58, 60, 69].
* **`compute_countnoise(...)`** & **`compute_countsignal(...)`**: Count significant non-cluster (noise) vs. cluster (signal) voxels in \\(F\\)-statistic maps [70-74].
* **`compute_dice(clmaps1, clmaps2)`**: Computes Dice Similarity Index (DSI) between thresholded component spatial maps and \\(F\\)-statistic maps [70, 75, 76].
* **`compute_signal_minus_noise_t(...)`** & **`compute_signal_minus_noise_z(...)`**: Perform two-sample t-tests/z-tests comparing \\(F\\)-statistics in cluster vs. non-cluster voxels [70, 77-79].
* **`compute_kappa_rho_difference(kappa, rho)`**: Evaluates the proportion of pseudo-\\(F\\)-stats dominated by \\(\kappa\\) versus \\(\rho\\) [70, 80, 81].
* **`generate_decision_table_score(ascending, descending)`**: Calculates ranked multi-metric decision table scores (`d_table_score`) [54, 56, 82, 83].

#### `tedana.metrics.external`
* **`fit_regressors(...)`**, **`fit_mixing_to_regressors(...)`**, **`build_fstat_regressor_models(...)`**, **`compute_external_regressor_correlations(...)`**, **`validate_extern_regress(...)`**: Fit external nuisance regressors (e.g., motion parameters, physiological noise) or task vectors to ICA mixing time series and validate regressor input matrices [58, 70, 81, 84-87].

---

### 6. `tedana.selection` — Decision Trees & Component Selection
Evaluates calculated component metrics against structured decision rules to classify components as accepted (BOLD), rejected (non-BOLD), or ignored [2, 52, 53, 88].

* **`component_selector.ComponentSelector(tree, out_dir='.')`**
  * **What it does**: Class for loading decision tree specifications (`tedana_orig`, `meica`, `minimal`, or custom JSON files), executing decision tree functions sequentially, maintaining classification state (`accepted_comps_`, `rejected_comps_`), and exporting results [53, 70, 89-91].

* **`tedica.automatic_selection(component_table, selector)`**
  * **What it does**: Driver function executing automatic component selection on `component_table` using a initialized `ComponentSelector` object [86, 89, 92, 93].

* **`tedpca.kundu_tedpca(component_table, n_echos, ...)`**
  * **What it does**: Implements Kundu's decision tree algorithm specifically for PCA component selection [23, 94, 95].

* **`selection_nodes` Submodule**:
  * Individual decision tree node functions, including `calc_extend_factor`, `calc_kappa_elbow`, `calc_rho_elbow`, `calc_median`, `dec_reclassify_high_var_comps`, `dec_variance_lessthan_thresholds`, `dec_classification_doesnt_exist`, and `manual_classify` [47, 58, 78, 80, 85, 90, 96, 97].

* **`selection_utils` Submodule**:
  * Helper functions for curve elbow detection and logging: `getelbow` (linear projection method), `getelbow_cons` (conservative mean/variance method), `rho_elbow_kundu_liberal`, `get_extend_factor`, `log_classification_counts`, `log_decision_tree_step`, `clean_dataframe`, `change_comptable_classifications`, and `selectcomps2use` [8, 25, 34, 54, 70, 94, 95, 98-104].

---

### 7. `tedana.gscontrol` — Global Signal Control
Provides optional post-processing denoising strategies for spatially diffuse noise [2, 105].

* **`gscontrol_raw(data_cat, data_optcom, n_echos, io_generator, dtrank=4)`**
  * **What it does**: Performs global signal regression (GSR) across time series [45, 106].

* **`minimum_image_regression(data_optcom, mixing, mask, component_table, ...)`**
  * **What it does**: Executes Minimum Image Regression (MIR) to remove \\(T_1\\)-like noise effects from BOLD-like components [46, 107, 108].
  * **Use Case**: Advanced removal of persistent spatially diffuse noise [105, 108].

---

### 8. `tedana.io` — File Handling & Data Export
Handles data input, file registry, and saving outputs in BIDS or legacy formats [2, 105, 109].

* **`OutputGenerator(reference_img, convention='bidsv1.5.0', out_dir='.', prefix=None, config='auto', ...)`**
  * **What it does**: Primary class managing file path resolution, BIDS naming conventions, directory creation, mask registration, and saving outputs to disk [30, 89, 93, 109, 110].
  * **Methods**: `register_mask`, `save_file`, `save_img`, `save_json`, `save_tsv`, `add_df_to_file`, `add_dict_to_file`, `save_self` [30, 93, 98, 111].

* **`InputHarvester`**: Parses registry files from prior runs to reconstruct parameters and outputs for re-use [89, 102, 104, 106].

* **`denoise_ts(data, mixing, mask, component_table)`**
  * **What it does**: Regresses the mixing time series of rejected components from the optimally combined data [47, 48, 112].
  * **Returns**: Denoised BOLD time series (`dnts`), High-Kappa accepted component time series (`hikts`), and Low-Kappa rejected component time series (`lowkts`) [48].

* **Utility I/O Functions**: `add_decomp_prefix`, `fname_to_component_list`, `get_fields`, `load_data_nilearn`, `load_json`, `load_ref_img`, `prep_data_for_json`, `split_ts`, `str_to_component_list`, `write_split_ts`, `writeresults`, `writeresults_echoes` [22, 32, 54, 84, 89, 94, 102, 113, 114].

---

### 9. `tedana.reporting` & `tedana.stats` — Reports & Statistics

#### `tedana.reporting`
* **`html_report.generate_report(io_generator, cluster_labels, similarity_t_sne)`**: Generates interactive HTML report documents summarizing adaptive masks, \\(T_2^*/S_0\\) distributions, decay model fits, component classifications, carpet plots, and t-SNE component clusters [54, 55, 103, 115].
* **`static_figures` Submodule**: Creates standalone PNG diagnostic plots: `pca_results`, `plot_t2star_and_s0`, `plot_rmse`, `plot_adaptive_mask`, `carpet_plot`, `comp_figures`, `plot_gscontrol`, `plot_heatmap` [22, 24, 62, 70, 73, 110, 116, 117].
* **`quality_metrics.calculate_rejected_components_impact`**: Quantifies variance explained by rejected noise components on accepted BOLD components [58, 118].

#### `tedana.stats`
* **`fit_model(x, y, output_residual=False)`**: Executes general linear model (GLM) regression (\\(Y = X\beta + e\\)) returning betas, residual sum of squares (SSE), and degrees of freedom [54, 119, 120].
* **`get_coeffs(data, x, add_const=False)`**: Calculates least-squares coefficient estimates [54, 83].
* **`t_to_z(t_values, dof)`**: Converts \\(t\\)-statistic values into normal \\(Z\\)-scores [7, 113].
* **`voxelwise_univariate_zstats(...)`**: Computes voxel-wise z-statistic maps [84].

---

### 10. `tedana.utils` — General Helper Utilities
* **`make_adaptive_mask(data, tes, ...)`**: Generates an adaptive voxel mask flagging late-echo signal dropout (`dropout`) or non-decaying voxels (`decay`) [26, 32, 38, 99, 107].
* **`load_mask(mask_file)`**: Reads and validates binary input brain masks [94].
* **`check_te_values(te_values)`** & **`check_t2s_values(t2s_map)`**: Validates and converts \\(TE\\) and \\(T_2^*\\) input values to milliseconds [8, 20, 70].
* **`sec2millisec(arr)`** & **`millisec2sec(arr)`**: Converts values between seconds and milliseconds [33, 113, 121].
* **`setup_loggers(...)`** & **`teardown_loggers()`**: Configures console and text file logging streams [7, 113, 122].
* **`get_resource_path()`**, **`get_system_version_info()`**, **`log_newsletter_info()`**: Returns environment paths, system library versions, and package details [57, 100, 106, 123].

---