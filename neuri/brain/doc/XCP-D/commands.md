**XCP-D (`xcp_d`)** is a postprocessing pipeline for fMRI derivatives (such as fMRIPrep, Nibabies, HCP, DCAN, and UK Biobank) [1, 2]. Below is the detailed breakdown of all command-line flags, options, parameters, and syntax documented in the sources [2].

---

### **1. Command Synopsis**

```bash
xcp_d [-h] --mode {abcd,hbcd,linc,nichart,none} [--version]
      [--participant-label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]]
      [--session-id SESSION_ID [SESSION_ID ...]]
      [-t TASK_ID [TASK_ID ...]] [--bids-filter-file FILE]
      [-d PACKAGE=PATH [PACKAGE=PATH ...]] [--bids-database-dir PATH]
      [--nprocs NPROCS] [--omp-nthreads OMP_NTHREADS]
      [--mem-mb MEMORY_MB] [--low-mem] [--use-plugin USE_PLUGIN] [-v]
      [--input-type {fmriprep,dcan,hcp,nibabies,ukb}]
      [--file-format {auto,cifti,nifti}] [--dummy-scans {auto,INT}]
      [--despike [{y,n}]] [-p CONFOUNDS_CONFIG]
      [--smoothing {auto,FLOAT}] [-m [{y,n}]]
      [--skip {alff,reho,parcellation,connectivity} ...]
      [--motion-filter-type {lp,notch,none}] [--band-stop-min BPM]
      [--band-stop-max BPM] [--motion-filter-order MOTION_FILTER_ORDER]
      [-r HEAD_RADIUS] [-f FD_THRESH] [--min-time MIN_TIME]
      [--output-type {auto,censored,interpolated}]
      [--disable-bandpass-filter] [--lower-bpf HIGH_PASS]
      [--upper-bpf LOW_PASS] [--bpf-order BPF_ORDER]
      [--atlases ATLAS [ATLAS ...] | --skip-parcellation]
      [--min-coverage {auto,FLOAT}]
      [--output-run-wise-correlations [{y,n}]]
      [--create-matrices CORRELATION_LENGTHS [CORRELATION_LENGTHS ...]]
      [--random-seed _RANDOM_SEED] [--linc-qc [{y,n}]]
      [--abcc-qc [{y,n}]]
      [--report-output-level {root,subject,session}]
      [--aggregate-session-reports AGGR_SES_REPORTS]
      [--output-layout {bids,multiverse}] [-w WORK_DIR]
      [--clean-workdir] [--resource-monitor] [--config-file FILE]
      [--write-graph] [--stop-on-first-crash] [--notrack]
      [--debug {pdb,all} ...] [--fs-license-file FILE]
      [--md-only-boilerplate] [--boilerplate-only] [--reports-only]
      [--warp-surfaces-native2std [{y,n}]]
      fmri_dir output_dir {participant}
``` [2]

---

### **2. Positional Arguments**

* **`fmri_dir`**: The root folder containing preprocessed fMRI derivatives (e.g., `/path/to/dset/derivatives/fmriprep`) [3].
* **`output_dir`**: The destination directory for XCP-D outputs [3]. When `--output-layout multiverse` is selected, `xcp_d-<hash>` is appended to the path; when set to `bids`, outputs are placed directly in the specified folder [3].
* **`analysis_level`**: The processing stage/level. Must be explicitly set to **`participant`** [4].

---

### **3. Required & Information Arguments**

* **`-h`, `--help`**: Display program help message and exit [2].
* **`--version`**: Display program version number and exit [2, 4].
* **`--mode {abcd, hbcd, linc, nichart, none}`**: **Required**. Configures predefined parameter presets for specific pipelines or studies [2, 4, 5]. Setting mode to `none` requires manual definition of almost all workflow parameters [5].

---

### **4. Options for Filtering BIDS Queries**

