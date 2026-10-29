### QuNex Suite Architecture & CLI Execution Model

The **QuNex (Quantitative Neuroimaging Environment & Toolbox) Suite** provides an integrated framework for onboarding, preprocessing, and analyzing neuroimaging data [1, 2]. QuNex uses a standardized Command-Line Interface (CLI) syntax across its modules:
`qunex <command_name> --<parameter1>="<value1>" --<parameter2>="<value2>"` [3-6].

#### Global CLI & Utility Flags
- `--allcommands` / `--a`: Displays a complete list of available QuNex commands along with short descriptions [4, 6].
- `--help` / `--h`: Displays inline help and argument specifications for a specific command [4, 6].
- `--version`: Prints the current version of the installed QuNex suite [6, 7].
- `-o`: Prints a full and current list of supported processing parameters [8, 9].

#### Parameter Resolution Precedence Hierarchy
QuNex resolves parameter values using a strict 5-tier priority hierarchy (highest to lowest) [8, 10-12]:
1. **Command-line arguments** passed directly during the command call [10-12].
2. **Session / Image-level specifications** inside the study batch file [11].
3. **Recipe file definitions** when executed via `run_recipe` [10-12].
4. **Header section** (`_<parameter> : <value>`) of the study batch file (`batch.txt`) [11, 12].
5. **System / Pipeline defaults** [10, 11].

---

### Execution & Infrastructure Controls

#### Containerized Execution (`qunex_container`)
QuNex commands are executed inside Docker or Singularity/Apptainer containers using the `qunex_container` wrapper [5, 13, 14]:
- `--container="<path_or_tag>"`: **(Required)** Specifies the path to the Singularity/Apptainer image (`.sif`) or Docker container tag [13, 15].
- `--bind="<host_path>:<container_path>"`: Maps host directories into the container filesystem (comma-separated list) [16, 17].
- `--cuda`: Enables GPU acceleration inside the container via the NVIDIA Toolkit [18].
- `--env_status`: Verifies the QuNex environment setup and dependencies inside the container [19].
- `--bash_post="<command>"`: Executes a shell preamble after entering the container but before running the QuNex command [13, 20, 21].
- `--containeropt="<options>"`: Passes raw options directly to Docker or Singularity runtime calls [19].

#### High-Performance Computing (HPC) Parallelism & Scheduling
QuNex features built-in multi-session and multi-element parallelism, as well as native SLURM and PBS cluster job scheduling [22-25]:
- `--parsessions=<int>`: Sets the number of sessions processed concurrently on a single compute node (default: `1`) [24, 26, 27].
- `--parelements=<int>`: Sets the number of sub-elements (e.g., individual BOLD runs) processed in parallel within a session (default: `1`) [23, 24, 28, 29].
- `--parjobs=<int>`: Sets the maximum number of independent cluster jobs spawned across nodes [30, 31].
- `--scheduler="<Scheduler>,<key>=<value>,..."`: Submits commands to an HPC queue [22, 23, 32]:
  - **SLURM keys**: `jobname`, `time`, `cpus-per-task`, `mem-per-cpu`, `partition`, `gpus` [22, 33-35].
  - **PBS keys**: `jobname`, `walltime`, `nodes`, `ppn`, `mem`, `depend`, `umask` [25, 36].
- `--bash="<command>"`: Preloads environment modules (e.g., CUDA) on worker nodes prior to execution [32, 33, 37].

#### Workflow Recipe Orchestration (`run_recipe`)
`run_recipe` chains multiple sequential or parallel QuNex processing steps defined in a YAML recipe file [13, 38, 39]:
- `--recipe_file="<path>"`: Path to the YAML file containing recipe specifications [13, 39, 40].
- `--recipe="<name>"`: Name of the specific recipe to execute [39-41].
- `--steps="<step1,step2,...>"`: Runs a specific subset of commands from the recipe or an ad-hoc sequence [40, 42, 43].
- `--logfolder="<path>"`: Overrides the target output directory for recipe execution logs [39, 40].
- Dynamic substitution: Environment variables can be dynamically injected into recipe parameters using Mustache notation (`{{$VAR_NAME}}`) [13, 44, 45].

---

### Core Pipeline Commands & Parameters

