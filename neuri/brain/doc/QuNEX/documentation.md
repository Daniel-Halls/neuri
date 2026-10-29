### 1. What QuNex Does
The **Quantitative Neuroimaging Environment & Toolbox (QuNex)** is an integrated, containerized software platform for data organization, preprocessing, quality assurance/control, and analytics across diverse neuroimaging modalities [1-3]. 

* **Pipeline Integrations**: QuNex natively incorporates the **Human Connectome Project (HCP) Minimal Preprocessing Pipelines** and integrates tools such as FSL, FreeSurfer, Connectome Workbench, and PALM, while offering native XNAT integration for web-based data management [1, 2, 4].
* **Scale and Modalities**: It is built to handle processing ranging from single subjects to large-scale datasets with tens of thousands of scans (such as the HCP Lifespan/Aging datasets and UK Biobank) [1, 5]. Supported data types include structural MRI, resting-state and task fMRI, diffusion MRI (dMRI), as well as non-human primate (NHP) and rodent (mice) neuroimaging data [5-7].
* **Core Philosophy**: QuNex relies on a Command-Line Interface (CLI) to prioritize auditability, exact parameter documentation, batch parallelization, and scientific reproducibility [8-10].

---

### 2. Pipeline Onboarding and Execution

#### Data Onboarding
Raw data from various acquisition formats are mapped into the standardized QuNex study structure using dedicated commands:
* **DICOM**: `import_dicom` (and `bruker_to_dicom` for Bruker formats) extracts raw DICOM or PAR/REC packages, de-identifies files, converts them to NIfTI, and generates initial acquisition metadata (`session.txt`) [11-13].
* **BIDS**: `import_bids` imports Brain Imaging Data Structure compliant datasets and maps them into the QuNex layout (`import_bids` running `map_bids2nii`) [14-16].
* **HCP Data**: `import_hcp` onboards HCP-formatted datasets (`HCA`, `HCD`, `HCYA`) [17-19].

#### Pipeline Execution Workflows
Processing can be executed step-by-step via CLI calls or automatically chained:
* **Command-Line Interface (CLI)**: Functions are invoked using the `qunex` command or through the container wrapper `qunex_container` [20-23].
* **QuNex Recipes Framework (`run_recipe`)**: Workflows can be declared using human-readable YAML files called recipes [24-26]. A single recipe file specifies global parameters and an ordered sequence of processing, quality control, analysis steps, and optional external scripts [2, 27, 28].
* **Containerization**: QuNex is distributed as a self-contained environment using Docker or Singularity/Apptainer images [29-31].
* **Parallel Execution & HPC Scheduling**: QuNex supports parallel processing across sessions (`--parsessions`) and parallel processing of elements within a session (`--parelements`, e.g., running multiple BOLD runs concurrently) [32-34]. Native integration is provided for cluster schedulers including **SLURM**, **PBS**, and **GridEngine** [35-37].

---

### 3. HCPStyleData vs. LegacyStyleData Modes

QuNex supports two primary processing modes configured via the `--hcp_processing_mode` parameter:

* **`HCPStyleData`**:
  * The default mode, applied when datasets strictly adhere to HCP acquisition guidelines [38, 39].
  * **Requirements**: High-resolution isotropic T1w and T2w structural images, spin-echo or gradient-echo field maps for BOLD/DWI distortion correction, and multi-band fMRI acquisitions [38-40].
* **`LegacyStyleData`**:
  * An extended processing mode designed for legacy, clinical, or non-HCP standard datasets [38, 40, 41].
  * **Functionality**: Relaxes HCP constraints to allow processing datasets that lack T2-weighted structural scans, lack field maps/distortion correction, use single-band BOLD fMRI, require slice-timing correction, use custom movement reference images, or require BOLD brain masking derived from dilated fMRI FOVs or BOLD scout images [38, 41, 42].

---

### 4. Outputs Generated & Logging Hierarchy

#### Processing & Analysis Outputs
* **Preprocessed Neuroimaging Data**: Resampled volume NIfTI files, CIFTI grayordinates surface/subcortical dense time series (`.dtseries.nii`), and FreeSurfer cortical surface reconstructions stored in `MNINonLinear/Results` and mapped to `images/` directories (`images/functional`, `images/structural`, `images/segmentation`) [43-45].
* **Downstream Analytics**: Parcellated CIFTI files (`.ptseries.nii`), seed-based and Global Brain Connectivity (GBC) maps, task GLM statistics, and diffusion microstructure metrics (DTIFit, NODDI, Probtrackx) [46-49].

