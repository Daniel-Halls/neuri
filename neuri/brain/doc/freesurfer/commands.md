### recon-all

* **Synopsis / Usage**: `recon-all -subjid <subject_id> -i <invol> [options]` [1-5]
* **Positional Arguments**: None (operates via required flags) [2, 5].
* **Flags & Options**:
  * **`-i <invol1.dcm|nii|mgz>`**: Specifies input T1-weighted anatomical volume [1-3, 6]. Can be specified multiple times for multiple input runs [2, 6].
  * **`-subjid <subject_id>`**: Defines the subject identifier and subject directory name [1-3, 5].
  * **`-sd <subjects_dir>`**: Sets the target subjects directory (defaults to `$SUBJECTS_DIR`) [3, 5].
  * **`-all`**: Runs the entire automated reconstruction pipeline [1, 3-5].
  * **`-autorecon1`**: Executes Stage 1 processing (motion correction, Talairach alignment, intensity normalization, and skull stripping) [2].
  * **`-autorecon2`**: Executes Stage 2 processing (GCA registration, CA normalization, CA registration, subcortical labeling, surface tessellation, topology fixing, white surface generation) [7].
  * **`-autorecon3`**: Executes Stage 3 processing (spherical mapping, surface registration, cortical parcellation, pial surface generation, ribbon masking, and stats extraction) [8-13].
  * **`-autorecon-hemi <lh|rh>`**: Executes reconstruction steps for a specified hemisphere [14].
  * **`-hemi <lh|rh>`**: Restricts processing to the specified hemisphere [14].
  * **`-T2 <invol>` / `-FLAIR <invol>`**: Converts and integrates an additional T2 or FLAIR image into the `orig` directory [2, 6].
  * **`-T2pial` (`-use_T2`)**: Uses a T2 image to refine the pial surface placement [10, 15].
  * **`-FLAIRpial` (`-use_FLAIR`)**: Uses a FLAIR image to refine the pial surface placement [15].
  * **`-3T`**: Enables parameter adjustments optimized for 3 Tesla MRI acquisitions [3, 4].
  * **`-parallel`**: Enables multi-CPU parallelization via OpenMP (defaults to 4 CPUs) [16, 17].
  * **`-openmp <n>`**: Sets the specific number of threads/CPUs for OpenMP parallel processing [17].
  * **`-cw256`**: Conforms the input volume to a 256³ field-of-view [14].
  * **`-mprage`**: Assumes scan parameters follow the MGH MP-RAGE protocol (adjusting for darker gray matter) [18].
  * **`-qcache`**: Produces pre-cached, resampled surface maps [5].
  * **`-base <baseid>`**: Specifies longitudinal template (base) processing mode [19].
  * **`-long <baseid>`**: Specifies longitudinal time-point processing mode referencing a base subject template [19].
  * **`-xopts-use` / `-xopts-clean` / `-xopts-overwrite`**: Manages usage, deletion, or overwriting of an existing expert options file [15].

---

### mri_convert

* **Synopsis / Usage**: `mri_convert [options] <involume> <outvolume>` [20-22]
* **Positional Arguments**:
  * `<involume>`: Input volume file path [21, 22].
  * `<outvolume>`: Output volume file path [21, 22].