#### 1. `hcp_pre_freesurfer` (HCP PreFreeSurfer Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_pre_freesurfer` [46]  
Executes structural preprocessing: averages multiple T1w/T2w acquisitions, performs AC-PC alignment, FNIRT-based brain extraction, readout/gradient distortion correction, and MNI atlas registration [46-48].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [49, 50]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [49, 50]. |
| `--sessions` | `None` | N/A | List or pattern of session IDs to process [49, 51]. |
| `--parsessions` | `1` | N/A | Number of parallel sessions to run [49, 51]. |
| `--overwrite` | `'no'` | N/A | Overwrites existing output directories (`yes`/`no`) [49, 50]. |
| `--hcp_suffix` | `''` | N/A | Appends a custom suffix to the HCP session folder [49, 50, 52]. |
| `--hcp_brainsize` | `150` | `brainsize` | Estimated head size in mm [53, 54]. |
| `--hcp_t1samplespacing` | Auto | `t1samplespacing` | Dwell time / sample spacing for T1w images [47, 53]. |
| `--hcp_t2samplespacing` | Auto | `t2samplespacing` | Dwell time / sample spacing for T2w images [47, 53]. |
| `--hcp_unwarpdir` / `--hcp_seunwarpdir` | Auto | `seunwarpdir` | Unwarping direction for spin-echo field maps (`x`, `y`, `z`, `-x`, etc.) [12, 47, 53]. |
| `--hcp_seechospacing` | Auto | `seechospacing` | Echo spacing for spin-echo field maps in seconds [47, 55]. |
| `--hcp_sephasepos` | Auto | `SEPhasePos` | Positive phase-encoding spin-echo image [54]. |
| `--hcp_sephaseneg` | Auto | `SEPhaseNeg` | Negative phase-encoding spin-echo image [54]. |
| `--hcp_gdcoeffs` | `'NONE'` | `gdcoeffs` | Path to scanner gradient distortion coefficient file [47]. |
| `--hcp_avgrdcmethod` | Auto | `avgrdcmethod` | Readout distortion correction method (`TOPUP`, `FIELDMAP`, `NONE`) [47]. |
| `--hcp_topupconfig` | Auto | `topupconfig` | Configuration file for FSL TOPUP [47]. |
| `--hcp_bfsigma` | Auto | `bfsigma` | Bias field smoothing sigma value [47]. |
| `--hcp_prefs_t1template` | Auto | `t1template` | Path to MNI152 T1w template volume [54]. |
| `--hcp_prefs_t1templatebrain` | Auto | `t1templatebrain` | Path to MNI152 skull-stripped T1w template [54]. |
| `--hcp_prefs_t1template2mm` | Auto | `t1template2mm` | Path to 2mm isotropic MNI152 T1w template [54]. |
| `--hcp_prefs_t2template` | Auto | `t2template` | Path to MNI152 T2w template volume [54]. |
| `--hcp_prefs_t2templatebrain` | Auto | `t2templatebrain` | Path to MNI152 skull-stripped T2w template [54]. |
| `--hcp_prefs_t2template2mm` | Auto | `t2template2mm` | Path to 2mm isotropic MNI152 T2w template [54]. |
| `--hcp_prefs_templatemask` | Auto | `templatemask` | Path to brain mask in MNI space [54]. |
| `--hcp_prefs_template2mmmask` | Auto | `template2mmmask` | Path to 2mm MNI brain mask [54]. |
| `--hcp_prefs_template_res` | Auto | N/A | Target resolution (in mm) for structural templates [50]. |
| `--hcp_prefs_fnirtconfig` | Auto | `fnirtconfig` | Configuration file for FNIRT nonlinear registration [54]. |
| `--hcp_prefs_custombrain` | Auto | `custombrain` | Path to user-provided custom brain mask [47]. |
| `--hcp_processing_mode` | `'HCPStyleData'` | `processing-mode` | Selects processing rules (`HCPStyleData` or `LegacyStyleData`) [47, 56, 57]. |
| `--hcp_t2` | `'t2'` | N/A | Set to `'NONE'` to run structural processing without T2w images [48, 51]. |

---

