The documented command-line flags, arguments, options, and parameters for the Human Connectome Project (HCP) Pipelines across native scripts and wrapper interfaces (such as QuNex) are organized by pipeline below.

---

### 1. PreFreeSurfer Pipeline (`PreFreeSurferPipeline.sh` / `hcp_pre_freesurfer`)

The PreFreeSurfer pipeline aligns T1w and T2w structural images to MNI space, performs rigid alignment, averages multiple structural runs, and corrects for gradient distortion and bias field [1, 2].

* **`--sessionsfolder`**: Directory path containing subject sessions [3].
* **`--batchfile`**: Path to the batch information file defining subject lists and modalities [4, 5].
* **`--hcp_processing_mode` / `--processing-mode`**: Controls acquisition compliance enforcement (**`HCPStyleData`** requiring T1w+T2w vs. **`LegacyStyleData`** allowing T1w-only processing) [1, 6].
* **`--hcp_prefs_templatemask` / `--templatemask`**: Custom template brain mask path [1, 7].
* **`--hcp_prefs_template2mmmask` / `--template2mmmask`**: Path to 2 mm template brain mask (default: **`MNI152_T1_2mm_brain_mask_dil.nii.gz`**) [1, 7].
* **`--hcp_prefs_fnirtconfig` / `--fnirtconfig`**: FNIRT non-linear registration configuration file (default: **`T1_2_MNI152_2mm.cnf`**) [1, 7].
* **`--hcp_prefs_custombrain` / `--custombrain`**: Path to custom brain image for template alignment [1].
* **`--use_sequence_info`**: Specifies DICOM/JSON sidecar sequence tags to parse (**`all`**, **`phenc`**, **`DwellTime`**, **`UnwarpDir`**, **`EchoSpacing`**) [8, 9].
* **`--hcp_sephasepos` / `--SEPhasePos`**: Spin-echo positive phase encoding direction [1].
* **`--hcp_seechospacing` / `--seechospacing`**: Echo spacing value for spin-echo field maps [1].
* **`--hcp_seunwarpdir` / `--seunwarpdir`**: Direction for spin-echo EPI distortion unwarping [1].
* **`--hcp_t1samplespacing` / `--t1samplespacing`**: Readout sample spacing for T1w acquisitions [1].
* **`--hcp_t2samplespacing` / `--t2samplespacing`**: Readout sample spacing for T2w acquisitions [1].
* **`--hcp_gdcoeffs` / `--gdcoeffs`**: Path to scanner-specific gradient nonlinearity distortion coefficients (`.coef` file) [1].
* **`--hcp_avgrdcmethod` / `--avgrdcmethod`**: Readout distortion correction method [1].
* **`--hcp_topupconfig` / `--topupconfig`**: TOPUP configuration file path [1].
* **`--hcp_bfsigma` / `--bfsigma`**: Smoothing sigma for structural bias field estimation [1].

---

### 2. FreeSurfer Pipeline (`FreeSurferPipeline.sh` / `hcp_freesurfer`)

The FreeSurfer pipeline performs tissue segmentation, cortical surface reconstruction, and subcortical parcellation tuned for HCP high-resolution structural data [2, 10].

* **`--session-dir` (`SessionDIR`)**: Path to the target session directory containing structural inputs [11, 12].
* **`--session` (`SessionID`)**: Subject/session ID label [11, 12].
* **`--processing-mode` (`ProcessingMode`)**: Processing compliance mode (**`HCPStyleData`** or **`LegacyStyleData`**) [11, 13].
* **`--t1` (`T1wImage`)**: Path to ACPC-aligned, bias-corrected T1w image (`T1w_acpc_dc_restore.nii.gz`) [11, 12].
* **`--t1brain` (`T1wImageBrain`)**: Path to brain-extracted T1w image (`T1w_acpc_dc_restore_brain.nii.gz`) [11, 14].
* **`--t2` (`T2wImage`)**: Path to ACPC-aligned, bias-corrected T2w image (`T2w_acpc_dc_restore.nii.gz`) [14, 15].
* **`--seed` (`hcp_fs_seed`)**: Random seed number for FreeSurfer stochastic steps [16].
* **`--existing-subject` (`hcp_fs_existing_session`)**: Boolean flag (`TRUE`/`FALSE`) to run on an existing subject directory, suppressing initial `recon-all -i` call [16, 17].
* **`--extra-reconall-arg` (`hcp_fs_extra_reconall`)**: Pipe-separated string (`|`) of custom arguments passed directly to `recon-all` [13, 16, 17].
* **`--no-conf2hires` (`hcp_fs_no_conf2hires`)**: Disables sub-millimeter high-resolution surface refining steps when input resolution is 1 mm or lower [16, 18].
* **`--flair` (`hcp_fs_flair`)**: Flag (`TRUE`/`FALSE`) directing `recon-all` to refine pial surfaces using FLAIR instead of T2w [16, 18].
* **`--gpu` / `--nogpu` (`hcp_nogpu`)**: Enables or disables GPU-accelerated FreeSurfer routines [16, 19].
* **`--high_myelin`**: Myelin intensity threshold for FreeSurfer surface placement [19].
* **`--freesurfer_home`**: Manual override path for `FREESURFER_HOME` [19].