* **Flags & Options**:
  * **`--in_type <type>` / `--out_type <type>`**: Explicitly sets input or output file format (e.g., `mgz`, `nifti1`, `nii`, `niigz`, `analyze`, `cor`, `mgh`, `dicom`) [20, 22-24].
  * **`-odt <uchar|short|int|float>` / `--out_data_type <type>`**: Specifies output voxel data type [21].
  * **`-rt <interpolate|weighted|nearest|cubic>` / `--resample_type <type>`**: Sets interpolation method during resampling (default: `interpolate`) [21, 25].
  * **`-nth <frame>`**: Extracts a specific 0-based frame number from a multi-frame volume [21].
  * **`--no_scale` (`-ns` / `--no_scale 1`)**: Disables value rescaling for COR/ANALYZE volumes [2, 21].
  * **`--conform`**: Resamples and embeds output volume to isotropic 1mm³ dimensions with 256³ grid size [2, 26, 27].
  * **`-upsample <N>`**: Reduces voxel size by a scaling factor of `N` in all dimensions [21].
  * **`-tr <TR>` / `-te <TE>` / `-TI <TI>`**: Manually sets TR, TE, or TI parameters in msec [21, 24].
  * **`-flip_angle <rad>`**: Specifies scan flip angle in radians [21].
  * **`--in_orientation <string>` / `--out_orientation <string>`**: Sets or converts volume orientation string (e.g., `RAS`, `LPI`) [21].
  * **`--sphinx`**: Adjusts image orientation metadata to sphinx position [21].
  * **`--autoalign <mtxfile>`**: Applies an auto-align transformation matrix from a text file [21].
  * **`-oval <val>`**: Sets specific voxel output value [21].
  * **`--outside_val <val>`**: Sets background value for voxels rotated into the field of view [21].
  * **`-is` / `--in_stats`**, **`-os` / `--out_stats`**: Prints volume intensity statistics for input or output volume [21].
  * **`-ii` / `--in_info`**, **`-oi` / `--out_info`**: Displays header metadata for input or output image [21].
  * **`-im` / `--in_matrix`**, **`-om` / `--out_matrix`**: Prints direction/voxel-to-RAS matrices [21].
  * **`-ro` / `--read_only`**, **`-nw` / `--no_write`**: Operates in read-only mode or suppresses writing output [21].
  * **`-nc` / `--nochange`**: Prevents changing the input data type to match template type [21].
  * **`--bfile-little-endian`**: Writes `bshort`/`bfloat` files using little-endian byte ordering [21].
  * **`--in_stats_table` / `--out_stats_table`**: Treats input/output data as a tabular stats file [21].

---

### mri_watershed

* **Synopsis / Usage**: `mri_watershed [options] <invol> <outvol>` [28-30]
* **Positional Arguments**:
  * `<invol>`: Input T1-weighted volume [28, 30].
  * `<outvol>`: Output skull-stripped brain volume [28, 30].
* **Flags & Options**:
  * **`-T1`**: Specifies input volume as T1-weighted (assuming T1 gray value ~ 110) [2, 28, 30].
  * **`-brain_atlas <atlas.gca> <xform.lta>`**: Uses atlas template and transform file to guide skull stripping [2, 30].
  * **`-w <weight>`**: Sets preweighting factor using atlas information [28, 30].
  * **`-no_wta`**: Disables preweighting for template deformation [28, 30].
  * **`-b <proba_merging>`**: Sets basin merging probability threshold (default: 0.32) [28, 30].
  * **`-h <int_hpf>`**: Specifies pre-flooding height percentage (default: 10) [28, 30].
  * **`-atlas`**: Applies atlas correction to repair cut-off brain regions or asymmetric boundaries [28, 31].
  * **`-surf <surfname>`**: Saves BEM surface estimates [28].
  * **`-useSRAS`**: Employs surface RAS coordinates (instead of scanner RAS) for generated surfaces [28].
  * **`-brainsurf <surfname>`**: Saves extracted brain surface mesh [28].
  * **`-shk_br_surf <int_h> <surfname>`**: Saves brain surface shrunk inward by `int_h` mm [28].
  * **`-less` / `-more`**: Shrinks or expands the skull-strip boundary surface [28].
  * **`-wat`**: Restricts processing strictly to the watershed algorithm [28].
  * **`-wat+temp`**: Executes watershed algorithm followed by first template smoothing [28].
  * **`-first_temp`**: Applies only first template smoothing and local matching [28].
  * **`-noT1`**: Skips T1 analysis pass to conserve memory [28].
  * **`-s <i j k>`**: Adds a custom seed point in voxel coordinates [28].
  * **`-c <i j k>`**: Defines explicit brain center in voxel coordinates [28].
  * **`-r <int_r>`**: Specifies approximate brain radius in voxels [28].
  * **`-t <int_threshold>`**: Adjusts watershed analysis process threshold [28].
  * **`-n`**: Bypasses the watershed analysis pass [28].
  * **`-LABEL`**: Generates tissue label volume (scalp, skull, CSF, gray, white matter) [28].
  * **`-man <csf_max trans_int GM_int>`**: Manually sets CSF max, transition intensity, and GM intensity thresholds [28].
  * **`-mask`**: Applies brain mask directly to input volume [28].
  * **`-copy`**: Copies input to output directly, bypassing skull stripping [28].
  * **`-surf_debug`**: Visualizes generated surfaces onto output volume [28].