#### 2. `hcp_freesurfer` (HCP FreeSurfer Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_freesurfer` [58]  
Performs automated volume segmentation, subcortical labeling, and cortical surface reconstruction using FreeSurfer [58-60].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [58, 61]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [58, 61]. |
| `--sessions` | `None` | N/A | List or pattern of session IDs [26, 62]. |
| `--parsessions` | `1` | N/A | Concurrent sessions per node [58, 61]. |
| `--overwrite` | `'no'` | N/A | Overwrites existing FreeSurfer outputs [58, 61]. |
| `--hcp_suffix` | `''` | N/A | Suffix appended to target session folder [61, 63]. |
| `--hcp_freesurfer_home` | System | N/A | Overrides default `$FREESURFER_HOME` path [64, 65]. |
| `--hcp_high_myelin` | Auto | N/A | High myelin threshold value for `recon-all` [64]. |
| `--hcp_nogpu` | False | `gpu` | Set flag to force non-GPU version of FreeSurfer [62, 64]. |
| `--hcp_t2` | `'t2'` | N/A | Set to `'NONE'` when processing without T2w images [59, 65, 66]. |
| `--hcp_expert_file` | `''` | N/A | Path to FreeSurfer expert options configuration file [66]. |
| `--hcp_fs_seed` | Auto | `seed` | Random seed integer for `recon-all` repeatability [62]. |
| `--hcp_processing_mode` | `'HCPStyleData'` | `processing-mode` | Processing compliance mode (`HCPStyleData` or `LegacyStyleData`) [56, 57, 62]. |
| `--hcp_fs_existing_session` | `'FALSE'` | `existing-subject` | Reuses an existing FreeSurfer subject reconstruction [62, 63]. |
| `--hcp_fs_extra_reconall` | `''` | `extra-reconall-arg` | Additional raw CLI parameters passed directly to `recon-all` [62]. |
| `--hcp_fs_no_conf2hires` | `'FALSE'` | `no-conf2hires` | Disables high-resolution surface refinement steps [62, 63]. |
| `--hcp_fs_flair` | `'FALSE'` | `flair` | Uses FLAIR image for pial surface refinement instead of T2w [62, 63]. |

---

#### 3. `hcp_post_freesurfer` (HCP PostFreeSurfer Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_post_freesurfer` [67]  
Converts FreeSurfer outputs to NIfTI/CIFTI formats, creates high- and low-resolution surface meshes (`fs_LR`), and generates cortical myelin maps [67-70].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [67, 71]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [67, 71]. |
| `--sessions` | `None` | N/A | Session IDs to process [71, 72]. |
| `--parsessions` | `1` | N/A | Number of parallel sessions [67, 71]. |
| `--overwrite` | `'no'` | N/A | Overwrite existing outputs [71, 73]. |
| `--hcp_freesurfer_labels` | Look Up Table | `freesurferlabels` | Location of `FreeSurferAllLut.txt` lookup table [68, 74, 75]. |
| `--hcp_surfatlasdir` | Standard Mesh | `surfatlasdir` | Path to low-resolution standard mesh sphere templates [68, 73, 74]. |
| `--hcp_grayordinatesdir` | 91282 DIR | `grayordinatesdir` | Directory path for Grayordinates space templates [68, 73, 74]. |
| `--hcp_grayordinatesres` | `2` | `grayordinatesres` | Volume resolution (in mm) of grayordinates representation [68, 73, 74]. |
| `--hcp_subcortgraylabels` | Look Up Table | `subcortgraylabels` | Location of `FreeSurferSubcorticalLabelTableLut.txt` [68, 73, 74]. |
| `--hcp_refmyelinmaps` | Reference Map | `refmyelinmaps` | Group myelin map file used for bias field correction [68, 73]. |
| `--hcp_hiresmesh` | `164` | `hiresmesh` | High-resolution mesh size (in thousands of vertices per hemisphere, e.g., 164k) [68, 76]. |
| `--hcp_lowresmesh` | `32` | `lowresmesh` | Low-resolution mesh size (in thousands of vertices per hemisphere, e.g., 32k) [68, 76]. |
| `--hcp_mcsigma` | `sqrt(200)` | `mcsigma` | Correction sigma (FWHM) for myelin map smoothing [68, 76]. |
| `--hcp_regname` | `'MSMSulc'` | `regname` | Surface registration method (`MSMSulc` or `FS`) [68, 76]. |
| `--hcp_inflatescale` | `1` | `inflatescale` | Surface inflation scaling factor [68, 76]. |
| `--hcp_fs_ind_mean` | `'YES'` | `use-ind-mean` | Uses session myelin map mean as reference map mean (`YES`/`NO`) [68, 75]. |
| `--hcp_processing_mode` | `'HCPStyleData'` | `processing-mode` | Processing compliance mode (`HCPStyleData` or `LegacyStyleData`) [56, 57, 68]. |
| `--hcp_thickness_regression` | `'BOTH'` | `thickness-regression` | Curvature-thickness regression model (`OLD`, `NEW`, `BOTH`) [68, 75]. |

---

