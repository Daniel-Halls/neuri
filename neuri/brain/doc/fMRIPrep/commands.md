### Command Syntax & Positional Arguments

The general command-line execution syntax for **fMRIPrep** is [1, 2]:

```bash
fmriprep [-h] [OPTIONS] bids_dir output_dir {participant}
```

* **`bids_dir`**: The root directory of a valid BIDS dataset (containing `sub-XXXXX` subject directories at the top level) [1, 3, 4].
* **`output_dir`**: The destination path where preprocessed derivatives and HTML visual reports will be stored [1, 3, 4].
* **`analysis_level` (`{participant}`)**: The processing stage to run; currently, only `"participant"` is supported per BIDS-Apps specifications [1, 3, 4].

---

### 1. Options for Filtering BIDS Queries
These options control dataset validation and filtering which subjects, sessions, tasks, or echoes are processed [3-5]:

* **`--skip_bids_validation`**, **`--skip-bids-validation`**: Assumes the input dataset is BIDS-compliant and skips BIDS validation (*default: `False`*) [1, 3, 4].
* **`--participant-label`**, **`--participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]`**: Space-delimited list of participant identifiers to process (the `sub-` prefix can be omitted) (*default: `None`*) [1, 3-5].
* **`--session-label SESSION_LABEL [SESSION_LABEL ...]`**: Space-delimited list of session identifiers to process (the `ses-` prefix can be omitted) (*default: `None`*) [1, 3, 5].
* **`-t TASK_ID`**, **`--task-id TASK_ID`**: Selects a specific BIDS task identifier to process (*default: `None`*) [1, 3, 5].
* **`--echo-idx ECHO_IDX`**: Selects a specific echo index to process in a multi-echo sequence (*default: `None`*) [1, 3, 5].
* **`--subject-anatomical-reference {first-lex,unbiased,sessionwise}`**: Method used to build the reference anatomical space (*default: `first-lex`*) [1, 3, 5]:
  * `first-lex`: Uses the first image in lexicographical order.
  * `unbiased`: Constructs an unbiased template from all available anatomical images across sessions.
  * `sessionwise`: Processes each session's anatomical images independently.
* **`--track-sessions`**, **`--no-track-sessions`**: Enable or disable session ID tracking and appending to FreeSurfer subject IDs (*default: `True`*) [1, 3].
* **`--bids-filter-file FILE`**: Path to a JSON file describing custom PyBIDS input filter queries (*default: `None`*) [1, 3].
* **`-d PACKAGE=PATH`**, **`--derivatives PACKAGE=PATH [PACKAGE=PATH ...]`**: Search path(s) for pre-computed derivatives (e.g., `--derivatives smriprep=/path/to/smriprep`) (*default: `None`*) [1, 3].
* **`--bids-database-dir PATH`**: Path to a PyBIDS database folder for faster dataset indexing (*default: `None`*) [1, 3].

---

### 2. Options to Handle Performance
Flags to restrict hardware resource usage, memory allocation, and parallel execution [6, 7]:

* **`--nprocs NPROCS`**, **`--nthreads`**, **`--n_cpus`**, **`--n-cpus`**: Maximum number of threads across all running processes (*default: `None`*) [1, 6, 7].
* **`--omp-nthreads OMP_NTHREADS`**: Maximum number of threads per single process (*default: `None`*) [1, 6, 7].
* **`--mem MEMORY_MB`**, **`--mem_mb`**, **`--mem-mb`**: Upper bound RAM limit for fMRIPrep processes in megabytes (*default: `None`*) [1, 6, 7].
* **`--low-mem`**: Reduces memory footprint at the expense of increased working directory disk usage (*default: `False`*) [1, 6, 7].
* **`--use-plugin FILE`**, **`--nipype-plugin-file FILE`**: Path to a custom Nipype execution plugin configuration file (*default: `None`*) [1, 6, 7].
* **`--sloppy`**: Uses low-quality settings for rapid execution during testing only (*default: `False`*) [1, 6, 7].

---

### 3. Options for Performing Only a Subset of the Workflow
Flags to restrict execution to specific parts of the pipeline [8, 9]:

* **`--anat-only`**: Executes anatomical preprocessing workflows only (*default: `False`*) [1, 8, 9].
* **`--level {minimal,resampling,full}`**: Derivative processing depth (*default: `full`*) [1, 8, 9]:
  * `minimal`: Generates minimal derivatives without resampling.
  * `resampling`: Generates recomputable targets that aid in resampling.
  * `full`: Generates all standard output derivatives.
* **`--boilerplate-only`**, **`--boilerplate_only`**: Generates citation boilerplate text only (*default: `False`*) [1, 8, 9].
* **`--reports-only`**: Regenerates aggregated visual HTML reports without re-executing workflow nodes (*default: `False`*) [1, 8, 9].

---