---

### mri_segment

* **Synopsis / Usage**: `mri_segment [options] <input_volume> <output_volume>` [32-34]
* **Positional Arguments**:
  * `<input_volume>`: Normalized input T1 volume (WM ~ 110) [32, 33].
  * `<output_volume>`: Output white matter segmentation volume (e.g., `wm.seg.mgz`) [32, 34].
* **Flags & Options**:
  * **`-mprage`**: Adjusts parameters assuming MP-RAGE pulse sequence [7, 32].
  * **`-auto` / `-noauto`**: Automatically detects class intensity statistics (default: `-auto`) [32].
  * **`-keep`**: Preserves existing manual WM edits (retains values 0 and 255) [32].
  * **`-ghi` / `-gray_hi <val>`**: Sets gray matter high intensity limit (default: 100.0) [32].
  * **`-wlo` / `-wm_low <val>`**: Sets white matter low intensity limit (default: 90.0) [32].
  * **`-whi` / `-wm_hi <val>`**: Sets white matter high intensity limit (default: 125.0) [32].
  * **`-thicken` / `-nothicken`**: Toggles thickening pass for white matter segmentation (default: ON) [32].
  * **`-nseg <n>`**: Thickens the `n` largest thin strands (default: 20) [32].
  * **`-fillbg`**: Enables filling of basal ganglia (default: OFF) [32].
  * **`-fillv`**: Enables filling of ventricles (default: OFF) [32].
  * **`-b <sigma>`**: Sets Gaussian blur sigma (default: 0.25) [32].
  * **`-n <iters>`**: Sets number of border classification iterations (default: 1) [32].
  * **`-t <mm>`**: Sets thickness limit for thin strands in mm (default: 4) [32].
  * **`-p <pct>`**: Sets percentage classification threshold (default: 0.80) [32].
  * **`-w <wsize>`**: Sets local neighborhood window size (default: 11) [32].
  * **`-nold_remove`**: Prevents removal of 1D strands from segmentation [32].
  * **`-slope <val>` / `-pslope <val>` / `-nslope <val>`**: Sets curvature slope parameters (default: 1.0) [32].
  * **`-debug_voxel <x y z>`**: Enables diagnostic logging for a specific voxel [32].
  * **`-log`**: Writes execution log to `./segment.dat` [32].
  * **`-v`**: Enables verbose diagnostic output [32].

---

### mris_make_surfaces

* **Synopsis / Usage**: `mris_make_surfaces [options] <subject_id> <hemisphere>` [35-38]
* **Positional Arguments**:
  * `<subject_id>`: Subject directory name [36, 38].
  * `<hemisphere>`: Target hemisphere (`lh` or `rh` / `l` or `r`) [36, 38].
* **Flags & Options**:
  * **`-whiteonly`**: Generates white matter surface only [7, 36].
  * **`-nowhite`**: Skips white matter surface generation (used when creating pial surface) [9, 10].
  * **`-white <name>` / `-pial <name>`**: Customizes output white or pial surface filenames [36].
  * **`-orig_white <surf>`**: Specifies initial white surface file to start deformation [9, 36].
  * **`-orig_pial <surf>`**: Specifies initial pial surface file to start deformation [9, 10, 36].
  * **`-aseg <aseg_file>`**: Specifies subcortical segmentation volume (e.g., `aseg.presurf.mgz`) [7, 9, 36, 39].
  * **`-T1 <T1vol>`**: Specifies input T1/brain volume (e.g., `brain.finalsurfs.mgz`) [7, 9, 36, 38].
  * **`-T2 <T2vol>`**: Specifies T2 volume to refine pial surface boundaries [10, 36].
  * **`-c`**: Creates curvature (`?h.curv`) and area (`?h.area`) files from white matter surface [36].
  * **`-q`**: Omits self-intersection checks (speeds up gray/white surface generation) [36].
  * **`-a <n>`**: Averages curvature values `n` times (default: 10) [36].
  * **`-wa <n>`**: Averages white matter surface curvature `n` times (default: 4) [36].
  * **`-pa <n>`**: Averages pial surface curvature `n` times (default: 16) [36].
  * **`-max_gray_scale <mgs>`**: Sets intensity scaling threshold for white matter deformation [36].
  * **`-first_wm_peak`**: Anchors WM surface at first intensity profile peak rather than highest [36].
  * **`-dura_thresh <thresh>`**: Manually sets threshold for multi-echo MPRAGE dura avoidance [36].
  * **`-wm_weight <w>`**: Sets WM mean weight for T2 threshold calculation (default: 3) [36].
  * **`-nsigma_above <n>` / `-nsigma_below <n>`**: Sets sigmas above/below mean allowed for gray matter T2 intensities [10, 36].
  * **`-T2_min <thresh>` / `-T2_max <thresh>`**: Sets min/max T2 intensity bounds inside cortical ribbon [36].
  * **`-min_peak_pct <inside_pct> <outside_pct>`**: Sets percentage of GM histogram peak for local GM thresholds [36].
  * **`-noaparc`**: Disables reading aparc annotation during surface creation [7, 39].
  * **`-mgz`**: Specifies volume inputs are in MGZ format [7, 9, 36].
  * **`-SDIR <dir>`**: Overrides `SUBJECTS_DIR` [36].
  * **`-long`**: Enables longitudinal surface deformation mode [36].