* **`--participant-label`, `--participant_label`**: Space-separated list of subject IDs to process (the `sub-` prefix can be omitted) [2, 4].
* **`--session-id`, `--session_id`**: Space-separated list of session IDs to process (the `ses-` prefix can be omitted) [2].
* **`-t`, `--task-id`, `--task_id`**: Filter datasets by specific task name(s) [2].
* **`--bids-filter-file FILE`**: Path to a JSON file containing PyBIDS filtering criteria (e.g., filtering `session`, `task`, `space`, `resolution`, or `density`) [2, 6, 7].
* **`-d`, `--datasets PACKAGE=PATH`**: Search path(s) for custom derivatives or atlas datasets (e.g., `-d custom=/path/to/custom_confounds` or `-d schaefer=/path/to/schaefer`) [2, 7-9].
* **`--bids-database-dir PATH`**: Path to a pre-indexed PyBIDS database directory to accelerate dataset query speeds [2, 7].

---

### **5. Resource Management Options**

* **`--nprocs`, `--nthreads`, `--n-cpus`, `--n_cpus NPROCS`**: Maximum number of CPU threads across all parallel processes (Default: `2`) [2, 7, 10].
* **`--omp-nthreads`, `--omp_nthreads OMP_NTHREADS`**: Maximum number of threads per process (Default: `1`) [2, 10].
* **`--mem-mb`, `--mem_mb MEMORY_MB`**: Upper limit for memory usage in megabytes [2, 10].
* **`--low-mem`**: Attempt to reduce memory usage at the cost of increased disk I/O in the working directory [2, 10].
* **`--use-plugin`, `--use_plugin`, `--nipype-plugin-file`**: Path to a custom Nipype execution plugin configuration file [2, 10].
* **`-v`, `--verbose`**: Increase verbosity / log debugging messages [2, 10].

---

### **6. Input & Postprocessing Parameters**

* **`--input-type {fmriprep, dcan, hcp, nibabies, ukb}`**: Specifies the input preprocessing pipeline source [2, 11]. Defaults vary by mode (`fmriprep` for `abcd`/`linc`; `nibabies` for `hbcd`) [11].
* **`--file-format {auto, cifti, nifti}`**: Processing format selector [2].
* **`--dummy-scans {auto, INT}`**: Number of initial volumes to discard from each run [2, 12]. Setting to `auto` automatically identifies non-steady-state volumes from preprocessing metadata [12, 13].
* **`--despike [{y, n}]`**: Despikes BOLD data before postprocessing [2, 12, 14].
* **`-p`, `--nuisance-regressors`, `--nuisance_regressors CONFOUNDS_CONFIG`**: Nuisance regression strategy (e.g., built-in strategies like `'36P'`, `'27P'`, `'24P'`, `'6P'` or a path to a custom YAML confound configuration) [2, 8, 15, 16].
* **`--smoothing {auto, FLOAT}`**: Gaussian kernel Full-Width at Half-Maximum (FWHM) in millimeters for smoothing denoised data [2, 15]. Set to `0` to disable [15].
* **`--skip {alff, reho, parcellation, connectivity} ...`**: Selectively skips specific postprocessing steps [2, 17, 18]:
  * `alff`: Skip ALFF calculations [17, 18].
  * `reho`: Skip Regional Homogeneity calculations [17, 18].
  * `parcellation`: Skip parcellation & time-series extraction (also automatically skips connectivity) [17, 18].
  * `connectivity`: Skip functional connectivity matrix calculations while preserving time-series extraction [17, 18].

---

### **7. Motion Parameter Filtering & Scrubbing**

* **`--motion-filter-type {lp, notch, none}`**: Filter type for removing respiratory artifacts from motion parameters [2, 19-23].
* **`--band-stop-min BPM`**: Lower frequency bound for motion filter in breaths-per-minute (bpm) [2, 19, 20, 23, 24].
* **`--band-stop-max BPM`**: Upper frequency bound for motion filter in bpm (Required if `--motion-filter-type` is `notch`) [2, 19, 20, 23, 25].
* **`--motion-filter-order INT`**: Filter order/coefficients for motion parameter filter [2, 19, 20, 25].
* **`-r`, `--head-radius HEAD_RADIUS`**: Head radius (mm) used for calculating Framewise Displacement (FD) [2, 26].
* **`-f`, `--fd-thresh FD_THRESH`**: FD threshold (mm) for identifying high-motion outlier volumes [2, 16, 27-29].
* **`--min-time MIN_TIME`**: Minimum duration (in seconds) of low-motion BOLD data required per run (Default: `240` s / 4 min) [2, 30].
* **`--output-type {auto, censored, interpolated}`**: Controls output BOLD time series representation [2, 30].