#### 4. `hcp_fmri_volume` (HCP fMRIVolume Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_fmri_volume` [77]  
Preprocesses 4D BOLD timeseries: motion correction, EPI distortion correction, slice-timing correction, and rigid/non-linear registration to MNI volume space [77-79].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [80]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [80]. |
| `--sessions` | `None` | N/A | Specific session IDs to process [44, 81]. |
| `--parsessions` | `1` | N/A | Concurrent sessions per node [81]. |
| `--parelements` | `1` | N/A | Concurrent BOLD runs processed in parallel within a session [23, 81]. |
| `--overwrite` | `'no'` | N/A | Overwrites existing volume outputs [81]. |
| `--hcp_bold_res` | `'2'` | `fmrires` | Target spatial resolution (mm) of output fMRI volume [82, 83]. |
| `--hcp_bold_biascorrection` | Auto | `biascorrection` | Bias field correction method (`SEBASED`, `LEGACY`, `NONE`) [83]. |
| `--hcp_bold_echodiff` | Auto | `echodiff` | Delta TE for GE field map distortion correction [83]. |
| `--hcp_gdcoeffs` | `'NONE'` | `gdcoeffs` | Scanner gradient distortion coefficient file path [83]. |
| `--hcp_bold_dcmethod` | Auto | `dcmethod` | Distortion correction method (`TOPUP`, `FIELDMAP`, `SiemensFieldMap`, `NONE`) [83]. |
| `--hcp_bold_echospacing` | Auto | `echospacing` | Effective EPI echo spacing in seconds [83]. |
| `--hcp_bold_unwarpdir` | Auto | `unwarpdir` | Phase-encoding unwarping direction (`x`, `y`, `z`, `-x`, `-y`, etc.) [83]. |
| `--hcp_bold_topupconfig` | Auto | `topupconfig` | TOPUP configuration file [83]. |
| `--hcp_bold_dof` | `6` | `dof` | Degrees of Freedom for motion correction / registration [83]. |
| `--hcp_printcom` | `''` | `printcom` | Debugging flag to print underlying shell commands [83]. |
| `--hcp_bold_usejacobian` | Auto | `usejacobian` | Applies Jacobian intensity modulation during unwarping (`TRUE`/`FALSE`) [83]. |
| `--hcp_bold_movreg` / `--hcp_bold_movereg` | `'FLIRT'` | `mctype` | Motion correction tool (`MCFLIRT` or `FLIRT`) [81, 83]. |
| `--hcp_bold_preregistertool` | Auto | `preregistertool` | Pre-registration tool prior to BBR alignment [83]. |
| `--hcp_processing_mode` | `'HCPStyleData'` | `processing-mode` | Processing compliance rules (`HCPStyleData` or `LegacyStyleData`) [56, 57, 83]. |
| `--hcp_bold_doslicetime` | `'FALSE'` | N/A | Enables slice-timing correction for single-band BOLD acquisitions [79, 81]. |
| `--hcp_bold_movref` / `--hcp_bold_moveref` | `'SBRef'` | N/A | Motion reference image (`first` volume or `SBRef`) [81, 83]. |
| `--hcp_bold_seimg` | Auto | N/A | Spin-echo reference image selection (`first`, `mean`) [83, 84]. |
| `--hcp_bold_refreg` | Auto | N/A | BOLD-to-structural reference registration mode (`nonlinear`, `rigid`) [83, 84]. |
| `--hcp_bold_mask` | Auto | N/A | FOV and brain masking strategy (e.g., `T1_DILATED2x_fMRI_FOV`, `DILATED`) [81, 83, 84]. |

---

#### 5. `hcp_fmri_surface` (HCP fMRISurface Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_fmri_surface` [85]  
Samples volume-preprocessed BOLD timeseries onto cortical surface meshes, performs subcortical volume processing, and outputs Grayordinate CIFTI dense timeseries (`.dtseries.nii`) [86-89].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [90]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [90]. |
| `--sessions` | `None` | N/A | Session IDs to process [44, 86]. |
| `--parsessions` | `1` | N/A | Concurrent sessions per node [86]. |
| `--parelements` | `1` | N/A | Concurrent BOLD runs processed in parallel [86]. |
| `--overwrite` | `'no'` | N/A | Overwrites existing surface/CIFTI outputs [44, 86]. |
| `--hcp_lowresmesh` | `32` | `lowresmesh` | Mesh density (in thousands of vertices per hemisphere, e.g., `32` for 32k_fs_LR) [86, 91]. |
| `--hcp_bold_res` | `'2'` | `fmrires` | Volume spatial resolution (mm) of input fMRI data [86, 92]. |
| `--hcp_bold_smoothFWHM` | `2` | `smoothingFWHM` | Surface geodesic smoothing kernel FWHM in mm [82, 86, 92]. |
| `--hcp_grayordinatesres` | `2` | `grayordinatesres` | Subcortical voxel resolution (mm) in grayordinates space [82, 86, 92]. |
| `--hcp_regname` | `'MSMSulc'` | `regname` | Surface registration sphere used for resampling (`MSMSulc`, `MSMAll`, `FS`) [86, 92]. |
| `--hcp_printcom` | `''` | `printcom` | Print internal command execution strings [86]. |
| `--hcp_filename` | `'automated'` | N/A | BOLD file naming convention (`automated` or `userdefined`) [91, 93-95]. |
| `--hcp_bold_prefix` | `'BOLD'` | N/A | File prefix used when generating automated BOLD directory names [91]. |
| `--hcp_longitudinal_template` | `'base'` | `longitudinal-template` | Template identifier for longitudinal workflows [86, 92]. |
| `--longitudinal` | False | `is-longitudinal` | Set flag if running in longitudinal mode [86, 87]. |