---

### mri_normalize

* **Synopsis / Usage**: `mri_normalize [options] <invol> <outvol>` [2, 7, 27, 40]
* **Positional Arguments**:
  * `<invol>`: Input volume (e.g., `nu.mgz`) [2, 7, 40].
  * `<outvol>`: Output normalized volume (e.g., `T1.mgz` or `norm.mgz`) [2, 7, 40].
* **Flags & Options**:
  * **`-g <gradient>`**: Sets max intensity/mm gradient threshold (default: 1.000) [2, 27, 40].
  * **`-mprage`**: Enables MP-RAGE intensity normalization settings [2, 7, 27].
  * **`-aseg <aseg_file>`**: Employs subcortical segmentation to guide normalization [7, 27].
  * **`-mask <maskfile>`**: Restricts normalization within a brain mask volume [7, 27].
  * **`-c <ctrl_pts.mgz>`**: Reads control points from volume file [7, 26].
  * **`-f <file>`**: Reads control points from text file (e.g., `control.dat`) [27].
  * **`-fonly`**: Restricts normalization strictly to control points file [27].
  * **`-label` / `-lonly`**: Uses control points from label file (or exclusively from label file) [27].
  * **`-a <val>`**: Sets control point target upper threshold above target (default: 25.0) [27].
  * **`-b <val>`**: Sets control point target lower threshold below target (default: 10.0) [27].
  * **`-n <iters>`**: Sets number of 3D normalization iterations (default: 2) [27].
  * **`-no1d`**: Disables 1D normalization pass [27].
  * **`-nonmax_suppress <0|1>`**: Toggles non-maximum suppression on surface interiors [27].
  * **`-conform`**: Interpolates and conforms output volume to 256³ grid size [27].
  * **`-gentle`**: Executes a milder normalization adjustment [27].
  * **`-prune`**: Toggles control point pruning (prevents WM expansion into GM) [27].
  * **`-atlas`**: Excludes control points located in non-brain regions via atlas [27].
  * **`-noskull`**: Ignores non-brain/skull voxels during normalization [27].
  * **`-monkey`**: Disables 1D normalization and sets 3D iterations to 1 [27].
  * **`-nosnr`**: Disables SNR-based normalization [27].
  * **`-sigma <sigma>`**: Applies Gaussian smoothing to estimated bias field [27].
  * **`-renorm <volume>`**: Loads volume and treats all voxels equal to 110 as control points [27].
  * **`-checknorm <volume> <min> <max>`**: Filters out control points outside intensity range `[min, max]` [27].
  * **`-surface`**: Normalizes based on interior skeleton of transformed surface [27].
  * **`-w <ctrl_vol> <bias_vol>`**: Writes output control point volume and bias field volume [27].

---

### mri_mask

* **Synopsis / Usage**: `mri_mask [options] <in_vol> <mask_vol> <out_vol>` [7, 41]
* **Positional Arguments**:
  * `<in_vol>`: Input volume [41].
  * `<mask_vol>`: Mask volume (typically skull-stripped) [41].
  * `<out_vol>`: Output masked volume [7, 41].