---

### **8. Data / Bandpass Filtering Parameters**

* **`--disable-bandpass-filter`, `--disable_bandpass_filter`**: Disables bandpass filtering on BOLD data (automatically disables ALFF derivative calculation) [2, 30, 31].
* **`--lower-bpf HIGH_PASS`**: High-pass cutoff frequency in Hz for Butterworth filter (Default: `0.01` Hz) [2, 31].
* **`--upper-bpf LOW_PASS`**: Low-pass cutoff frequency in Hz for Butterworth filter (Default: `0.08` Hz) [2, 31].
* **`--bpf-order BPF_ORDER`**: Butterworth bandpass filter order (Default: `2`) [2, 32].

---

### **9. Parcellation & Mode Options**

* **`--atlases ATLAS [ATLAS ...]`**: List of parcellation atlases to apply [2, 9, 32]. Default includes built-in atlases (e.g., `4S1056Parcels` through `4S956Parcels`, `Glasser`, `Gordon`, `HCP`, `MIDB`, `MyersLabonte`, `Tian`) [32].
* **`--skip-parcellation`**: Deprecated flag; replaced by `--skip parcellation` [2, 17, 32-34].
* **`--min-coverage {auto, FLOAT}`**: Minimum spatial coverage threshold (0 to 1) for parcels; parcels below threshold are set to NaN (Default: `auto` / `0.5`) [2, 26-28, 34].
* **`--output-run-wise-correlations [{y,n}]`**: Output correlation matrices for individual runs [2, 34, 35].
* **`--create-matrices CORRELATION_LENGTHS [CORRELATION_LENGTHS ...]`**: Generate correlation matrices for specified data durations (in seconds or `all`) from concatenated runs (requires `--combine-runs`; not supported in `linc` mode) [2, 19, 20, 36-39].
* **`--random-seed _RANDOM_SEED`**: Seed value for frame sampling during `--create-matrices` [2, 39].
* **`--linc-qc [{y,n}]`**: Calculate LINC quality control metrics [2, 26-28, 39].
* **`--abcc-qc [{y,n}]`**: Produce ABCC/DCAN style executive summary and QC files [2, 39, 40].

---

### **10. Reporting, Workdir, & Debugging Options**

* **`--report-output-level {root, subject, session}`**: Output hierarchy for visual HTML reports [2, 41].
* **`--aggregate-session-reports AGGR_SES_REPORTS`**: Option for aggregating multi-session reports [2].
* **`--output-layout {bids, multiverse}`**: Structure layout of generated derivatives [2, 3].
* **`-w`, `--work-dir WORK_DIR`**: Path to Nipype intermediate working directory (Default: `working_dir`) [2, 42].
* **`--clean-workdir`**: Clears working directory contents upon run completion [2, 42].
* **`--resource-monitor`**: Enables Nipype resource logging (CPU and RAM tracking) [2, 42].
* **`--config-file FILE`**: Path to a pre-generated configuration file [2, 42].
* **`--write-graph`**: Writes the execution workflow graph [2, 42].
* **`--stop-on-first-crash`**: Forces early termination if any workflow node crashes [2, 42].
* **`--notrack`**: Disables telemetry/tracking [2].
* **`--debug {pdb, all}`**: Enables debug modes [2].
* **`--fs-license-file FILE`**: Path to FreeSurfer license file [2].
* **`--md-only-boilerplate`**: Generates methods boilerplate in Markdown format only [2].
* **`--boilerplate-only`**: Generates methods boilerplate text and exits [2].
* **`--reports-only`**: Re-generates visual reports without re-running data processing [2].
* **`--warp-surfaces-native2std [{y,n}]`**: Warps native anatomical surfaces to standard space (`fsLR-32k`; requires CIFTI file format) [2, 27, 28, 40, 43].

---