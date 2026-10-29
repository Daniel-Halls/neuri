# QSIRecon (`qsirecon`) Command-Line Reference & Specification Guide

**QSIRecon** is a BIDS-App designed for postprocessing and diffusion MRI (dMRI) reconstruction workflows [1-3]. It accepts preprocessed diffusion data (from QSIPrep or other minimal pipelines) and executes curated or custom reconstruction pipelines [2, 4, 5].

---

## 1. Syntax & Core Command Structure

```bash
qsirecon [-h] [--participant-label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]]
         [--session-id SESSION_ID [SESSION_ID ...]]
         [-d PACKAGE=PATH [PACKAGE=PATH ...]] [--bids-filter-file FILE]
         [--bids-database-dir PATH] [--nprocs NPROCS]
         [--omp-nthreads OMP_NTHREADS] [--mem MEMORY_MB] [--low-mem]
         [--use-plugin FILE] [--sloppy] [--boilerplate-only] [--reports-only]
         [--report-output-level {root,subject,session}] [--infant]
         [--b0-threshold B0_THRESHOLD] [--output-resolution OUTPUT_RESOLUTION]
         [--fs-license-file PATH] --recon-spec RECON_SPEC
         [--input-type {qsiprep,ukb,hcpya}] [--fs-subjects-dir PATH]
         [--skip-odf-reports] [--recon-spec-aux-files RECON_SPEC_AUX_FILES]
         [--atlases ATLAS [ATLAS ...]] [--version] [-v] [-w WORK_DIR]
         [--resource-monitor] [--config-file FILE] [--write-graph]
         [--stop-on-first-crash] [--notrack] [--debug {pdb,all} [{pdb,all} ...]]
         input_dir output_dir {participant}
```
*(Source: [1])*

### Container Call Example (Apptainer / Singularity)
```bash
apptainer run \
    --containall \
    --writable-tmpfs \
    -B "${PWD}" \
    qsirecon-latest.sif \
    "${PWD}/inputs/qsiprep" \
    "${PWD}/results/qsirecon" \
    participant \
    -w "${PWD}/work" \
    --nthreads 8 \
    --omp-nthreads 8 \
    --recon-spec dsi_studio_autotrack \
    -v -v
```
*(Source: [6, 7])*

---

## 2. Positional Arguments

* **`input_dir`**: Root directory of the input dataset containing subject-level folders [1, 8]. If the dataset is not BIDS-valid, a BIDS-compliant layout is generated based on `--input-type` [8].
* **`output_dir`**: Output path where postprocessed derivatives, parcellations, and visual HTML reports are stored [1, 8].
* **`analysis_level`**: Processing stage to execute (currently only `participant` is supported) [1, 8].

---

## 3. Command-Line Flags & Options

### A. Options for Filtering Input Data
* **`--participant-label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]`**: Space-delimited list of participant identifiers to process (the `sub-` prefix can be omitted) [1, 8].
* **`--session-id SESSION_ID [SESSION_ID ...]`**: Space-delimited list of session identifiers to filter for multi-session datasets [1].
* **`-d PACKAGE=PATH, --dataset PACKAGE=PATH`**: Key-value pairs used to link external dataset paths [1].
* **`--bids-filter-file FILE`**: Path to a JSON file containing BIDS selection filters for input queries [1].
* **`--bids-database-dir PATH`**: Path to a directory containing pre-built SQLite database indices for the BIDS dataset [1].

---

### B. Reconstruction Workflow & Spec Options
* **`--recon-spec RECON_SPEC`** (**REQUIRED**): Specifies the reconstruction pipeline to execute [1, 5, 9]. Can be a built-in workflow identifier (e.g., `dsi_studio_autotrack`, `amico_noddi`) or the path to a custom YAML specification file [5, 10].
* **`--input-type {qsiprep, ukb, hcpya}`**: Specifies the pipeline used to create the input data [1, 5]:
  * **`qsiprep`** *(default)*: Preprocessed data from QSIPrep [5].
  * **`ukb`**: UK Biobank minimal preprocessing pipeline [5].
  * **`hcpya`**: Human Connectome Project (HCP) Young Adult pipeline [5].
* **`--fs-subjects-dir PATH`**: Directory containing pre-computed FreeSurfer output directories to integrate into structural/surface-based reconstruction workflows [1, 5].
* **`--skip-odf-reports`**: Skips rendering of Orientation Distribution Function (ODF/FOD) visual reportlets [1, 11].
* **`--recon-spec-aux-files RECON_SPEC_AUX_FILES`**: Directory containing auxiliary files for the reconstruction pipeline (e.g., group-averaged response functions) [1, 11].

---

### C. Parcellation & Atlas Options
* **`--atlases ATLAS [ATLAS ...]`**: Space-delimited list of brain atlases to transform and apply for connectome/scalar extraction [1, 11].
  * **Built-in Atlases**: `AAL116`, `AICHA384Ext`, `Brainnetome246Ext`, `Gordon333Ext`, and the `4S` atlas series [11, 12].

---

### D. Workflow Configuration Options
* **`--infant`**: Configures anatomical spatial normalization and templates for infant brains (e.g., MNIInfant cohorts) [1, 5, 13].
* **`--b0-threshold B0_THRESHOLD`**: Any `.bval` value below this threshold is treated as a \\(b=0\,\mathrm{s/mm}^2\\) volume (default: `100`) [1, 5].
* **`--output-resolution OUTPUT_RESOLUTION`**: Isotropic voxel size in millimeters for spatial resampling after reconstruction [1, 5].
* **`--fs-license-file PATH`**: Path to the FreeSurfer license file [1, 5, 6]. If omitted, QSIRecon checks the `$FS_LICENSE` or `$FREESURFER_HOME/license.txt` paths [5].