---

### 3. PostFreeSurfer Pipeline (`PostFreeSurferPipeline.sh` & Sub-scripts)

PostFreeSurfer converts FreeSurfer volumes and surfaces to NIfTI/GIFTI, registers surfaces to standard `fs_LR` space using MSMSulc, generates full-resolution ribbon files, and computes myelin maps [20-22].

#### Mandatory Arguments (`PostFreeSurferPipeline.sh`):
* **`--study-folder` (`StudyFolder`)**: Absolute path to study directory containing all subject folders [23].
* **`--session` (`Session`) / `--subject`**: Session or visit ID label [23].
* **`--subcortgraylabels` (`SubcorticalGrayLabels`)**: Path to `FreeSurferSubcorticalLabelTableLut.txt` [24].
* **`--freesurferlabels` (`FreeSurferLabels`)**: Path to `FreeSurferAllLut.txt` lookup table [24].
* **`--refmyelinmaps` (`ReferenceMyelinMaps`)**: Path to group reference myelin map file used for bias correction [24].

#### Optional Arguments (`PostFreeSurferPipeline.sh`):
* **`--surfatlasdir` (`SurfaceAtlasDIR`)**: Path to standard mesh atlases (default: `$HCPPIPEDIR/global/templates/standard_mesh_atlases`) [23].
* **`--grayordinatesres` (`GrayordinatesResolution`)**: Spatial resolution of grayordinates in mm (default: **`2`**; alternative: **`1.60`**) [23, 25].
* **`--grayordinatesdir` (`GrayordinatesSpaceDIR`)**: Template directory path for grayordinates (auto-set based on resolution if omitted) [23, 25].
* **`--hiresmesh` (`HighResMesh`)**: Vertex count in thousands for high-resolution mesh (default: **`164`**k) [24].
* **`--lowresmesh` (`LowResMeshes`)**: Mesh resolution for fMRI data (default: **`32`**k; or multi-resolution list like `32@59`) [24, 25].
* **`--mcsigma` (`CorrectionSigma`)**: Sigma value for myelin map bias correction (default: **$\sqrt{200} \approx 14.14$**) [23, 24].
* **`--regname` (`RegName`)**: Surface registration technique (default: **`MSMSulc`**; alternative: `FS`) [24].
* **`--inflatescale` (`InflateExtraScale`)**: Scaling factor for extra surface inflation (default: **`1`**) [24].
* **`--processing-mode` (`ProcessingMode`)**: Compliance mode (**`HCPStyleData`** or **`LegacyStyleData`**) [24].
* **`--structural-qc` (`QCMode`)**: Structural QC execution setting (**`yes`**, **`no`**, or **`only`**; default: **`yes`**) [24, 25].
* **`--use-ind-mean` (`UseIndMean`)**: Use individual session myelin map mean as group reference mean (**`YES`** or **`NO`**, default: **`YES`**) [24].
* **`--thickness-regression` (`ThicknessReg`)**: Thickness-curvature regression model (**`OLD`**, **`NEW`**, or **`BOTH`**; default: **`BOTH`**) [24, 25].
* **`--subject-long` (`Subject`)**: Subject ID label used in longitudinal mode [24].
* **`--longitudinal-mode` (`LongitudinalMode`)**: Longitudinal processing stage (**`NONE`**, **`TIMEPOINT_STAGE1`**, **`TIMEPOINT_STAGE2`**, or **`TEMPLATE`**; default: **`NONE`**) [24, 25].
* **`--longitudinal-template` (`LongitudinalTemplate`)**: FreeSurfer longitudinal template ID [25].
* **`--sessions` (`SessionList`)**: `@`-separated list of session IDs when running in `TEMPLATE` longitudinal mode [25].
* **`--species` (`Species`)**: Target species (default: **`Human`**) [25].
* **`--myelin-volume-fwhm` (`MyelinVolumeFWHM`)**: Volume smoothing FWHM in mm for myelin mapping (default: **`5`**) [25].
* **`--myelin-surface-fwhm` (`MyelinSurfaceFWHM`)**: Surface smoothing FWHM in mm for myelin mapping (default: **`4`**) [25].
* **`--msmsulc-conf` (`MSMSulcConf`)**: Configuration file name for MSMSulc (default: **`MSMSulcStrainFinalconf`**) [25].
* **`--flatmap-root-name` (`FlatMapRootName`)**: Root filename for flat maps (default: **`colin.cerebral`**) [25].

