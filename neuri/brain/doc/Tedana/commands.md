Here is the complete command-line reference for **Tedana** commands (`tedana`, `t2smap`, `ica_reclassify`) and the AFNI wrapper (`tedana_wrapper.py`), including full syntax, flags, options, and descriptions as documented in your sources.

---

### 1. `tedana` (Canonical Multi-Echo Denoising Workflow)

`tedana` executes multi-echo ICA decomposition, calculates TE-dependence metrics (\\(K\\) and \\(\rho\\)), classifies independent components into BOLD and non-BOLD signal, and outputs denoised BOLD datasets along with summary reports [1-3].

#### Syntax
```bash
tedana [-h] -d FILE [FILE ...] -e TE [TE ...] [--out-dir PATH] 
       [--prefix PREFIX] [--convention {orig,bids}] [--no-reports] 
       [--png-cmap PNG_CMAP] [--verbose] [--overwrite] [--mask FILE] 
       [--masktype {dropout,decay,none} [{dropout,decay,none} ...]] 
       [--dummy-scans INT] [--fittype {loglin,curvefit}] 
       [--combmode {t2s}] [--t2smap FILE] [--tedpca TEDPCA] 
       [--tree TREE] [--external FILE] 
       [--ica-method {robustica,fastica}] [--seed INT] 
       [--n-robust-runs [1-347]] [--maxit INT] [--maxrestart INT] 
       [--mix FILE] [--n-independent-echos INT] [--tedort] 
       [--gscontrol {mir,gsr} [{mir,gsr} ...]] [--lowmem] 
       [--n-threads INT] [--debug] [-v]
```

#### Required Arguments
* **`-d FILE [FILE ...]`**: Multi-echo functional dataset(s) for analysis [1, 3, 307]. Can be provided as a list of echo-specific files in ascending order or a single \\(z\\)-concatenated file [3, 307].
* **`-e TE [TE ...]`**: Ascending echo times associated with the data [3, 307]. Per BIDS convention, values should be supplied in **seconds** (e.g., `0.015 0.039 0.063`), though millisecond values are still accepted with a deprecation warning [3, 307].

#### Output Control & Formatting
* **`--out-dir PATH`**: Directory path for output files (default: current working directory) [3, 307].
* **`--prefix PREFIX`**: Prefix string prepended to output filenames (default: `""`) [3, 307].
* **`--convention {orig,bids}`**: Filenaming convention scheme, where `bids` uses the BIDS derivatives standard (default: `bids`) [3, 307].
* **`--no-reports`**: Suppresses the generation of `.html` reports and `.png` static plots (default: `False`) [335].
* **`--png-cmap PNG_CMAP`**: Name of a Matplotlib colormap used when generating figures (default: `'coolwarm'`) [335].
* **`--verbose`**: Increases terminal log verbosity and saves a detailed TSV log file in the output directory [309, 335].
* **`--overwrite`**: Forces overwriting of pre-existing files in the output directory [335].

#### Masking & Scan Trimming
* **`--mask FILE`**: Path to a binary brain mask spatially aligned with the input data [3]. If omitted, Nilearn's `compute_epi_mask` derives a mask from the first echo [3].
* **`--masktype {dropout,decay,none} [{dropout,decay,none} ...]`**: Method(s) to define the adaptive mask across echoes (default: `['dropout']`) [3].
* **`--dummy-scans INT`**: Number of initial dummy volumes to remove from BOLD data and confounds before processing (default: `0`) [3].

#### Decay Model Fitting & Combination
* **`--fittype {loglin,curvefit}`**: \\(T_2^*/S_0\\) decay model fitting scheme; `loglin` applies a linear fit to log-transformed data, whereas `curvefit` performs monoexponential nonlinear fitting on raw data (default: `loglin`) [3].
* **`--combmode {t2s}`**: Multi-echo optimal combination strategy (`t2s` follows Posse 1999) [335].
* **`--t2smap FILE`**: Path to a precalculated \\(T_2^*\\) map in the same space as the input data (values in seconds) [335].

#### PCA & Component Selection Trees
* **`--tedpca TEDPCA`**: Criterion for selecting components during PCA dimension reduction [3]. Options include information criteria (`aic`, `mdl`, `kic`), Kundu decision trees (`kundu`, `kundu-stabilize`), a float for variance percentage explained (`0.0–1.0`), or an integer specifying a fixed component count (default: `aic`) [3].
* **`--tree TREE`**: Decision tree model used for component classification (`tedana_orig`, `meica`, `minimal`, or a path to a custom JSON specification; default: `tedana_orig`) [3].
* **`--external FILE`**: Path to a TSV file containing external nuisance or task regressors (matching volume count) to incorporate into decision tree evaluation [3].
* **`--mix FILE`**: Precalculated ICA mixing matrix file to bypass PCA/ICA decomposition [309, 335].