---

#### 6. `hcp_diffusion` (HCP Diffusion Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_diffusion` [96]  
Executes diffusion MRI preprocessing: $b_0$ intensity normalization, TOPUP distortion modeling, FSL `eddy` motion/eddy-current correction with gradient vector reorientation, and BBR registration to native T1w space [97-101].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [97, 102]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [97, 102]. |
| `--sessions` | `None` | N/A | Session IDs to process [33, 102]. |
| `--parsessions` | `1` | N/A | Number of parallel sessions [97, 102]. |
| `--overwrite` | `'no'` | N/A | Overwrites existing diffusion outputs [97, 102]. |
| `--hcp_suffix` | `''` | N/A | Suffix appended to target session folder [102, 103]. |
| `--logfolder` | `''` | N/A | Custom path for command execution logs [97, 103]. |
| `--hcp_dwi_echospacing` | Auto | `echospacing` | EPI echo spacing in seconds [97, 98, 103]. |
| `--use_sequence_info` | `'all'` | N/A | Inline DICOM sequence headers used in preprocessing [103, 104]. |
| `--hcp_dwi_posdata` | `''` | `posData` | Comma-separated list overriding positive phase-encoding dMRI images [98, 105]. |
| `--hcp_dwi_negdata` | `''` | `negData` | Comma-separated list overriding negative phase-encoding dMRI images [98, 105]. |
| `--hcp_dwi_dummy_bval_bvec` | False | N/A | Generates dummy `bval`/`bvec` files if missing [105]. |
| `--hcp_dwi_phasepos` | Auto | `PEdir` | Phase-encoding direction specifier [98]. |
| `--hcp_dwi_gdcoeffs` | `'NONE'` | `gdcoeffs` | Scanner gradient distortion coefficient file path [98, 106]. |
| `--hcp_dwi_dof` | `6` | `dof` | Degrees of Freedom for post-eddy structural registration [98, 107]. |
| `--hcp_dwi_b0maxbval` | `50` | `b0maxbval` | Maximum b-value threshold treated as $b_0$ volumes [98, 107]. |
| `--hcp_dwi_combinedata` | `1` | `combine-data-flag` | Image pair combination strategy (`1` = combine PE pairs; `2` = uncombined) [98, 107]. |
| `--hcp_printcom` | `''` | `printcom` | Debugging flag to print underlying commands [98]. |
| `--hcp_dwi_extraeddyarg` | `''` | `extra-eddy-arg` | Raw arguments appended directly to the FSL `eddy` call [98]. |
| `--hcp_dwi_name` | `'Diffusion'` | `dwiname` | Output directory name for diffusion results [98, 108]. |
| `--hcp_dwi_selectbestb0` | Auto | `select-best-b0` | Selects best $b_0$ image for registration [98]. |
| `--hcp_dwi_topupconfig` | Auto | `topup-config-file` | TOPUP configuration file path [98]. |
| `--hcp_dwi_even_slices` | False | `ensure-even-slices` | Trims odd slices to ensure even slice count for TOPUP/eddy [98, 108]. |
| `--hcp_nogpu` | False | `gpu` | Set flag to run CPU-based `eddy` instead of CUDA GPU `eddy` [85, 97, 98, 108, 109]. |
| `--hcp_longitudinal_template` | `'base'` | `longitudinal-template` | Template name for longitudinal processing [98, 106]. |
| `--longitudinal` | False | `is-longitudinal` | Set flag if running longitudinal variant [98, 106]. |

---