* **Flags & Options**:
  * **`-T <thresh>`**: Thresholds mask volume at `#` (values ≤ `thresh` are zeroed out, e.g., `-T 5`) [7, 41].
  * **`-xform <xform.lta>`**: Applies LTA transform to align mask volume to input volume space [41].
  * **`-invert`**: Reversely applies the `-xform` matrix [41].
  * **`lta_src <vol>` / `lta_dst <vol>`**: Overrides source or target volume metadata for `-xform` [41].
  * **`-bb <npad>`**: Extracts bounding box around mask expanded by `npad` voxels [41].
  * **`-abs`**: Computes `abs()` of mask values before thresholding [41].
  * **`-transfer <val>`**: Transfers strictly voxel value `#` from mask to output image [41].
  * **`-keep_mask_deletion_edits`**: Transfers manual voxel-deletion edits (`voxels=1`) from mask to output [41].

---

### mri_ca_label

* **Synopsis / Usage**: `mri_ca_label [options] <invol1> [invol2 ...] <xform> <gcafile> <outvol>` [7, 42, 43]
* **Positional Arguments**:
  * `<invol1> [invol2 ...]`: Input normalized volume(s) [42].
  * `<xform>`: Transform file (e.g., `talairach.m3z` or `.lta`) [7, 42].
  * `<gcafile>`: Gaussian Classifier Atlas file [7, 42].
  * `<outvol>`: Output segmented volume (e.g., `aseg.auto_noCCseg.mgz`) [7, 42].
* **Flags & Options**:
  * **`-relabel_unlikely <std_devs> <window_size>` (`-RELABEL_UNLIKELY <1|0>`)**: Reclassifies voxels exceeding standard deviation threshold using Gaussian window [7, 26].
  * **`-prior <thresh>`**: Sets prior probability threshold (default: 0.5) [7, 26].
  * **`-align`**: Aligns input volume to GCA atlas space [7, 26].
  * **`-cross-sequence`**: Labels volume acquired with sequence differing from atlas training [26].
  * **`-nogibbs`**: Disables Gibbs priors during labeling [26].
  * **`-wm <path>`**: Supplies explicit white matter segmentation file [26].
  * **`-conform`**: Interpolates output volume to isotropic 1mm³ [26].
  * **`-topo_dist_thresh <dist>` / `-topo_volume_thresh1 <v1>` / `-topo_volume_thresh2 <v2>`**: Sets topological distance and volume thresholds for disconnected ventricle filtering [26].
  * **`-t1 <gca_t1>`**: Employs T1 GCA file for thin temporal lobe labeling [26].
  * **`-normpd`**: Normalizes Proton Density image to GCA means [26].
  * **`-tr <TR>` / `-te <TE>` / `-alpha <ALPHA>`**: Specifies scan TR (ms), TE (ms), and alpha (rad) [26].
  * **`-pthresh <thresh>`**: Sets probability threshold for adaptive renormalization (default: 0.7) [26].
  * **`-niter <n>` / `-n <n>`**: Sets maximum likelihood / Gibbs iterations (default: 200) [26].
  * **`-novar`**: Disables variance in classification [26].
  * **`-regularize <reg>`**: Regularizes variance (`sigma + nC(noise)`) [26].
  * **`-nohippo`**: Disables automatic editing of hippocampus [26].
  * **`-fwm <mri_vol>`**: Uses fixed white matter segmentation volume [26].
  * **`-mri <mri_vol>`**: Writes most likely MR volume to file [26].
  * **`-heq <mri_vol>`**: Applies histogram equalization from reference volume [26].
  * **`-renorm <mri_vol>` / `-renormalize <wsize> <iter>`**: Renormalizes class means using predicted intensity values [26].
  * **`-flash` / `-flash_params <filename>`**: Uses FLASH forward model/tissue parameters to predict intensities [26].
  * **`-m <mri_vol>`**: Masks final labeling using specified volume [26].
  * **`-f <mode_filter_iters> <thresh>`**: Applies mode filter `f` times with threshold `thresh` [26].
  * **`-nowmsa`**: Disables WMSA labels (hypo/hyper-intensities) [26].
  * **`-write_probs <filename>`**: Writes label probabilities to text file [26].
  * **`-L <mri_vol>`**: Specifies longitudinal mode using label from timepoint 1 [26].

---

### mri_ca_register