#### ICA Configuration
* **`--ica-method {robustica,fastica}`** (or `--ica_method`): ICA algorithm choice [3, 308]. `fastica` runs FastICA once; `robustica` runs FastICA multiple times and clusters components to ensure stability (default: `fastica`) [3, 308].
* **`--seed INT`**: Random seed for FastICA/RobustICA initialization. Set to a positive integer for reproducible results or `-1` for random initialization across calls (default: `42`) [3, 308, 335].
* **`--n-robust-runs [1-347]`**: Iteration count for RobustICA (default: `30`) [309].
* **`--maxit INT`**: Maximum iterations for ICA convergence (default: `500`) [309, 335].
* **`--maxrestart INT`**: Maximum convergence attempt restarts for ICA (default: `10`) [309, 335].
* **`--n-independent-echos INT`**: Number of independent echoes used in goodness-of-fit metrics (\\(F\\)-statistics), primarily for EPTI acquisitions [3, 309].

#### Denoising & Global Signal Options
* **`--tedort`**: Orthogonalizes rejected components with respect to accepted components prior to final time-series denoising (default: `False`) [309, 335].
* **`--gscontrol {mir,gsr} [{mir,gsr} ...]`**: Performs additional global signal control using Minimum Image Regression (`mir`) or Global Signal Regression (`gsr`) [309, 335].

#### Performance & System Options
* **`--lowmem`**: Enables low-memory processing using `IncrementalPCA` (default: `False`) [309, 335].
* **`--n-threads INT`**: Number of CPU threads assigned for parallel computation (default: `1`) [309, 335].
* **`--debug`**: Enables debugging mode with detailed logging [309, 335].
* **`-v, --version`**: Displays program version and exits [307].
* **`-h, --help`**: Displays help documentation and exits [1].

---

### 2. `t2smap` (Optimal Combination & \\(T_2^*/S_0\\) Estimation)

`t2smap` estimates voxelwise \\(T_2^*\\) and \\(S_0\\) maps or time series and produces optimally combined multi-echo BOLD datasets without running ICA denoising [312, 346].

#### Syntax
```bash
t2smap [-h] -d FILE [FILE ...] -e TE [TE ...] [--out-dir PATH] 
       [--prefix PREFIX] [--convention {orig,bids}] [--verbose] 
       [--overwrite] [--mask FILE] 
       [--masktype {dropout,decay,none} [{dropout,decay,none} ...]] 
       [--dummy-scans INT] [--exclude EXCLUDE] 
       [--fittype {loglin,curvefit}] [--fitmode {all,ts}] 
       [--combmode {t2s,paid}] [--n-independent-echos INT] 
       [--n-threads INT] [--debug] [-v]
```

#### Options & Flags
* **`-d FILE [FILE ...]`**: Multi-echo functional dataset files in ascending echo order [312, 346].
* **`-e TE [TE ...]`**: Echo times in seconds (or deprecated milliseconds) [312, 346].
* **`--out-dir PATH`**: Output directory path [312, 346].
* **`--prefix PREFIX`**: Prefix string prepended to output filenames [312, 346].
* **`--convention {orig,bids}`**: Naming convention scheme (`bids` or `orig`; default: `bids`) [312, 346].
* **`--mask FILE`**: Path to a binary brain mask [312, 346].
* **`--masktype {dropout,decay,none} [{dropout,decay,none} ...]`**: Adaptive mask generation method(s) (default: `['dropout']`) [312, 346].
* **`--dummy-scans INT`**: Number of dummy scans to discard from the beginning of datasets [312, 346].
* **`--exclude EXCLUDE`**: Zero-based volume indices (e.g., `'0,5,10'` or ranges like `'0:5'`) to exclude from adaptive mask generation and \\(T_2^*/S_0\\) fitting while retaining them in the combined data [313, 346].
* **`--fittype {loglin,curvefit}`**: \\(T_2^*/S_0\\) model fitting method (`loglin` for log-linear, `curvefit` for nonlinear monoexponential raw data fit; default: `loglin`) [313, 346].
* **`--fitmode {all,ts}`**: Fitting scheme over time; `all` fits per voxel across all timepoints, while `ts` fits per voxel and per timepoint (default: `all`) [313, 346].
* **`--combmode {t2s,paid}`**: Combination weighting algorithm (`t2s` Posse 1999, or `paid` Poser; default: `t2s`) [313, 346].
* **`--n-independent-echos INT`**: Independent echo count for goodness-of-fit metrics [313, 346].
* **`--n-threads INT`**: CPU thread allocation (default: `1`) [313, 346].
* **`--verbose`**: Outputs intermediate maps and files [312, 346].
* **`--overwrite`**: Forces overwriting of pre-existing output files [312, 346].
* **`--debug`**: Enables debug output [313, 346].
* **`-v, --version`**: Displays version information and exits [312].
* **`-h, --help`**: Displays help documentation and exits [312].

---

### 3. `ica_reclassify` (Post-Processing Manual Reclassification)

`ica_reclassify` takes the file registry output from a previous `tedana` run, applies user-specified manual reclassifications or classification tags, and regenerates the final denoised time series and HTML reports [305, 310, 337].