#### Sub-script Arguments (`FreeSurfer2CaretConvertAndRegisterNonlinear.sh`):
* Mandatory: `--study-folder`, `--session`, `--t1w-folder`, `--atlas-space-folder`, `--freesurfer-folder`, `--surface-atlas-dir`, `--high-res-mesh`, `--low-res-meshes`, `--atlas-transform`, `--inverse-atlas-transform`, `--freesurfer-labels`, `--grayordinates-space-dir`, `--grayordinates-resolutions`, `--subcortical-gray-labels`, `--reg-name`, `--inflate-extra-scale`, `--longitudinal-mode`, `--species`, `--msm-sulc-conf`, `--flat-map-root-name` [26-28].
* Optional: `--native-folder` (default: `Native`), `--freesurfer-input` (default: `T1w_acpc_dc_restore_1mm`), `--t1w-image` (default: `T1w_acpc_dc_restore`), `--t2w-image` (default: `T2w_acpc_dc_restore`), `--atlas-space-t1w-image` (default: `T1w_restore`), `--atlas-space-t2w-image` (default: `T2w_restore`), `--t1w-image-brain-mask` (default: `brainmask_fs`), `--longitudinal-template`, `--longitudinal-timepoints` [26-29].

---

### 4. fMRIVolume Pipeline (`fMRIVolumePipeline.sh` / `hcp_fmri_volume`)

fMRIVolume completes slice timing correction, motion correction, EPI distortion correction, BOLD-to-T1w co-registration, and one-step resampling into MNI volume space [30].

* **`--sessionsfolder`**: Target sessions root directory [4, 5].
* **`--batchfile`**: Batch execution file defining subject BOLD series [4, 5].
* **`--hcp_wb_resample`**: Enables Workbench (`wb_command`) for volume resampling rather than FSL `applywarp` [31].
* **`--hcp_processing_mode`**: Controls acquisition mode compliance (`HCPStyleData` vs. `LegacyStyleData`) [6, 31].
* **Fieldmap/FOV Mask Options (`LegacyStyleData` mode)**:
  * **`T1_fMRI_FOV`**: Combined T1w brain mask and fMRI field-of-view mask (default) [31].
  * **`T1_DILATED_fMRI_FOV`**: Once-dilated T1w brain mask combined with fMRI FOV [31].
  * **`T1_DILATED2x_fMRI_FOV`**: Twice-dilated T1w brain mask combined with fMRI FOV [31].
  * **`fMRI_FOV`**: fMRI FOV mask only [31].

---

### 5. fMRISurface Pipeline (`GenericfMRISurfaceProcessingPipeline.sh` / `hcp_fmri_surface`)

fMRISurface maps volume BOLD timeseries onto cortical surfaces, performs surface-constrained smoothing, subcortical volume processing, and outputs CIFTI dense timeseries (`.dtseries.nii`) [32, 33].