### 4. Workflow Configuration Options
Core settings controlling functional coregistration, slice timing, output spaces, and distortion corrections [10-12]:

* **`--ignore {fieldmaps,slicetiming,sbref,t2w,flair,fmap-jacobian} [...]`**: Disables specific pipeline components by ignoring corresponding dataset inputs (*default: `[]`*) [1, 10, 11].
* **`--force {bbr,no-bbr,syn-sdc,fmap-jacobian} [...]`**: Forces selected processing steps, overriding automatic heuristics (*default: `[]`*) [1, 10-12]:
  * `[no-]bbr`: Enables or disables Boundary-Based Registration for BOLD-to-T1w coregistration.
  * `syn-sdc`: Forces SyN-SDC distortion estimation in addition to existing fieldmaps.
  * `fmap-jacobian`: Forces Jacobian weighting during fieldmap unwarping.
* **`--output-spaces [OUTPUT_SPACES ...]`**: Spatial reference spaces for resampling (e.g., `MNI152NLin2009cAsym:res-2`, `fsaverage`, `func`) (*default: `None`*) [1, 10-12].
* **`--bold2anat-init {auto,t1w,t2w,header}`**: Method for initial BOLD-to-anatomical alignment (*default: `auto`*) [1, 10].
* **`--bold2anat-dof {6,9,12}`**: Degrees of freedom for BOLD-to-anatomical registration (*default: `6`*) [1, 10].
* **`--slice-time-ref SLICE_TIME_REF`**: Reference time point for slice-timing correction as a fraction of TR (0 = start, 0.5 = midpoint, 1 = end) (*default: `0.5`*) [1, 10].
* **`--dummy-scans DUMMY_SCANS`**: Number of initial nonsteady-state volumes to discard (overrides auto-detection) (*default: `None`*) [1, 10].
* **`--fallback-total-readout-time FALLBACK_TOTAL_READOUT_TIME`**: Fallback Total Readout Time in seconds or `"estimated"` (*default: `None`*) [1, 10].
* **`--random-seed _RANDOM_SEED`**: Seed value for reproducible random number generation (*default: `None`*) [1, 10].
* **`--me-t2s-fit-method {curvefit,loglin}`**: Decay fitting method for multi-echo echo combination (`curvefit` or `loglin`) (*default: `curvefit`*) [1, 10].
* **`--project-goodvoxels`**: Excludes high-variation voxels from surface resampling (*default: `False`*) [1, 10, 13].
* **`--longitudinal`**, **`--force-bbr`**, **`--force-no-bbr`**: *Deprecated flags* replaced by `--subject-anatomical-reference unbiased` and `--force [no-]bbr` [1, 10].

---

### 5. Options for Modulating Outputs
Flags that govern derivative directory layout, surface formats, and report generation [13-16]:

* **`--output-layout {bids,legacy}`**: Directory structure format for outputs (`bids` or legacy `<output-dir>/fmriprep`) (*default: `bids`*) [1, 13-15].
* **`--me-output-echos`**: Saves individual motion/slice/SDC-corrected echo time series to aid post-processing (e.g. Tedana) (*default: `False`*) [1, 14, 15].
* **`--cifti-output [{91k,170k}]`**: Generates BOLD time series in CIFTI grayordinates format (`91k` = 2mm resolution; `170k` = 1.6mm resolution) (*default: `False`*) [1, 14, 16].
* **`--msm`**, **`--no-msm`**: Enables or disables Multimodal Surface Matching surface registration (*default: `True` / `--msm`*) [1, 14, 16].
* **`--medial-surface-nan`**: Fills medial wall vertices with NaNs on surface GIFTI files (*default: `False`*) [1, 14, 15].
* **`--aggregate-session-reports AGGR_SES_REPORTS`**: Maximum number of sessions aggregated into a single visual HTML report before splitting (*default: `4`*) [1, 14, 15].
* **`--md-only-boilerplate`**: Skips Pandoc conversion of generated citation boilerplates (*default: `False`*) [1, 14, 16].

---

### 6. Options Relating to Confounds
Flags controlling confound regressor extraction and motion outlier thresholds [16-18]:

* **`--return-all-components`**: Outputs all principal components from CompCor decompositions rather than truncating at 50% explained variance (*default: `False`*) [1, 16-18].
* **`--fd-spike-threshold REGRESSORS_FD_TH`**: Framewise Displacement threshold in mm for flagging motion outlier frames (*default: `0.5`*) [1, 16-18].
* **`--dvars-spike-threshold REGRESSORS_DVARS_TH`**: Standardized DVARS threshold for flagging motion outlier frames (*default: `1.5`*) [1, 16-18].

---

### 7. ANTs, Fieldmap & Distortion Correction Options
Specific settings for brain extraction, B-spline fieldmap fitting, and SyN-based fieldmap-less SDC [18-20]:

* **`--skull-strip-template SKULL_STRIP_TEMPLATE`**: Target template used for ANTs-based brain extraction [1, 18, 21, 22].
* **`--skull-strip-fixed-seed`**: Uses a fixed random seed for ANTs skull-stripping reproducibility [1, 18, 21, 22].
* **`--skull-strip-t1w {auto,skip,force}`**: Execution mode for T1w skull-stripping (*default: `force`*) [1, 20-22].
* **`--fmap-bspline`**: Fits fieldmaps using least-squares B-Spline regularization (*default: `False`*) [1, 19-21].
* **`--fmap-no-demean`**: Disables demean operations on fieldmap estimations (*default: `True`*) [1, 19-21].
* **`--use-syn-sdc [{warn,error}]`**: Enables experimental anatomical SyN fieldmap-less distortion correction (*default: `False`*) [1, 19-21].
* **`--force-syn`**: *Deprecated flag* replaced by `--force syn-sdc` [1, 19-21].

---

### 8. Specific Options for FreeSurfer Preprocessing
Flags controlling FreeSurfer surface reconstruction workflows [2, 21]:

* **`--fs-license-file FILE`**: Path to a valid FreeSurfer license key file [1, 2, 21].
* **`--fs-subjects-dir PATH`**: Custom directory path for reading or writing FreeSurfer outputs [1, 2, 21].
* **`--submm-recon`**, **`--no-submm-recon`**: Enables or disables submillimeter reconstruction in FreeSurfer `recon-all` [1, 2, 21].
* **`--fs-no-reconall`**: Disables FreeSurfer surface reconstruction entirely [1, 2, 21, 23].
* **`--fs-no-resume`**: Prevents resuming existing longitudinal FreeSurfer templates [1, 2, 21].

---

### 9. Carbon Usage Tracking & Other Utility Options
Infrastructure, logging, tracking, and debugging options [2, 21, 24-26]:

* **`--track-carbon`**: Tracks computational power consumption via CodeCarbon (*default: `False`*) [1, 2, 21, 24].
* **`--country-code COUNTRY_CODE`**: ISO country code for carbon footprint estimations (*default: `CAN`*) [1, 2, 21, 24].
* **`-h`**, **`--help`**: Displays help message and exits [1, 3].
* **`--version`**: Shows fMRIPrep version number and exits [1, 3, 21, 24].
* **`-v`**, **`--verbose`**: Increases logging verbosity (`-vvv` sets debug level) (*default: `0`*) [1, 3, 21, 24].
* **`-w WORK_DIR`**, **`--work-dir WORK_DIR`**: Path to the intermediate working directory [1, 2, 21, 24, 25].
* **`--clean-workdir`**: Empties working directory prior to execution (*default: `False`*) [1, 2, 21, 24, 25].
* **`--resource-monitor`**: Enables Nipype CPU and memory resource profiling (*default: `False`*) [1, 2, 21, 24, 25].
* **`--config-file FILE`**: Loads execution settings from a configuration file [1, 2, 21, 24, 25].
* **`--write-graph`**: Exports computational execution graph diagrams (*default: `False`*) [1, 2, 21, 24, 25].
* **`--stop-on-first-crash`**: Halts execution immediately upon encountering a node failure (*default: `False`*) [1, 2, 21, 24, 26].
* **`--notrack`**: Opts out of sending anonymous run usage telemetry to developers (*default: `False`*) [1, 2, 21, 24, 26, 27].
* **`--debug {compcor,fieldmaps,pdb,all}`**: Enables specific interactive debugging features (*default: `None`*) [1, 2, 21, 24, 26].

---

### 10. Docker Wrapper Interface (`fmriprep-wrapper`)
When using the container wrapper script (`fmriprep-wrapper`), container mounts are handled via additional wrapper flags [28, 29]:

```bash
fmriprep-wrapper [WRAPPER_OPTIONS] bids_dir output_dir participant [FMRIPREP_OPTIONS]
```

* **Named Arguments**:
  * **`-i IMAGE`**, **`--image IMAGE`**: Specifies the Docker image tag to execute [28].
* **Mapped Directory Flags**:
  * Automates host-to-container volume bindings for **`-w`**, **`--output-spaces`**, **`--fs-license-file`**, **`--fs-subjects-dir`**, **`--config-file`**, **`-d` / `--derivatives`**, **`--use-plugin`**, **`--bids-database-dir`**, and **`--bids-filter-file`** [29].
* **Developer & Environment Options**:
  * **`--patch PACKAGE=PATH`**: Patches local Python packages into the container environment [28, 29].
  * **`--shell`**: Opens an interactive shell inside the container instead of running fMRIPrep [28, 29].
  * **`-e ENV_VAR VALUE`**, **`--env`**: Sets custom environment variables in the container [28, 29].
  * **`-u USER`**: Sets the execution user account ID [28].
  * **`--network NETWORK`**: Configures Docker network settings [28].
