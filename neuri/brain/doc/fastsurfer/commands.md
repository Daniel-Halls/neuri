The primary entry point for **FastSurfer** is the main wrapper script **`run_fastsurfer.sh`**, which automates both the deep-learning segmentation stream (**FastSurferCNN / FastSurferVINN**) and the surface reconstruction stream (**`recon-surf`**) [1]. 

---

### Command Syntax
```bash
run_fastsurfer.sh --sid <subjectID> --sd <subjects_dir> --t1 <T1_input> [OPTIONS]
```
`run_fastsurfer.sh` processes a T1 full-head image to produce:
1. **Volumetric Segmentation**: A deep-learning-based segmentation using FastSurferVINN (equivalent to FreeSurfer's `aparc.DKTatlas+aseg.mgz`) [1].
2. **Surface Reconstruction**: Surface generation, cortical thickness estimates, and statistics structured as a FreeSurfer subject directory via `recon-surf` [1].

---

### Required & Core Arguments

| Flag | Argument | Description |
| :--- | :--- | :--- |
| **`--sid`** | `<subjectID>` | Subject ID for directory creation inside `$SUBJECTS_DIR` [1]. |
| **`--sd`** | `<subjects_dir>` | Path to the output directory `$SUBJECTS_DIR` (can also be set via environment variable) [1]. |
| **`--t1`** | `<T1_input>` | T1 full-head input image (not bias-corrected). **Requires an absolute path** [1]. |
| **`--fs_license`** | `<license>` | Path to the FreeSurfer license key file (required for surface generation) [1]. |
| **`--asegdkt_segfile`** | `<filename>` | Absolute path/filename for the segmentation file output containing `aparc+DKTatlas-aseg`. Default: `$SUBJECTS_DIR/$sid/mri/aparc.DKTatlas+aseg.deep.mgz` [1]. |
| **`--vox_size`** | `<0.7-1\|min>` | Forces processing at a specified voxel size (between `0.7` and `1.0` mm) or `"min"` (default). If `"min"` is selected, voxel size is derived from the smallest dimension of the input: if > 0.98 mm, conformed to 1 mm isometric; if \\(\le\\) 0.98 mm, conformed to isometric voxels of that size. Controls high-resolution surface processing (<1 mm) [1]. |
| **`--edits`** | *(None)* | Enables manual edit mode by substituting files with `*.manedit.<ext>` (replaces `<asegdkt_segfile>` and `<mask_name>` in segmentation; disables existing run checks in `recon-surf` for edits of `mri/wm.mgz`, `brain.finalsurfs.mgz`, and WM control points) [1]. |
| **`--version`** | `[info]` | Prints version information and exits. Optional `<info>` flags include `+git_branch`, `+git`, `+checkpoints`, and `+pip` for detailed environment status [1]. |
| **`-h` / `--help`** | *(None)* | Prints help documentation and exits [1]. |

---

### Pipeline Control Flags

| Flag | Description |
| :--- | :--- |
| **`--seg_only`** | Runs only the segmentation pipeline (FastSurferVINN) and skips surface reconstruction [2]. |
| **`--surf_only`** | Runs only the surface pipeline (`recon-surf`). The segmentation file must already exist [3]. |

---

### Segmentation Pipeline Options (`FastSurferCNN`)

| Flag | Argument | Description |
| :--- | :--- | :--- |
| **`--seg_log`** | `<seg_log>` | Log file path for the segmentation pipeline (FastSurferVINN, CerebNet, HypVINN). Default: `$SUBJECTS_DIR/$sid/scripts/deep-seg.log` [2]. |
| **`--conformed_name`** | `<conf.mgz>` | Absolute path to save the conformed T1 image. Default: `$SUBJECTS_DIR/$sid/mri/orig.mgz` [2]. |
| **`--no_biasfield`** | *(None)* | Generates a bias-field corrected image and enables calculation of partial volume-corrected stats files [2]. |
| **`--norm_name`** | `<name>` | Path/filename for the bias-field corrected image. Default: `$SUBJECTS_DIR/$sid/mri/orig_nu.mgz` [2]. |
| **`--tal_reg`** | *(None)* | Performs Talairach registration for eTIV estimation in `--seg_only` mode and stats generation [2]. |

---

### Surface Pipeline Options (`recon-surf`)

| Flag | Description |
| :--- | :--- |
| **`--3T`** | Uses the 3T atlas for Talairach registration (yields better eTIV estimates for 3T MRI acquisitions; default is the 1.5T atlas) [3]. |

---

### Resource & Hardware Compute Options

| Flag | Argument | Description |
| :--- | :--- | :--- |
| **`--device`** | `<str>` | Sets compute device for inference (`"cpu"`, `"cuda"`, or specific GPU like `cuda:1`). Default checks GPU availability before CPU [3]. |
| **`--viewagg_device`** | `<str>` | Specifies device for view aggregation (`"auto"`, `"cpu"`, or specific device). `"auto"` evaluates total GPU memory and falls back to CPU if memory is insufficient [3]. |
| **`--threads`** | `<int>` | Sets global OpenMP and ITK thread count (or `"max"`) [3]. |
| **`--threads_seg`** | `<int>` | Thread count specifically allocated for the segmentation pipeline [3]. |
| **`--threads_surf`** | `<int>` | Thread count specifically allocated for surface reconstruction (enables parallel processing of left/right hemispheres when threads \\(\ge\\) 2; default: 1) [3]. |
| **`--batch`** | `<batch_size>` | Batch size for neural network inference (default: 1) [3]. |
| **`--py`** | `<python_cmd>` | Python executable string for both pipelines. Default: `"python3.10 -s"` (where `-s` disables home directory package search) [3]. |

---

### Developer & Experimental Flags

| Flag | Description |
| :--- | :--- |
| **`--ignore_fs_version`** | Bypasses FreeSurfer version compatibility checks [4]. |
| **`--fstess`** | Uses FreeSurfer's `mri_tesselate` for surface creation instead of default marching cubes (`mri_mc`) [4]. |
| **`--fsqsphere`** | Uses FreeSurfer iterative inflation for `qsphere` instead of default spectral spherical projection [4]. |
| **`--fsaparc`** | Additionally generates traditional FreeSurfer `aparc` segmentations and cortical ribbon (skipped by default in favor of deep-learning predictions) [4]. |
| **`--no_fs_T1`** | Skips generation of `T1.mgz` and creates `brainmask.mgz` directly from `norm.mgz` (saves ~1:30 min) [4]. |
| **`--no_surfreg`** | Skips FreeSurfer surface registration for cross-subject correspondence (speeds up execution when only segmentation stats are needed) [4]. |
| **`--allow_root`** | Permits script execution with root user privileges [4]. |

---

### Longitudinal Flags

> *Note: Non-expert users are advised to use `long_fastsurfers.sh` for sequential processing of longitudinal data [5].*

| Flag | Argument | Description |
| :--- | :--- | :--- |
| **`--base`** | *(None)* | Longitudinal template (base) processing. Requires prior preparation via `recon-surf/long_prepare_template.sh`. No T1/T2 passed explicitly [5]. |
| **`--long`** | `<baseid>` | Longitudinal time-point processing relative to base subject `<baseid>` [5]. |

🧠 Would you like me to generate a complete Snakemake rule or shell workflow wrapper for running FastSurfer across multiple subjects?