| Native Parameter | QuNex Equivalent | Description | Default |
| :--- | :--- | :--- | :--- |
| **`--lowresmesh`** | `hcp_lowresmesh` | Low-resolution surface mesh node resolution (in k) | **`32`** [34, 35] |
| **`--fmrires`** | `hcp_bold_res` | Spatial resolution of fMRI outputs in mm | **`2`** [34, 35] |
| **`--smoothingFWHM`** | `hcp_bold_smoothFWHM` | Surface spatial smoothing FWHM in mm | **`2`** [34, 35] |
| **`--grayordinatesres`** | `hcp_grayordinatesres` | Subcortical voxel size in grayordinates space in mm | **`2`** [34, 35] |
| **`--regname`** | `hcp_regname` | Surface registration technique (`MSMSulc` or `FS`) | **`MSMSulc`** [35, 36] |
| **`--printcom`** | `hcp_printcom` | Debug flag to print shell commands without executing | *(None)* [35] |
| **`--longitudinal-template`**| `hcp_longitudinal_template`| Target template ID for longitudinal processing | *(None)* [32, 35] |
| **`--is-longitudinal`** | `longitudinal` | Toggles longitudinal execution mode | *(None)* [32, 35] |

---

### 6. Diffusion Preprocessing Pipeline (`DiffPreprocPipeline.sh` / `hcp_diffusion`)

Diffusion Preprocessing handles intensity normalization, EPI distortion correction via TOPUP, eddy current and motion correction via `eddy`, and registration to native T1w space [37, 38].

* **`--sessionsfolder`**: Path to root study folder [3].
* **`--sessions`**: Comma-separated list of session IDs to process [3].
* **`--echospacing`**: EPI readout echo spacing in seconds (e.g. `0.00069` or `0.69` ms) [3].
* **`--pedir`**: Phase encoding direction axis (**`1`** for LR/RL, **`2`** for AP/PA) [3].
* **`--unwarpdir`**: Unwarping vector direction (**`x`**, **`x-`**, **`y`**, **`y-`**) [3].
* **`--hcp_dwi_selectbestb0`**: Flag selecting the single least-distorted $b=0$ image per phase encoding direction for TOPUP (instead of uniform temporal sampling) [39].
* **`--hcp_dwi_extraeddyarg`**: Pipe-separated string (`|`) of raw flags passed directly to `eddy` (e.g., `"--niter=8|--nvoxhp=2000"`) [39].
* **`--nogpu`**: Optional flag disabling GPU/CUDA binaries in favor of CPU execution [37, 40].

---

### 7. ICA-FIX Pipeline (`hcp_icafix` / `hcp_post_fix` / `hcp_reapply_fix`)

ICA-FIX runs MELODIC ICA decomposition, classifies noise components using trained weights, and regresses out motion/artifact components from BOLD data [41, 42].

* **`--hcp_icafix_bolds`**: Grouping specification string defining BOLD runs and concatenation groups (e.g. `"<group1>:<bold1>,<bold2>|<group2>:<bold3>,<bold4>"`) [43].
* **`--hcp_icafix_highpass`**: High-pass filter cutoff in seconds (**`0`** for multi-run concatenated FIX, **`2000`** for single-run FIX) [34, 44].
* **`--hcp_icafix_deleteintermediates`**: Deletes concatenated intermediate filtered and unfiltered timeseries files (**`TRUE`**/**`FALSE`**) [45].
* **`--hcp_icafix_regname`**: Surface registration name to use during CIFTI cleaning (default: **`MSMSulc`**) [45].
* **`--hcp_lowresmesh`**: Low-resolution surface mesh resolution (default: **`32`**k) [34, 45].
* **`--hcp_icafix_parallel_limit`**: Maximum number of concurrent local `melodic` threads during component extraction [46].
* **`--hcp_icafix_concatenate_only`**: Flag halting pipeline execution immediately after run concatenation [46].
* **`--hcp_reuse_existing_ica`**: Bypasses MELODIC re-computation and reuses pre-existing ICA decomposition results (**`TRUE`**/**`FALSE`**) [46].
* **`--hcp_autoreclean_model_folder`**: Directory path to custom RData FIX classifier models [34].

---

### 8. MSMAll Pipeline (`MSMAllPipeline.sh` / `hcp_msmall` / `hcp_dedrift_and_resample`)

MSMAll calculates multimodal cortical surface registration using resting-state fMRI functional connectivity, architecture (myelin maps), and topographic maps [42, 47].