* **Synopsis / Usage**: `mri_ca_register [options] <norm.mgz> <gcafile> <out_m3z>` [7, 44, 45]
* **Positional Arguments**:
  * `<norm.mgz>`: Normalized input volume [7, 44, 45].
  * `<gcafile>`: Gaussian Classifier Atlas file [7, 44, 45].
  * `<out_m3z>`: Output non-linear transform file (e.g., `talairach.m3z`) [7, 44, 45].
* **Flags & Options**:
  * **`-align-after`**: Executes alignment after setup [7].
  * **`-nobigventricles`**: Disables big ventricle expansion handling [7, 46].
  * **`-mask <brainmask.mgz>`**: Specifies volume to use as spatial registration mask [7, 44, 46].
  * **`-T <talairach.lta>`**: Input linear transform file in LTA format [7, 44].
  * **`-tol <val>`**: Defines convergence tolerance for registration [44, 47].
  * **`-levels <n>`**: Defines number of surround voxels / multi-resolution levels (default: 6) [44, 46].
  * **`-ri`**: Reads multiple intensity normalization inputs [44].

---

### mri_ca_normalize

* **Synopsis / Usage**: `mri_ca_normalize [options] <inbrain1> [inbrain2] <atlas.gca> <xform.lta> <outvol>` [7, 48, 49]
* **Positional Arguments**:
  * `<inbrain1> [inbrain2]`: Input brain and/or intensity volume(s) (e.g., `nu.mgz`) [7, 48].
  * `<atlas.gca>`: GCA atlas file [7, 48, 49].
  * `<xform.lta>`: Input transform file (`talairach.lta`) [7, 48, 49].
  * `<outvol>`: Output normalized volume (`norm.mgz`) [7, 48, 49].
* **Flags & Options**:
  * **`-c <ctrl_pts.mgz>`**: Specifies control points volume file [7].
  * **`-mask <brainmask.mgz>`**: Specifies volume to use as brain mask [7, 50].
  * **`-p <pct>`**: Sets percentage of likely white matter to use as control points (default: 0.50 / 50%) [50].

---

### mris_ca_label

* **Synopsis / Usage**: `mris_ca_label [options] <subject_id> <hemi> <canonsurf> <classifier> <outputfile>` [9, 11, 51-54]
* **Positional Arguments**:
  * `<subject_id>`: Subject identifier [52, 54].
  * `<hemi>`: Hemisphere (`lh` or `rh`) [52, 54].
  * `<canonsurf>`: Canonical registered spherical surface (e.g., `sphere.reg`) [9, 11, 52, 54].
  * `<classifier>`: Classifier array input file (`.gcs` atlas) [9, 11, 52, 54].
  * `<outputfile>`: Output annotated surface file (`?h.aparc.annot`) [9, 11, 52, 54].
* **Flags & Options**:
  * **`-l <cortex.label>`**: Restricts parcellation within specified cortex label boundary [9, 11].
  * **`-aseg <aseg.presurf.mgz>`**: Incorporates subcortical segmentation volume to constrain parcellation [9, 11].
  * **`-sdir <subjects_dir>`**: Sets subjects directory (default: `$SUBJECTS_DIR`) [53].
  * **`-orig <filename>`**: Specifies original surface filename (default: `smoothwm`) [53].
  * **`-long`**: Refines initial labeling read from `-r` in longitudinal pipeline mode [53].
  * **`-r <precomputed.annot>`**: Reads precomputed parcellation annotation file [53].
  * **`-novar`**: Sets covariance matrices to identity [53].
  * **`-nbrs <size>`**: Defines neighborhood size (default: 2) [53].
  * **`-f <iters>`**: Applies mode filter `iters` times prior to writing output (default: 10) [53].
  * **`-t <table_file>`**: Specifies input parcellation color table file [53].
  * **`-p <prob_file>`**: Outputs vertex-wise label probability file [53].
  * **`-v <level>`**: Sets diagnostic logging verbosity (default: 0) [53].
  * **`-w <iters> <filename>`**: Saves Gibbs process snapshots every `iters` iterations [53].
  * **`-seed <n>`**: Sets random number generator seed [55].

---

### mris_smooth

* **Synopsis / Usage**: `mris_smooth [options] <input_surface> <output_surface>` [7, 56]
* **Positional Arguments**:
  * `<input_surface>`: Input surface file (e.g., `?h.orig.nofix` or `?h.white`) [7, 56].
  * `<output_surface>`: Output smoothed surface file (e.g., `?h.smoothwm.nofix` or `?h.smoothwm`) [7, 56].