---

### E. Performance, Resource, & Execution Options
* **`--nprocs NPROCS`, `--nthreads NTHREADS`**: Maximum number of compute tasks/processes allowed to run simultaneously [1, 7].
* **`--omp-nthreads OMP_NTHREADS`**: Maximum number of OpenMP multithreading threads per process [1, 7].
* **`--mem MEMORY_MB`, `--memory-mb MEMORY_MB`**: Memory cap in megabytes [1].
* **`--low-mem`**: Minimizes memory usage during execution [1].
* **`--use-plugin FILE`**: Specifies a custom Nipype plugin configuration file for distributed or cluster execution [1].
* **`--sloppy`**: Runs workflows in fast, suboptimal testing mode to verify pipeline execution [1].
* **`--boilerplate-only`**: Generates only the HTML/Markdown citation boilerplate text and exits [1].
* **`--reports-only`**: Re-aggregates HTML visual reports from cached working directories without re-running compute nodes [1].
* **`--report-output-level {root, subject, session}`**: Output location for HTML reports (default: `'root'`) [1, 5].

---

### F. Debugging & Infrastructure Flags
* **`--version`**: Prints QSIRecon version information and exits [1, 11].
* **`-v, --verbose`**: Increases log verbosity (up to `-vvv` for detailed debug logging) [1, 6, 7, 13].
* **`-w WORK_DIR, --work-dir WORK_DIR`**: Directory path for storing intermediate workflow scratch files [1, 6, 7, 13].
* **`--resource-monitor`**: Enables Nipype's execution profiler to log CPU and RAM utilization over time [1, 13].
* **`--config-file FILE`**: Path to a TOML configuration file containing execution settings [1, 13].
* **`--write-graph`**: Exports execution workflow graphs (DOT/SVG formats) [1, 13].
* **`--stop-on-first-crash`**: Forces the pipeline to halt immediately upon encountering a node failure [1, 13].
* **`--notrack`**: Opts out of sending anonymous telemetry to QSIRecon developers [1, 13].
* **`--debug {pdb, all}`**: Enables interactive debugging modes [1, 14].

---

## 4. Reconstruction Workflow Specs (`recon-spec`)

### Built-In Reconstruction Workflows
QSIRecon ships with pre-configured pipelines for multi-shell, Cartesian, and single-shell diffusion acquisitions [2, 10]:

| Workflow Name | Software Framework | Compatible Schemes |
| :--- | :--- | :--- |
| **`amico_noddi`** | AMICO / DIPY | Multi-Shell [10] |
| **`dipy_mapmri`** | DIPY | Multi-Shell, Cartesian [12] |
| **`dsi_studio_autotrack`** | DSI Studio | Multi-Shell, Cartesian, Single-Shell [7, 12] |
| **`dsi_studio_gqi`** | DSI Studio | Multi-Shell, Cartesian, Single-Shell [12] |
| **`mrtrix_multishell_msmt_ACT-hsvs`** | MRtrix3 | Multi-Shell [12] |
| **`mrtrix_singleshell_ss3t_ACT-hsvs`** | MRtrix3 | Single-Shell [12] |
| **`pyafq_tractometry`** | PyAFQ | Multi-Shell, Single-Shell [1, 6, 12] |
| **`ss3t_fod_autotrack`** | MRtrix3 / DSI Studio | Multi-Shell, Single-Shell [12] |
| **`TORTOISE`** | TORTOISE | Multi-Shell [12] |

---

### Custom Reconstruction Specs (YAML Architecture)
Custom reconstruction specs are defined using **YAML** configuration files [15]. Each spec consists of three main structural components:

```yaml
name: custom_recon_pipeline
anatomical:
  - mrtrix_5tt_hsvs

nodes:
  - action: csd
    name: msmt_csd
    software: MRTrix3
    qsirecon_suffix: MRtrix3_act-FAST
    parameters:
      response:
        algorithm: dhollander
      fod:
        algorithm: msmt_csd
        max_sh: [16]
      mtnormalize: true

  - action: fit_noddi
    name: fit_noddi
    software: AMICO
    qsirecon_suffix: NODDI

  - action: template_map
    name: template_map
    software: qsirecon
    input: qsirecon
    scalars_from:
      - fit_noddi
    parameters:
      interpolation: NearestNeighbor
```
*(Source: [15, 17-20])*

#### Structural Components:
1. **`name`**: Unique string naming the overall pipeline (defines the workspace subdirectory) [15].
2. **`anatomical`**: Specifies anatomical preprocessing actions run on T1w/T2w images prior to dMRI model fitting (e.g., `mrtrix_5tt_hsvs` for Hybrid Surface-Volume Segmentation) [15].
3. **`nodes`**: Ordered list of processing units [15, 17, 18]. Each node contains:
   * **`action`**: The underlying processing task (e.g., `csd`, `fit_noddi`, `DKI_reconstruction`, `template_map`) [17-19].
   * **`software`**: Target software engine (`MRTrix3`, `Dipy`, `AMICO`, `DSIStudio`, `TORTOISE`, `PyAFQ`, `qsirecon`) [17-19].
   * **`name`**: Unique node identifier used for internal data piping [17, 18, 20].
   * **`qsirecon_suffix`**: BIDS derivative suffix appended to generated output files [17-19].
   * **`input`**: Links outputs from an upstream node as inputs to the current node [18, 20].
   * **`scalars_from`**: Lists scalar-generating nodes whose outputs should be transformed to template/standard space via a `template_map` action [19].

---

Would you like to explore specific reconstruction specs in more detail, or set up a custom YAML pipeline for your dataset?
