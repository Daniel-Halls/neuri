The command-line interface for **QSIPrep (`qsiprep`)** takes a valid BIDS-formatted dataset as input and builds a dynamic, subject-specific diffusion MRI preprocessing workflow [1, 2]. Below is a comprehensive list of all command-line positional arguments, BIDS app options, DWI preprocessing parameters, and execution flags as documented in the sources [3].

---

### **1. Core Syntax & Positional Arguments**

The basic command-line usage structure is:
`qsiprep bids_dir output_dir participant [options]` [3]

* **`bids_dir`**: The root directory of a valid, BIDS-compliant dataset containing at least one diffusion MRI series [1, 4].
* **`output_dir`**: The root directory where outcomes of preprocessing (derivatives) and visual HTML reports will be saved [4-6].
* **`analysis_level`**: The processing stage to be executed [4]. Currently, the only supported choice is **`participant`** [4].

---

### **2. BIDS Filtering & Querying Options**

These options control which subjects, sessions, or specific scans from the BIDS dataset are selected for processing [7, 8]:

| Flag / Parameter | Description |
| :--- | :--- |
| **`--skip-bids-validation`** | Assumes the input dataset is BIDS-compliant and skips validator checks [4]. |
| **`--participant-label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]`** | Space-delimited list of participant identifiers to process (the `sub-` prefix can be omitted) [4]. |
| **`--session-id SESSION_ID [SESSION_ID ...]`** | Space-delimited list of session identifiers to process (the `ses-` prefix can be omitted) [3]. |
| **`--bids-filter-file FILE`** | Path to a JSON file defining custom PyBIDS filters to select specific modalities, runs, or acquisitions [7, 8]. |
| **`--bids-database-dir PATH`** | Path to a cached PyBIDS SQLite database folder for faster indexing of large datasets [7]. |

---

### **3. Performance & Computational Resource Options**

Options for managing parallelization, system memory, and execution plugins [7]:

* **`--nprocs` / `--nthreads` / `--n-cpus`**: Sets the maximum number of CPU threads across all processes [7].
* **`--omp-nthreads`**: Sets the maximum number of threads per individual process [7].
* **`--mem` / `--mem-mb`**: Defines the upper bound memory limit (in MB) for QSIPrep processes [7].
* **`--low-mem`**: Reduces memory footprint during execution by utilizing uncompressed NIfTIs and disk caching [7, 9].
* **`--use-plugin` / `--nipype-plugin-file`**: Path to a custom Nipype execution plugin configuration file [7].
* **`--sloppy`**: Runs workflows in low-quality mode for fast testing and debugging only [7, 10].

---

### **4. Workflow Scope Selection**

Flags to restrict processing to specific sub-components or generate boilerplate documentation [7, 11]:

* **`--anat-only`**: Executes only the anatomical reference processing workflows and exits [7, 11].
* **`--dwi-only`**: Ignores anatomical (T1w/T2w) data and processes diffusion images only (registers \\(b=0\\) to an AC-PC aligned template) [7, 11-15]. *(Note: Equivalent to `--anat-modality none` [15, 16]).*
* **`--boilerplate-only` / `--boilerplate`**: Generates only the HTML/Markdown citation boilerplate text and exits [3, 7, 9, 11].
* **`--reports-only`**: Reruns report aggregation based on existing cached working directories without running processing workflows [3, 10, 11].

---

### **5. Anatomical Reference & Template Processing Options**

Options that govern skull-stripping, longitudinal template building, anatomical contrast, and spatial normalization [3, 11, 15, 17, 18]:

* **`--anat-modality {T1w, T2w, none}`**: Specifies the anatomical reference contrast (default: `T1w`) [17]. If `--infant` is set, `T2w` is forced [17]; if `none`, anatomical workflows are bypassed [15, 16].
* **`--subject-anatomical-reference {first-lex, unbiased, sessionwise}`**: Defines how subject-specific anatomical reference space is constructed across multiple sessions/scans (`first-lex` uses lexicographical order, `unbiased` constructs a robust template) [11, 19-21].
* **`--skip-anat-based-spatial-normalization`**: Disables non-linear spatial normalization of the anatomical image to MNI template space, saving computation time [12, 17].
* **`--anatomical-template {MNI152NLin2009cAsym}`**: Specifies the standard spatial template for normalization [3, 22].
* **`--infant`**: Configures pipelines for infant brains and automatically sets the anatomical template to `MNIInfant` [11, 23, 24].
* **`--longitudinal`**: Enables longitudinal processing for multiple time-points [11, 23].
* **`--b0-to-t1w-transform {Rigid, Affine}`**: Transformation model used when coregistering \\(b=0\\) reference images to anatomical reference images (default: `Rigid`) [3, 22, 25].
* **`--intramodal-template-iters INTRAMODAL_TEMPLATE_ITERS`**: Number of iterations for building an intramodal \\(b=0\\) template across scan groups [3, 25].
* **`--intramodal-template-transform {Rigid, Affine, BSplineSyN, SyN}`**: Transformation model used for intramodal template creation (default: `BSplineSyN`) [3, 25].
* **`--fs-license-file PATH`**: Absolute path to a valid FreeSurfer `license.txt` file (required when FreeSurfer tools like SynthStrip or SynthSeg are invoked) [15, 25, 26].

---

### **6. DWI Preprocessing, Denoising & Resampling Parameters**

Parameters controlling image noise reduction, artifact correction, intensity normalization, and output grid resampling [12, 17, 27-30]:

* **`--output-resolution OUTPUT_RESOLUTION`** *(REQUIRED)*: Sets the isotropic voxel size (in mm) for preprocessed output DWI series [3, 12, 31]. Single-shot interpolation (Lanczos-windowed Sinc or BSpline for \\(>10\%\\) upsampling) is performed to this spatial resolution [12-14].
* **`--b0-threshold B0_THRESHOLD`**: Any b-value in `.bval` files below this number is treated as a \\(b=0\\) volume (default: `100`) [17, 22].
* **`--denoise-method {dwidenoise, patch2self, none}`**: Selects the image-based noise reduction algorithm: MRtrix3 MP-PCA (`dwidenoise`), DIPY (`patch2self`), or disables denoising (`none`) (default: `dwidenoise`) [16, 17, 27, 29].
* **`--dwi-denoise-window DWI_DENOISE_WINDOW`**: Window size (in voxels) for image denoising (`auto` or an odd positive integer) [16, 17].
* **`--unringing-method {none, mrdegibbs, rpg}`**: Gibbs-ringing removal algorithm: `none`, MRtrix3 (`mrdegibbs`), or TORTOISE (`rpg`) (default: `none`) [17, 19, 27, 29].
* **`--b1-biascorrect-stage {final, none, legacy}`**: Sets the pipeline stage for \\(B_1\\) bias field correction (`final` applies correction after resampling, `none` skips it, `legacy` applies it before concatenation) [17, 22, 30].
* **`--dwi-no-biascorr`**: *DEPRECATED flag*; use `--b1-biascorrect-stage none` instead [16, 17, 30].
* **`--no-b0-harmonization`**: Disables scaling/harmonization of \\(b=0\\) image intensities across different DWI series [1, 28, 30].
* **`--denoise-after-combining`**: Runs denoising steps *after* concatenating multiple DWI series instead of individually on each series before concatenation [1, 16, 28, 32].
* **`--separate-all-dwis`**: Prevents merging/concatenation of multiple DWI series; each scan is preprocessed independently [12, 19, 28].
* **`--distortion-group-merge {concat, average, none}`**: Method for combining preprocessed images across distortion groups (`concat` appends 4D volumes, `average` averages opposing PE directions HCP-style, `none` keeps groups separate) [16, 28, 32, 33].

---

### **7. Head Motion Correction (HMC) & Susceptibility Distortion Correction (SDC)**

Options specifying head motion estimation models, FSL Eddy configuration, and fieldmap unwarping [3, 25, 34-37]:

* **`--hmc-model {none, 3dSHORE, eddy, tensor}`**: Model used to generate target reference volumes for head motion correction (`eddy` for FSL Eddy, `3dSHORE` or `tensor` for SHORELine on non-shelled/Cartesian data, `none` to copy transforms from nearest \\(b=0\\)) [3, 25, 34, 38].
* **`--hmc-transform {Affine, Rigid}`**: Transformation model optimized during motion estimation (default: `Affine`) [3, 25].
* **`--b0-motion-corr-to {iterative, first}`**: Initial \\(b=0\\) volume alignment target for SHORELine motion correction [3, 22, 25].
* **`--shoreline-iters SHORELINE_ITERS`**: Number of iterations for SHORELine motion correction (default: `2`) [3, 19, 37].
* **`--eddy-config EDDY_CONFIG`**: Path to a custom JSON file containing command-line parameter settings for `eddy` [3, 16, 25, 34].
* **`--pepolar-method {TOPUP, DRBUDDI, TOPUP+DRBUDDI}`**: Distortion correction method for reverse phase-encoding (PEPOLAR/blip-up/blip-down) fieldmaps (default: `TOPUP`) [3, 35, 37].
* **`--fmap-bspline`**: Regularizes fieldmaps using a B-Spline basis field [3, 16, 37].
* **`--fmap-no-demean`**: Disables median subtraction from fieldmap estimations [3, 16, 37].
* **`--use-syn-sdc [{warn, error}]`**: Enables experimental ANTs SyN-based fieldmap-less distortion correction when no fieldmaps are available [3, 19, 36, 37].
* **`--force-syn`**: Forces SyN distortion correction even if explicit fieldmaps are present [3, 23].
* **`--ignore {fieldmaps, t2w, phase} [{fieldmaps, t2w, phase} ...]`**: Ignores specified input modalities or fieldmaps during processing [3, 11, 26].

---

### **8. Infrastructure, Logging & Debugging Flags**

General execution controls, crash handling, and logging verbosity [3, 23]:

* **`-v` / `--verbose`**: Increases terminal logging verbosity (e.g., `-vvv` for detailed Nipype node debug logs) [3, 23, 39].
* **`-w WORK_DIR` / `--work-dir WORK_DIR`**: Directory path where intermediate workflow execution scratch files are written [3, 22, 23, 39].
* **`--config-file FILE`**: Path to a pre-generated TOML configuration file to override command-line defaults [3, 23, 40].
* **`--resource-monitor`**: Enables real-time CPU and RAM resource monitoring logs [3, 19, 23].
* **`--write-graph`**: Exports execution workflow graphs (DOT/SVG diagrams) [3, 22, 23].
* **`--stop-on-first-crash`**: Forces execution to halt immediately upon the first node failure [3, 19, 23].
* **`--notrack`**: Opts out of sending anonymous run telemetry metrics to developers [3, 10, 23, 41].
* **`--debug {fieldmaps, pdb, all}`**: Enables interactive Python debugging (`pdb`) or specific workflow debugging modes [3, 9, 23].
* **`--version`**: Prints QSIPrep version string and exits [3, 23].

---

🧠 **Next Step**: Would you like to generate a sample configuration file (such as a custom `eddy_config.json` or BIDS filter JSON) to set up a specific dataset pipeline?