#### Quality Control (QC) & Quality Assurance (QA)
* **Visual QC (`run_qc`)**: Generates visual inspection packages across modalities (`rawNII`, `T1w`, `T2w`, `myelin`, `BOLD`, `DWI`), producing Connectome Workbench `.scene` files, rendered `.png` snapshots, and zipped `.QC.wb.zip` scene bundles [50-52]. For raw NIfTI files, it produces FSL `slicesdir` HTML reports [53-55].
* **Quality Assurance (`run_qa`)**: Evaluates processing completion against YAML specification rules, automatically generating `QA_pass.list` and `QA_fail.list` session files along with human-readable (`.txt`) and structured (`.yaml`) QA reports [56-58].

#### Three-Tier Logging Hierarchy
QuNex generates logs across three distinct levels of granularity stored in `<studyfolder>/processing/logs/` [59, 60]:
1. **Recipe Logs**: High-level log reporting overall workflow progress, resolved command parameters, and a pass/fail summary for each command in a recipe [59, 61, 62].
2. **Summary / Run Logs (`runlogs`)**: Mid-level logs recording outgoing calls to external tools/pipelines per session, execution timestamps, parameter settings, and error messages preventing execution [63-66].
3. **Command Logs (`comlogs`)**: Low-level logs capturing the exact console output (`stdout` and `stderr`) generated by underlying binary tools (e.g., FreeSurfer, FSL, or HCP scripts) [63, 67, 68].

---

### 5. Required Folder Structures & Parameter / Batch Configuration Files

#### Study-Level Directory Structure
Initialized using `create_study`, the standard QuNex study hierarchy consists of the following [69-72]:

```text
<studyfolder>/
├── analysis/               # Group-level statistical analysis & scripts
├── processing/             # Preprocessing execution content
│   ├── logs/               # Log hierarchy (runlogs, comlogs, batchlogs, runchecks)
│   ├── lists/              # Session .list files for batching
│   ├── scripts/            # Study processing scripts
│   ├── scenes/             # QC and visualization Connectome Workbench scene files
│   └── batch.txt           # Active study-level batch configuration file
├── info/                   # Study metadata (demographics, tasks, stimuli, bids, hcpls)
└── sessions/               # Primary data root for individual sessions
    ├── inbox/              # Incoming scanner data (MR, EEG, BIDS, HCPLS)
    ├── archive/            # Backup folder for raw packed scanner data
    ├── specs/              # Study parameter templates & mapping files
    ├── QC/                 # Group-level quality control outputs
    └── <session_id>/       # Individual session subfolders
```

#### Session-Level Directory Structure
Inside `<sessionsfolder>/<session_id>/`, data follows a structured organization [43, 73]:
* **Metadata files**: `session.txt` (acquisition info) and `session_<pipeline>.txt` (mapped pipeline info) [43, 73, 74].
* **`dicom/` & `nii/`**: Raw DICOM folders and converted, un-preprocessed NIfTI images [43, 73].
* **`hcp/`**: Working directory for HCP minimal preprocessing pipelines (`unprocessed/`, `T1w/`, `MNINonLinear/`) [75-77].
* **`images/`**: Standardized directory where preprocessed HCP outputs are mapped for downstream analysis (`functional/`, `structural/`, `segmentation/`) [44, 73].
* **`QC/` & `logs/`**: Session-specific visual QC assets and console log outputs [73].

#### Mapping & Parameter Configuration Files
QuNex relies on specific configuration files to drive processing:

1. **Mapping Specification File (`specs/<pipeline>_mapping.txt` / `hcp_mapping.txt`)**:
   * Bridges raw sequence names/numbers from DICOM imports to standard pipeline descriptors [78-80].
   * **Example Syntax**: `fieldmap_phase => FM-Phase: fm(1)` or `T1w_MPR => T1w` [81].
   * The `create_session_info` command parses this file alongside `session.txt` to generate the pipeline-ready `session_hcp.txt` [82-84].
2. **Parameter Header Template (`specs/parameters.txt`)**:
   * Defines group-level parameters applying across the study (e.g., `_TR : 2.0`, `_hcp_unwarpdir : z`, `_hcp_brainsize : 150`) [85-87].
3. **Batch Parameter File (`processing/batch.txt`)**:
   * Compiled via `create_batch`, combining the group parameter header with the list of sessions and session/image-level overrides [88-90].

#### Hierarchical Parameter Precedence System
QuNex evaluates parameters using a strict 5-tier priority hierarchy (from lowest to highest precedence) [91-94]:
1. **Batch File Header** (Global defaults set at study level) [87, 91, 95]
2. **Recipe File (`recipe.yaml`)** (Parameters declared inside the recipe specification) [91, 94, 96]
3. **Command-Line Interface (CLI)** (Flags passed directly during call execution) [91, 92]
4. **Batch File Session Section** (Session-specific overrides inside `batch.txt`) [91, 93]
5. **Batch File Image Section** (Image-specific parameters defined directly on scan lines in `batch.txt`, highest priority) [91, 97].