* **Flags & Options**:
  * **`-nw`**: Disables writing out curvature (`.curv`) and area (`.area`) files [7].
  * **`-n <iters>`**: Sets number of smoothing iterations (default: 10) [7, 56].
  * **`-a <iters>`**: Sets number of curvature averaging iterations (default: 10) [56].

---

### mris_inflate

* **Synopsis / Usage**: `mris_inflate [options] <insurfacefile> <outsurfacefile>` [7, 57, 58]
* **Positional Arguments**:
  * `<insurfacefile>`: Input surface file (e.g., `?h.smoothwm`) [7, 57, 58].
  * `<outsurfacefile>`: Output inflated surface file (e.g., `?h.inflated`) [7, 57, 58].
* **Flags & Options**:
  * **`-no-save-sulc`**: Suppresses saving sulcal morphometry (`?h.sulc`) file during inflation [7, 58].
  * **`-n <iterations>`**: Sets maximum number of inflation iterations (default: 55) [59].
  * **`-w <n>`**: Saves inflation snapshot every `n` iteration steps [59].
  * **`-dist <distcoeff>`**: Sets metric distortion/smoothness tradeoff factor (default: 0.1) [59].

---

### mris_sphere

* **Synopsis / Usage**: `mris_sphere [options] <insurfacefile> <outsurfacefile>` [7, 8, 60, 61]
* **Positional Arguments**:
  * `<insurfacefile>`: Input inflated surface file (e.g., `?h.inflated`) [7, 8, 60, 61].
  * `<outsurfacefile>`: Output spherical surface file (e.g., `?h.qsphere.nofix` or `?h.sphere`) [7, 8, 60, 61].
* **Flags & Options**:
  * **`-q`**: Enables quick spherical inflation / spectral projection mode (`qsphere`) [7].

---

### mris_register

* **Synopsis / Usage**: `mris_register [options] <surf_fname> <target_fname> <out_fname>` [8, 62-64]
* **Positional Arguments**:
  * `<surf_fname>`: Input subject spherical surface (e.g., `?h.sphere`) [8, 63, 64].
  * `<target_fname>`: Target average surface template atlas (e.g., `?h.average.curvature.filled.buckner40.tif`) [8, 63, 64].
  * `<out_fname>`: Output registered spherical surface file (e.g., `?h.sphere.reg`) [8, 63, 64].
* **Flags & Options**:
  * **`-curv`**: Uses `smoothwm` curvature for final alignment stage [8, 64, 65].
  * **`-nocurv`**: Disables `smoothwm` curvature during final alignment stage [65].
  * **`-nosulc`**: Disables initial sulcal alignment [65].
  * **`-norot`**: Disables initial rigid body alignment [65].
  * **`-1`**: Treats target argument as a single subject's surface file rather than an atlas template [63, 65].
  * **`-annot <annot_name>`**: Zeroes out medial wall vertices using specified annotation file [65].
  * **`-sreg <starting_reg_fname>`**: Initializes registration using coordinates from specified registration file [65].
  * **`-jacobian <jacobian_fname>`**: Writes mapping Jacobian values to output file [65].
  * **`-dt <dt>`**: Sets momentum integration step size [65].
  * **`-M <momentum>`**: Selects momentum integration type and sets momentum value [65].
  * **`-nbrs <nbrs>`**: Sets neighborhood size [65].
  * **`-N <niterations>`**: Sets number of registration iterations [65].
  * **`-P <max_passes>`**: Limits surface unfolding to specified maximum passes [65].
  * **`-adaptive`**: Enables adaptive time-step numerical integration [65].
  * **`-median`**: Uses median normalization instead of mean [65].
  * **`-multi_scale <scales>`**: Sets number of multi-scale resolution levels [65].
  * **`-rotate <dalpha dbeta dgamma>`**: Rotates brain mesh by specified angles [65].
  * **`-reverse`**: Applies mirror-image reversal prior to morphing [65].
  * **`-topology`**: Enforces topology preservation of positive-area triangles [65].
  * **`-remove_negative <0|1>`**: Enables iterative smoothing to eliminate negative-area triangles [65].
  * **`-overlay <overlay_file> <navgs>`**: Incorporates overlay variable into atlas with `navgs` smoothing passes [65].
  * **`-overlay-dir <overlay_dir>`**: Changes default overlay directory path [65].
  * **`-C <curvature_fname>`**: Supplies custom curvature input file [65].
  * **`-canon <canon_name>`**: Employs surface for canonical properties [65].
  * **`-inflated` / `-infname <name>`**: Uses specified inflated surface for initial alignment [65].
  * **`-O <orig_name>`**: Sets surface for original properties [65].
  * **`-L`**: Incorporates manual label alignment to atlas label [65].