#### Syntax
```bash
ica_reclassify [-h] [--manacc INT [INT ...]] [--manrej INT [INT ...]] 
               [--tagacc TAG [TAG ...]] [--tagrej TAG [TAG ...]] 
               [--config CONFIG] [--out-dir PATH] [--prefix PREFIX] 
               [--convention {orig,bids}] [--no-reports] 
               [--png-cmap PNG_CMAP] [--verbose] [-f] 
               [--dummy-scans INT] [--tedort] 
               [--gscontrol {gsr,mir} [{gsr,mir} ...]] 
               [--n-threads INT] [--debug] [-v] FILE
```

#### Arguments
* **`FILE`**: Mandatory path to the JSON file registry (`desc-tedana_registry.json` or `registry.json`) from a previous `tedana` run [311, 337].
* **`--manacc INT [INT ...]`**: Zero-indexed component indices to accept [311, 337]. Supplied as space/comma-delimited integers, a CSV file, or a text file [311, 337].
* **`--manrej INT [INT ...]`**: Zero-indexed component indices to reject [311, 337]. Supplied as space/comma-delimited integers, a CSV file, or a text file [311, 337].
* **`--tagacc TAG [TAG ...]`**: Custom classification tag(s) to attach to all accepted components [311, 337].
* **`--tagrej TAG [TAG ...]`**: Custom classification tag(s) to attach to all rejected components [337].
* **`--config CONFIG`**: Path to a filename configuration file or `'auto'` [310, 338].
* **`--out-dir PATH`**: Output directory for reclassified outputs [310, 337].
* **`--prefix PREFIX`**: Prefix prepended to output filenames [310, 338].
* **`--convention {orig,bids}`**: Naming convention scheme (`bids` or `orig`; default: `bids`) [310, 338].
* **`--no-reports`**: Disables generation of updated HTML reports and PNG figures [310, 337].
* **`--png-cmap PNG_CMAP`**: Matplotlib colormap for figure generation (default: `'coolwarm'`) [310, 337].
* **`--dummy-scans INT`**: Dummy scan count to discard (default: `0`) [310, 337].
* **`--tedort`**: Orthogonalizes rejected components against accepted ones prior to re-denoising (default: `False`) [310, 337].
* **`--gscontrol {gsr,mir} [{gsr,mir} ...]`**: Performs global signal control (`gsr` or `mir`) [310, 337].
* **`-f, --overwrite`**: Forces overwriting of existing output files [310, 337].
* **`--verbose`**: Increases logging verbosity and writes log files [310, 337].
* **`--n-threads INT`**: CPU thread allocation [310].
* **`--debug`**: Enables debug mode [310, 337].
* **`-v, --version`**: Prints version information and exits [310].
* **`-h, --help`**: Prints help documentation and exits [310].

---

### 4. `tedana_wrapper.py` (AFNI Proc Integration Wrapper)

`tedana_wrapper.py` is AFNI's internal wrapper script that bridges AFNI workflows (such as `afni_proc.py`) to `tedana.py` [21, 22].

#### Syntax
```bash
tedana_wrapper.py -input DSETS [DSETS ...] -TE ms [ms ...] -mask MASK 
                  [-help] [-results_dir DIR] [-prefix PREFIX] [-save_all] 
                  [-prep_only] [-tedana_prog TEDANA_PROG] [-tedana_is_exec] 
                  [-ted_label LABEL] [-tedana_opts 'OPTS']
```

#### Required Arguments
* **`-input DSETS [DSETS ...]`**: 4D NIfTI/AFNI datasets for each echo [22].
* **`-TE ms [ms ...]`**: Echo times in **milliseconds** for each corresponding input echo [22].
* **`-mask MASK`**: Brain mask dataset in the same grid/space as input datasets [22].

#### Tedana Invocation Options
* **`-prep_only`**: Prepares stacked echo data using `3dZcat` and stops before executing `tedana.py` [23].
* **`-tedana_prog TEDANA_PROG`**: Executable path and name of `tedana.py` (default: `meica.libs/tedana.py` within the AFNI binary directory) [23].
* **`-tedana_is_exec`**: Invokes `tedana.py` directly as an executable rather than `python tedana.py` [23].
* **`-ted_label LABEL`**: Folder suffix label (creates an output directory formatted as `TED.LABEL`) [23].
* **`-tedana_opts 'OPTS'`**: Enclosed string of raw command-line options passed directly to `tedana.py` [22, 23]. Example: `-tedana_opts '--initcost=tanh --conv=2.5e-5'` [22].

#### Wrapper Execution & Output
* **`-results_dir DIR`**: Parent directory created for output files (default: `./Bunnymen`) [23].
* **`-prefix PREFIX`**: Dataset prefix string for output filenames (default: `Bunnymen`) [23].
* **`-save_all`**: Saves all intermediate 3D/4D datasets instead of keeping only the `3dZcat` concatenated dataset and standard Tedana outputs [23].
* **`-h, --help`, `-help`**: Displays help documentation and exits [23].

---