#### 7. `hcp_icafix` (HCP ICAFIX Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_icafix` [110]  
Performs automated signal vs. noise ICA component classification using FIX and regresses noise components and motion parameters out of fMRI timeseries [110-113]. Automatically triggers `hcp_post_fix` upon completion [112, 113].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [29, 110]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [29, 110]. |
| `--sessions` | `None` | N/A | Session IDs to process [29, 114]. |
| `--parsessions` | `1` | N/A | Number of parallel sessions [29, 110]. |
| `--parelements` | `1` | N/A | Number of parallel BOLD elements [29, 110]. |
| `--overwrite` | `'no'` | N/A | Overwrites existing FIX outputs [29, 110]. |
| `--hcp_icafix_bolds` | `''` | N/A | Specifies run grouping (e.g., `"GROUP_1:BOLD_1,BOLD_2\|GROUP_2:BOLD_3,BOLD_4"`). Concatenates all BOLDs to `fMRI_CONCAT_ALL` if omitted [111, 114]. |
| `--hcp_icafix_highpass` | `0` / `2000` | `high-pass` | High-pass temporal filter cutoff in seconds (`0` for multi-run, `2000` for single-run) [82, 111, 112]. |
| `--hcp_icafix_domotionreg` | `TRUE` / `FALSE` | `motion-regression` | Regresses 24 motion parameters (`TRUE` for single-run, `FALSE` for multi-run) [111, 115, 116]. |
| `--hcp_icafix_model` | Pre-trained | `training-file` | Path to trained FIX classifier model (`.RData`) [111]. |
| `--hcp_icafix_threshold` | `20` | `fix-threshold` | FIX classification signal/noise threshold [111]. |
| `--hcp_icafix_deleteintermediates` | `'FALSE'` | `delete-intermediates` | Deletes high-pass filtered intermediate 4D volumes after cleaning (`TRUE`/`FALSE`) [111, 117]. |
| `--hcp_icafix_fallbackthreshold` | Auto | `fallback-threshold` | Secondary threshold used if initial classification yields ambiguous components [111]. |
| `--hcp_icafix_parallel_limit` | Auto | `parallel-limit` | Maximum CPU thread limit for internal MATLAB/R calculations [111]. |
| `--hcp_matlab_mode` | System | N/A | MATLAB execution mode (`interpreted`, `compiled`, or `octave`) [111, 118, 119]. |
| `--hcp_icafix_postfix` | `'TRUE'` | N/A | Set to `'FALSE'` to disable automatic execution of `hcp_post_fix` [112, 113]. |

---

#### 8. `hcp_msmall` (HCP MSMAll Multi-Modal Surface Matching Pipeline)
**Function**: `qx_utilities.hcp.process_hcp.hcp_msmall` [120]  
Executes multi-modal surface-based registration aligning cortical folding, myelin maps, and resting-state fMRI network topography to the group template [121-123]. Automatically triggers `hcp_dedrift_and_resample` unless disabled [122, 123].

| Command Flag / Parameter | Default | Mapped HCP Pipeline Parameter | Description |
| :--- | :--- | :--- | :--- |
| `--batchfile` | `''` | N/A | Path to study `batch.txt` file [124]. |
| `--sessionsfolder` | `'.'` | N/A | Base directory containing session folders [124, 125]. |
| `--sessions` | `None` | N/A | Session IDs to process [125, 126]. |
| `--parsessions` | `1` | N/A | Concurrent sessions [125, 127]. |
| `--parelements` | `1` | N/A | Concurrent MSMAll group elements [125, 127]. |
| `--hcp_suffix` | `''` | N/A | Suffix appended to target session folder [125, 127]. |
| `--logfolder` | `''` | N/A | Custom log output path [125, 127]. |
| `--hcp_icafix_bolds` | `''` | N/A | BOLD run grouping matching the `hcp_icafix` configuration [125, 126, 128, 129]. |
| `--hcp_msmall_bolds` | `''` | N/A | Specific BOLD runs used as input features for MSMAll [126, 127, 129]. |
| `--hcp_hiresmesh` | `164` | `high-res-mesh` | High-resolution mesh size (164k) [121, 130-132]. |
| `--hcp_lowresmesh` | `32` | `low-res-mesh` | Low-resolution fMRI mesh size (32k) [121, 130-132]. |
| `--hcp_regname` | `'MSMSulc'` | `input-registration-name` | Starting input surface registration [121, 130-132]. |
| `--hcp_matlab_mode` | System | `matlab-run-mode` | MATLAB execution mode (`interpreted`, `compiled`, `octave`) [121, 130-132]. |
| `--hcp_msmall_procstring` | Auto | `fmri-proc-string` | Filename descriptor for input FIX-cleaned timeseries [121, 130-132]. |
| `--hcp_msmall_outfmriname` | `'rfMRI_REST'` | `output-fmri-name` | Output name for concatenated MSMAll fMRI series [121, 127, 130, 133]. |
| `--hcp_icafix_highpass` | `0` / `2000` | `high-pass` | Filter cutoff matching the ICAFIX step [121, 127, 130, 133]. |
| `--hcp_msmall_templates` | Template DIR | `msm-all-templates` | Path to directory containing MSMAll template files [121, 127, 130, 133]. |
| `--hcp_msmall_outregname` | `'MSMAll_InitialReg'` | `output-registration-name` | Output registration sphere name [121, 127, 130, 133]. |
| `--hcp_msmall_myelin_target` | Target Map | `myelin-target-file` | Reference group myelin map target file [121, 130, 134-136]. |
| `--hcp_msmall_module_name` | Auto | `module-name` | Internal MSM module execution name [121]. |
| `--hcp_msmall_iteration_modes` | Auto | `iteration-modes` | Iterative registration stage parameters [121]. |
| `--hcp_msmall_method` | Auto | `method` | MSM cost functional optimization method [121]. |
| `--hcp_msmall_use_migp` | Auto | `use-migp` | Enables MIGP (MELODIC Incremental Group PCA) data reduction [121]. |
| `--hcp_msmall_ica_dim` | Auto | `ica-dim` | ICA dimensionality for functional feature extraction [121]. |
| `--hcp_msmall_low_sica_dims` | Auto | `low-sica-dims` | Lower-dimensional sICA settings [121]. |
| `--hcp_msmall_vn` | Auto | `vn` | Variance normalization option [121]. |
| `--hcp_msmall_reg_conf_path` | Auto | `registration-configure-path` | Path to MSM solver configuration file [121]. |
| `--hcp_msmall_reg_vars` | Auto | `registration-configure-override-variables` | Key-value overrides for MSM solver variables [121]. |
| `--hcp_msmall_rsn_template` | Template File | `rsn-template-file` | Resting-state network spatial template file [121]. |
| `--hcp_msmall_rsn_weights` | Weights File | `rsn-weights-file` | Resting-state network weighting map [121, 136]. |
| `--hcp_msmall_topography_roi` | ROI File | `topography-roi-file` | Cortical topography ROI mask [121, 136]. |
| `--hcp_msmall_topography_target` | Target File | `topography-target-file` | Cortical topography target map [121, 136]. |
| `--hcp_msmall_no_ind_mean` | False | `use-ind-mean` | Disables individual mean scaling for reference myelin map [121, 136]. |
| `--hcp_msmall_start_frame` | `1` | `start-frame` | Starting frame index for single-run feature extraction [121, 122]. |
| `--hcp_msmall_end_frame` | Last | `end-frame` | Ending frame index for single-run feature extraction [121, 122]. |
| `--hcp_msmall_resample` | `'TRUE'` | N/A | Set to `'FALSE'` to disable automatic execution of `hcp_dedrift_and_resample` [122, 123]. |