---

### mri_robust_template

* **Synopsis / Usage**: `mri_robust_template --mov <tp1.mgz> <tp2.mgz> ... --template <template.mgz> [options]` [2, 66-68]
* **Required Flagged Arguments**:
  * **`--mov <tp1.mgz> <tp2.mgz> ...`**: Input movable volume files to align to common template [2, 67-69].
  * **`--template <template.mgz>`**: Output template volume (final average image) [2, 67, 68].
  * **`--satit`**: Automatically detects outlier sensitivity (recommended for head/brain scans) [2, 67-69].
  * **`--sat <val>`**: Manually sets outlier sensitivity threshold (higher = less sensitive, e.g., `--sat 4.685`) [67].
* **Optional Flagged Arguments**:
  * **`--lta <tp1.lta> <tp2.lta> ...`**: Output LTA transformation matrices mapping inputs to template [2, 68, 70].
  * **`--mapmov <aligned1.mgz> ...`**: Output resampled images mapped into template space [70].
  * **`--weights <weights1.mgz> ...`**: Output outlier weight maps in target space [70].
  * **`--average <0|1>`**: Sets averaging method: `0` Mean, `1` Median (default: 1) [2, 68, 70].
  * **`--inittp <#>`**: Selects time point index for spatial initialization (`0`: no init) [2, 68, 70].
  * **`--fixtp`**: Maps all inputs to initial time point without resampling the target [2, 68, 70].
  * **`--iscale`**: Enables intensity scaling across time points [2, 70].
  * **`--iscalein <is1.txt> ...`**: Inputs initial intensity scaling values [70].
  * **`--iscaleout <is1.txt> ...`**: Writes output intensity scale factors (activates `--iscale`) [2, 68, 70].
  * **`--ixforms <t1.lta> ...`**: Specifies initial LTA transforms on source volumes (`id` = identity) [70].
  * **`--vox2vox`**: Outputs VOX2VOX LTA files (default: RAS2RAS) [70].
  * **`--affine`**: Computes 12 DOF affine registration (default: 6 DOF rigid body) [70].
  * **`--leastsquares`**: Employs least squares optimization instead of robust M-estimator [70].
  * **`--noit`**: Disables iteration, outputting initial template directly [2, 68, 70].
  * **`--maxit <#>`**: Sets maximum iterations (default: 6 for >2 time points, 5 for 2 time points) [70].
  * **`--highit <#>`**: Sets max iterations on highest resolution level (default: 5) [70].
  * **`--epsit <eps>`**: Sets convergence update threshold (default: 0.03 for >2 TPs, 0.01 for 2 TPs) [70].
  * **`--subsample <#>`**: Subsamples image grid if dimensions exceed `#` voxels (e.g., `--subsample 200`) [2, 68, 70].
  * **`--floattype`**: Converts images to single-precision float internally [70].
  * **`--finalnearest`**: Uses nearest-neighbor interpolation when constructing final average [70].
  * **`--doubleprec`**: Uses double-precision floating point arithmetic internally [70].
  * **`--debug`**: Enables verbose diagnostic logging [70].

---

### talairach_avi

* **Synopsis / Usage**: `talairach_avi --i <invol> --xfm <out_xfm> [options]` [2, 71]
* **Mandatory Flags**:
  * **`--i <invol>`**: Input anatomical volume (e.g., `orig_nu.mgz`) [2, 71].
  * **`--xfm <out_xfm>`**: Output Talairach transform file path (e.g., `transforms/talairach.auto.xfm`) [2, 71].
* **Optional Flags**:
  * **`--fslregout <file>`**: Computes and writes an FSL-compatible registration matrix file [72].
  * **`--atlas <atlas_file>`**: Specifies target template volume (defaults to MNI `average_305`) [71].