| Native Parameter | QuNex Parameter | Description | Default / Values |
| :--- | :--- | :--- | :--- |
| **`--output-fmri-name`** | `hcp_msmall_outfmriname` | Output name for concatenated resting-state BOLD series | **`rfMRI_REST`** [44, 48, 49] |
| **`--high-pass`** | `hcp_icafix_highpass` | High-pass filter cutoff matching ICA-FIX run | **`0`** (multi-run) or **`2000`** [44, 48, 49] |
| **`--msm-all-templates`** | `hcp_msmall_templates` | Path to MSMAll group template directory | `$HCPPIPEDIR/global/templates/MSMAll` [48-50] |
| **`--output-registration-name`**| `hcp_msmall_outregname` | Output registration filename prefix | **`MSMAll_InitialReg`** [44, 48, 49] |
| **`--high-res-mesh`** | `hcp_hiresmesh` | High-resolution mesh vertex count in k | **`164`** [49, 51, 52] |
| **`--low-res-mesh`** | `hcp_lowresmesh` | Low-resolution mesh vertex count in k | **`32`** [49, 51, 52] |
| **`--input-registration-name`** | `hcp_regname` | Initial input registration sphere name | **`MSMSulc`** [49, 51, 52] |
| **`--matlab-run-mode`** | `hcp_matlab_mode` | MATLAB engine environment | **`compiled`**, **`interpreted`**, or **`octave`** [49, 52, 53] |
| **`--fmri-proc-string`** | `hcp_msmall_procstring` | Identification string for input FIX-cleaned timeseries | `<tail>_hp<highpass>_clean` [49, 52] |
| **`--myelin-target-file`** | `hcp_msmall_myelin_target` | Group reference myelin map scalar file | `Q1-Q6_RelatedParcellation210...32k_fs_LR.dscalar.nii` [49, 50, 54, 55] |
| **`--module-name`** | `hcp_msmall_module_name` | Underlying script execution module name | **`MSMAll.sh`** [55, 56] |
| **`--use-migp`** | `hcp_msmall_use_migp` | Toggles MIGP group component analysis | Enabled [56, 57] |
| **`--ica-dim`** | `hcp_msmall_ica_dim` | Target dimensionality for group sICA | **`40`** [56, 57] |
| **`--low-sica-dims`** | `hcp_msmall_low_sica_dims` | `@`-separated low sICA dimensions for individual weighting | `7@8@9@... @21` [56, 57] |
| **`--vn`** | `hcp_msmall_vn` | Enables variance normalization | Disabled by default [56, 57] |
| **`--registration-configure-path`**| `hcp_msmall_reg_conf_path`| Relative/absolute path to MSM configuration file | **`MSMAllStrainFinalconf1to1_1to3`** [56, 57] |
| **`--rsn-template-file`** | `hcp_msmall_rsn_template` | Path to alternate RSN template file | Relative to `--msm-all-templates` [56, 58] |
| **`--rsn-weights-file`** | `hcp_msmall_rsn_weights` | Path to alternate RSN weights file | Relative to `--msm-all-templates` [56, 58] |
| **`--topography-roi-file`** | `hcp_msmall_topography_roi`| Path to topography ROI scalar file | `Q1-Q6_RelatedParcellation210.atlas_Topographic_ROIs...` [56, 58] |
| **`--topography-target-file`**| `hcp_msmall_topography_target`| Path to topography target scalar file | `Q1-Q6_RelatedParcellation210.atlas_Topography...` [56, 58] |
| **`--use-ind-mean`** | `hcp_msmall_no_ind_mean` | Toggles individual vs group mean myelin map normalization | Flag disables individual mean [56, 58] |
| **`--start-frame`** | `hcp_msmall_start_frame` | Starting BOLD frame index (inclusive) | **`1`** [56, 59] |
| **`--end-frame`** | `hcp_msmall_end_frame` | Ending BOLD frame index (inclusive) | Last frame [56, 59] |
* **`--hcp_msmall_resample`**: Controls whether to automatically trigger `DeDriftAndResample` upon MSMAll completion (**`TRUE`**/**`FALSE`**) [47, 55].

---

*Note on Source Coverage:* The notebook sources detail the complete option structures for `PostFreeSurferPipeline.sh`, `FreeSurferPipeline.sh`, `FreeSurfer2CaretConvertAndRegisterNonlinear.sh`, and the full QuNex parameter interface wrappers (`hcp_*`) which expose all HCP pipeline options. Internal sub-script helper arguments for `PreFreeSurferPipeline.sh` and `fMRIVolumePipeline.sh` are documented primarily via these QuNex mapping interfaces.

🧠 Would you like me to generate a tailored reference document artifact or build a custom shell wrapper script for any of these specific pipelines?