---

#### 9. `run_qc` (QuNex Quality Control Pipeline)
**Function**: `qx_utilities.bash.run_qc` [137]  
Generates Connectome Workbench scene files (`.wb.scene`) and high-resolution PNG image snapshots for visual quality inspection across structural, functional, and diffusion modalities [21, 93, 137].

| Command Flag / Parameter | Default | Description |
| :--- | :--- | :--- |
| `--sessionsfolder` | Path | **(Required)** Base directory containing session folders [138, 139]. |
| `--sessions` | Session List | Comma-separated list or pattern of session IDs [138, 139]. |
| `--modality` | Modality | **(Required)** QC target modality (`rawNII`, `T1w`, `T2w`, `myelin`, `BOLD`, `DWI`, `general`, `eddyQC`) [138, 139]. |
| `--datapath` | Auto | Overrides default input path for data images [137]. |
| `--datafile` | Auto | Overrides default input filename [137]. |
| `--batchfile` | `''` | Path to study `batch.txt` file [137, 140-142]. |
| `--timestamp` | System Time | Custom timestamp identifier string appended to log outputs [137, 143]. |
| `--dwipath` | `'Diffusion'` | Path containing preprocessed diffusion data [144-146]. |
| `--dwidata` | `'data'` | Filename prefix for dMRI data [144-146]. |
| `--dtifitqc` | `'yes'` | Generates tensor fit visual QC figures (`yes`/`no`) [144, 146]. |
| `--bedpostxqc` | `'yes'` | Generates BedpostX fiber orientation QC figures (`yes`/`no`) [146, 147]. |
| `--eddyqcstats` | `'yes'` | Links FSL `eddy` QC statistics and motion reports into the QC folder (`yes`/`no`) [146, 147]. |
| `--boldprefix` | `'BOLD'` | BOLD directory/file prefix name [147, 148]. |
| `--boldsuffix` | `'Atlas'` | BOLD file suffix (e.g., `Atlas` for CIFTI grayordinate data) [141, 145, 147, 149]. |
| `--skipframes` | `0` | Number of initial frames skipped during image rendering [137]. |
| `--bolddata` | Auto | Specific BOLD run identifiers (e.g., `'1'`, `'1,6'`, `'blink'`, `'BOLD_1,BOLD_2'`) [140-142, 145, 147, 148]. |
| `--boldfcinput` | Auto | Data input image file path for BOLD FC QC [137, 140, 146]. |
| `--hcp_filename` | `'automated'` | Naming strategy (`automated` or `userdefined`) [93]. |
| `--overwrite` | `'no'` | Overwrites existing QC scene and image files [138, 139, 150]. |
| `--hcp_suffix` | `''` | Suffix for parallel HCP pipeline variants [150]. |
| `--scenetemplatefolder` | Template DIR | Path to scene template files (default: `${TOOLS}/${QUNEXREPO}/qx_library/data/scenes/qc`) [137, 139, 150]. |
| `--outpath` | Auto | Output directory for group QC results (default: `<sessionsfolder>/QC/<modality>`) [137, 139, 151]. |
| `--scenezip` | `'yes'` | Packages generated Workbench scenes into compressed `.zip` files (`yes`/`no`) [4, 137, 152]. |
| `--userscenefile` | `''` | Custom user scene filename [143]. |
| `--userscenepath` | `''` | Path containing user custom scene templates [143]. |
| `--suffix` | Auto | Custom suffix formatted as `<session_id>_<timestamp>` [143, 144]. |
| `--snronly` | `'no'` | Set to `'yes'` to compute BOLD temporal SNR maps while omitting scene generation [141, 142, 144]. |
| `--boldfc` | `''` | Computes functional connectivity QC (`pscalar` or `pconn`) [140, 142, 146]. |
| `--boldfcpath` | Functional DIR | Input folder containing functional connectivity files [140, 142]. |
| `--processcustom` | `'no'` | Set to `'yes'` to process additional custom scenes from `processing/scenes/QC/` [153]. |
| `--omitdefaults` | `'no'` | Omits standard default scene rendering (`yes`/`no`) [152-154]. |
| `--sourcefile` | `'session_hcp.txt'` | Source session information mapping filename [93, 153]. |
| `--overwritestep` | `'no'` | Explicitly overwrites prior step outputs (`yes`/`no`) [146, 155]. |

---

### Command Syntax Reference & Specific Usage Examples

```bash
# 1. Structural Preprocessing
qunex hcp_pre_freesurfer \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --parsessions=4 \
    --hcp_brainsize=150 \
    --overwrite="no" [51, 53, 156]

qunex hcp_freesurfer \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --parsessions=4 \
    --hcp_t2="NONE" \
    --overwrite="no" [65, 157]

qunex hcp_post_freesurfer \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --parsessions=4 \
    --hcp_grayordinatesres=2 \
    --hcp_hiresmesh=164 \
    --hcp_lowresmesh=32 \
    --overwrite="no" [72, 73]

# 2. Functional Preprocessing
qunex hcp_fmri_volume \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --parsessions=2 \
    --parelements=4 \
    --hcp_bold_doslicetime="TRUE" \
    --hcp_bold_movreg="MCFLIRT" \
    --hcp_bold_mask="T1_DILATED2x_fMRI_FOV" \
    --overwrite="yes" [81]

qunex hcp_fmri_surface \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --parsessions=4 \
    --parelements=4 \
    --hcp_lowresmesh=32 \
    --hcp_bold_smoothFWHM=2 \
    --overwrite="no" [44, 158]

# 3. Diffusion Preprocessing
qunex hcp_diffusion \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --parsessions=1 \
    --hcp_dwi_b0maxbval=50 \
    --hcp_dwi_combinedata=1 \
    --bash="module load CUDA/11.3.1" \
    --scheduler="SLURM,time=24:00:00,cpus-per-task=1,mem-per-cpu=16000,partition=GPU,gpus=1" [33, 107]

# 4. Denoising & Surface Matching
qunex hcp_icafix \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --hcp_icafix_bolds="GROUP_1:BOLD_1,BOLD_2|GROUP_2:BOLD_3,BOLD_4" \
    --hcp_icafix_highpass=0 \
    --hcp_matlab_mode="interpreted" [111, 114]

qunex hcp_msmall \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --hcp_icafix_bolds="GROUP_1:REST_1,REST_2,TASK_1|GROUP_2:REST_3,TASK_2" \
    --hcp_msmall_bolds="REST_1,REST_2" \
    --hcp_matlab_mode="interpreted" [121, 126]

# 5. Quality Control
qunex run_qc \
    --sessionsfolder="/data/study/sessions" \
    --batchfile="/data/study/processing/batch.txt" \
    --modality="BOLD" \
    --bolddata="1,2" \
    --boldsuffix="Atlas" \
    --outpath="/data/study/sessions/QC/BOLD" \
    --scenezip="yes" \
    --overwrite="yes" [18, 141, 145, 148, 149]
```
