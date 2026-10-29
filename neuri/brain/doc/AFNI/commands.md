# AFNI Command-Line Flag, Option, and Parameter Reference Manual

Below is the complete reference list of command-line flags, options, and parameters for the specified AFNI commands as documented in the sources.

---

## 1. `afni_proc.py`
`afni_proc.py` generates C-shell processing scripts for single-subject fMRI preprocessing and statistical analysis [1, 2].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-subj_id`** | `<subject_id>` | Subject identifier string used in output file prefixing [1, 3, 4]. |
| **`-script`** | `<script_name>` | Names the output C-shell script file created by `afni_proc.py` [1, 5]. |
| **`-out_dir`** | `<directory>` | Specifies the output results directory for script execution [1, 5, 6]. |
| **`-scr_overwrite`** | *None* | Overwrites any existing output script file with the same name [1, 5, 6]. |
| **`-blocks`** | `<block_1 block_2 ...>` | Defines the ordered processing block sequence (e.g., `despike`, `tshift`, `ricor`, `blip`, `align`, `tlrc`, `volreg`, `blur`, `mask`, `combine`, `scale`, `regress`) [1, 3-7]. |
| **`-radial_correlate_blocks`** | `<block_1 ...>` | Generates radial correlation diagnostic volumes for specified blocks (e.g., `tcat`, `volreg`, `regress`) [3-5]. |
| **`-copy_anat`** | `<dataset>` | Copies the anatomical reference dataset into the results directory [1, 3-7]. |
| **`-anat_has_skull`** | `<yes \| no>` | Specifies whether the anatomical volume contains skull (`yes`) or is skull-stripped (`no`) [3, 4, 6, 7]. |
| **`-anat_uniform_method`** | `<unifize \| none>` | Sets spatial intensity uniformization method (calls `3dUnifize`) [1, 3]. |
| **`-anat_follower`** | `<label> <space> <dset>` | Maps auxiliary anatomical volumes through spatial alignment transformations [4]. |
| **`-anat_follower_ROI`** | `<label> <space> <dset>` | Maps ROI masks through anatomical or EPI transformations [4, 7]. |
| **`-dsets`** | `<dset1 dset2 ...>` | Inputs single-echo EPI functional datasets (accepts multi-run lists) [1, 4-6]. |
| **`-dsets_me_echo`** | `<e1_files> <e2_files> ...` | Inputs multi-echo EPI dataset series (invoked once per echo) [3]. |
| **`-echo_times`** | `<t1 t2 t3 ...>` | Echo times in milliseconds for multi-echo processing [3]. |
| **`-reg_echo`** | `<echo_index>` | 1-based index specifying which echo volume is used for motion registration [3]. |
| **`-combine_method`** | `<OC \| ...>` | Multi-echo combination method (e.g., `OC` for Optimal Combination) [3]. |
| **`-tcat_remove_first_trs`** | `<num_TRs>` | Drops initial `N` time points per run for T1 equilibration [1, 3-6, 8]. |
| **`-blip_forward_dset`** | `<dataset>` | Specifies forward phase-encoded EPI dataset for distortion correction [9]. |
| **`-blip_reverse_dset`** | `<dataset>` | Specifies reverse phase-encoded EPI dataset for distortion correction [9]. |
| **`-ricor_regs`** | `<1D_file>` | Inputs physiological time series regressors for RETROICOR processing [9]. |
| **`-ricor_regs_nfirst`** | `<num_TRs>` | Specifies initial physiological time points to remove matching EPI TR removal [9]. |
| **`-align_opts_aea`** | `<options>` | Passes option flags directly to `align_epi_anat.py` (e.g., `-cost lpc+ZZ`, `-ginormous_move`, `-giant_move`, `-check_flip`, `-AddEdge`) [1, 3-7]. |
| **`-align_epi_strip_method`** | `<3dSkullStrip \| ...>` | Selects skull-stripping algorithm used during EPI-anatomical alignment [3]. |
| **`-Allineate_opts`** | `'<options>'` | Passes custom flag strings directly to internal `3dAllineate` calls [3]. |
| **`-source_automask`** | *None* | Generates an automask on the source EPI volume during alignment [3]. |
| **`-tlrc_base`** | `<template>` | Standard space template volume (e.g., `MNI152_2009_template_SSW.nii.gz`) [1, 3-6, 8]. |
| **`-tlrc_NL_warp`** | *None* | Enables non-linear spatial warping to standard space (`3dQwarp` or `@SSwarper`) [3-6]. |
| **`-tlrc_NL_warped_dsets`** | `<anatQQ> <aff12.1D> <WARP>` | Supplies pre-computed `@SSwarper` outputs (`anatQQ.nii`, `aff12.1D`, `WARP.nii`) [3, 4, 6]. |
| **`-volreg_warp_dxyz`** | `<size_mm>` | Sets isotropic voxel resolution in millimeters for output standard space volumes [1, 6]. |
| **`-volreg_align_to`** | `<MIN_OUTLIER \| first \| third>` | Chooses reference target volume for motion correction registration [1, 3-6, 8]. |
| **`-volreg_align_e2a`** | *None* | Performs EPI-to-anatomical alignment during volume registration [1, 3, 4, 6]. |
| **`-volreg_tlrc_warp`** | *None* | Concatenates motion correction, EPI-to-anat, and TLRC transformations into one interpolation step [1, 3-6]. |
| **`-volreg_compute_tsnr`** | `<yes \| no>` | Computes temporal signal-to-noise ratio (tSNR) dataset maps [3, 4]. |
| **`-blur_size`** | `<fwhm_mm>` | Sets spatial Gaussian blurring filter width in mm FWHM [1, 3-7]. |
| **`-blur_to_fwhm`** | *None* | Blurs dataset iteratively until an absolute target FWHM is reached [5]. |
| **`-mask_epi_anat`** | `<yes \| no>` | Intersects anatomical and EPI masks to restrict functional analysis [3-5]. |
| **`-regress_stim_times`** | `<f1 f2 ...>` | Inputs stimulus onset timing text files (in seconds) [1, 3-6, 8]. |
| **`-regress_stim_labels`** | `<l1 l2 ...>` | Assigns labels to each input stimulus timing class [1, 3-6, 8]. |
| **`-regress_stim_types`** | `<times \| AM1 \| AM2>` | Defines stimulus regressor types (timing vs amplitude modulation) [1, 6, 8]. |
| **`-regress_basis`** | `'<basis_function>'` | Sets Hemodynamic Response Function (HRF) model (e.g., `'BLOCK(20,1)'`, `'GAM'`) [4, 5, 8]. |
| **`-regress_basis_multi`** | `'<b1>' '<b2>' ...` | Assigns distinct basis functions per stimulus class [1, 6]. |
| **`-regress_local_times`** | *None* | Interprets stimulus onset times as relative to run start rather than global time [5]. |
| **`-regress_censor_motion`** | `<limit_mm>` | Censors TRs where Euclidean norm (`enorm`) motion derivative exceeds threshold [1, 4-6, 8]. |
| **`-regress_censor_outliers`** | `<limit_frac>` | Censors TRs where outlier voxel fraction exceeds limit (e.g., `0.05` or `0.1`) [4, 5, 8]. |
| **`-regress_motion_per_run`** | *None* | Fits separate 6-degree motion parameter regressors for each functional run [3-6, 8]. |
| **`-regress_opts_3dD`** | `<options>` | Passes custom flags directly to `3dDeconvolve` (e.g., `-gltsym`, `-glt_label`, `-jobs`, `-bout`, `-GOFORIT 99`) [1, 3-6, 8]. |
| **`-regress_make_ideal_sum`** | `<filename.1D>` | Writes sum of all ideal un-censored stimulus regressors to a 1D file [1, 4-6]. |
| **`-regress_3dD_stop`** | *None* | Runs `3dDeconvolve` with `-x1D_stop` to build matrices without voxelwise estimation [6]. |
| **`-regress_reml_exec`** | *None* | Executes `3dREMLfit` for Generalized Least Squares with ARMA(1,1) temporal autocorrelation [5, 6, 8]. |
| **`-regress_opts_reml`** | `<options>` | Passes custom flags directly to `3dREMLfit` [5]. |
| **`-regress_est_blur_epits`** | *None* | Estimates spatial smoothness on EPI time series datasets [1, 3-6]. |
| **`-regress_est_blur_errts`** | *None* | Estimates spatial smoothness on residual error time series (`errts`) [1, 3-6]. |
| **`-regress_run_clustsim`** | `<yes \| no>` | Computes cluster-size thresholding tables via `3dClustSim` [3, 4, 8]. |
| **`-regress_compute_fitts`** | *None* | Generates full model fitted time series dataset (`fitts`) [4, 5, 8]. |
| **`-html_review_style`** | `<pythonic \| ...>` | Selects APQC quality control HTML report layout [3, 4]. |
| **`-execute`** | *None* | Immediately executes the generated C-shell script upon creation [1, 3, 4, 6]. |

---

## 2. `@SSwarper`
`@SSwarper` performs dual-pass anatomical skull-stripping and non-linear registration of T1-weighted structural images to a standard space template [3, 10].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-input`** | `<dset>` | Inputs T1-weighted anatomical dataset [3, 10, 11]. |
| **`-base`** | `<template>` | Specifies target standard space template volume (e.g., `MNI152_2009_template_SSW.nii.gz`) [3, 10, 11]. |
| **`-subid`** | `<subject_id>` | Subject identifier string used in output file prefixing [3, 12]. |
| **`-odir`** | `<output_dir>` | Directory where script outputs and working files are written [3, 12]. |
| **`-mask_apply`** | `<MA>` | Applies a fixed pre-existing mask without further refinement [11]. |
| **`-minp`** | `<patch_size>` | Minimum patch size parameter passed to `3dQwarp` (default: `11`) [11]. |
| **`-nolite`** | *None* | Disables the `-lite` speedup flag in internal `3dQwarp` calls [11, 13]. |
| **`-skipwarp`** | *None* | Skips non-linear alignment computation (used for affine alignment troubleshooting) [14]. |
| **`-deoblique`** | *None* | Deobliques input volume via `3dWarp -deoblique -wsinc5` prior to alignment [14]. |
| **`-deoblique_refitly`** | *None* | Purges obliquity header information via `3drefit -deoblique` before alignment [15]. |
| **`-warpscale`** | `<WS>` | Controls non-linear warp flexibility in `3dQwarp` (range `0.1`–`1.0`, default: `1.0`) [15]. |
| **`-post_aff_tol`** | `<PAT>` | Boundary tolerance in voxels between affine-aligned subject and template (default: `3`) [15]. |
| **`-cost_aff`** | `<CA>` | Specifies cost function for affine alignment via `3dAllineate` (default: `lpa+ZZ`) [16]. |
| **`-cost_nl_init`** | `<CNI>` | Specifies cost function for initial non-linear alignment via `3dQwarp` (default: `lpa`) [16]. |
| **`-cost_nl_final`** | `<CNF>` | Specifies cost function for final non-linear alignment via `3dQwarp` (default: `pcl`) [16]. |
| **`-penfac`** | `<PF>` | Weight factor for grid distortion penalty in final rounds of `3dQwarp` [17]. |
| **`-tmp_name_rand`** | *None* | Generates randomly named intermediate working files (`junk.SSwarper_[rand]`) [17]. |
| **`-echo`** | *None* | Enables verbose terminal shell command echoing (`set echo`) [18]. |
| **`-verb`** | *None* | Enables verbose output tracing in internal `3dQwarp` execution [18]. |
| **`-noclean`** | *None* | Retains intermediate working files in output directory upon completion [18]. |

---

## 3. `3dvolreg`
`3dvolreg` aligns sub-bricks of 3D+time datasets to a base volume using rigid-body (6-parameter) spatial registration [19].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-input`** | `<dataset>` | Inputs 3D+time dataset for volume registration [19]. |
| **`-base`** | `<dset \| index>` | Base volume for registration (sub-brick index or dataset volume string) [19]. |
| **`-prefix`** | `<fname>` | Output dataset prefix (`NULL` suppresses output dataset writing) [20]. |
| **`-verbose`** | *None* | Prints progress reports (repeat `-verbose -verbose` for detailed iteration logs) [20]. |
| **`-Fourier` / `-heptic` / `-quintic` / `-cubic` / `-linear`** | *None* | Selects spatial interpolation method for parameter estimation and resampling (default: `-heptic`) [20]. |
| **`-clipit` / `-noclip`** | *None* | Constrains resampled voxel values to input dataset range (default: `-clipit`) [20]. |
| **`-zpad`** | `<n>` | Adds `n` planes of zero padding around all 6 dataset boundaries during rotation (default: `4`) [20]. |
| **`-twopass`** | *None* | Two-pass parameter estimation (coarse blurred pass followed by fine pass) [21]. |
| **`-1Dfile`** | `<fname.1D>` | Saves 6 rigid-body motion parameters (roll, pitch, yaw, dS, dL, dP) to a text file [19, 21]. |
| **`-1Dmatrix_save`** | `<fname.1D>` | Writes 3x4 transformation matrices for each sub-brick into a text file [22]. |
| **`-maxdisp1D`** | `<fname.1D>` | Writes maximum spatial displacement (mm) per sub-brick to a 1D file [19]. |
| **`-rotparent`** | `<rset>` | Applies additional rotation/translation transformation extracted from master dataset `rset` [19, 23]. |
| **`-gridparent`** | `<gset>` | Modifies spatial grid and slice padding of output dataset to match `gset` [19, 24]. |
| **`-maxite`** | `<m>` | Sets maximum iteration count for convergence (default: `23`) [19, 21]. |
| **`-x_thresh`** | `<x>` | Translation convergence threshold in voxels (default: `0.01`) [19]. |
| **`-rot_thresh`** | `<r>` | Rotation convergence threshold in degrees (default: `0.02`) [19]. |
| **`-delta`** | `<d>` | Voxel-size step delta used for finite-difference spatial derivatives (default: `0.70`) [19, 21]. |
| **`-final`** | `<mode>` | Final output interpolation mode (`NN`, `linear`, `cubic`, `quintic`, `heptic`, `Fourier`) [19, 21]. |
| **`-weight`** | `'<wset[n]>'` | Applies 3D spatial weighting dataset sub-brick during alignment [19, 21]. |

---

## 4. `3dAllineate`
`3dAllineate` performs affine (12-parameter) spatial alignment between source and base datasets [25, 26].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-source` (`-input`)** | `<dset>` | Specifies input source dataset to be aligned [27-29]. |
| **`-base` (`-reference`)** | `<dset>` | Target base dataset defining target coordinate space [27, 30]. |
| **`-prefix` (`-out_file`)** | `<pname>` | Prefix name for output warped dataset [27, 28, 31]. |
| **`-cost`** | `<cost_func>` | Selects alignment cost functional (`lpc`, `lpa`, `lpc+ZZ`, `lpa+ZZ`, `mi`, `nmi`, `hel`, `crA`) [29, 32-34]. |
| **`-autoweight`** | `[+clip][^power]` | Automasks and blurs base image to compute spatial weighting map [35]. |
| **`-automask`** | *None* | Automatically masks base volume during cost calculation [26, 35]. |
| **`-source_mask` / `-source_automask`** | `<sss>` / *None* | Masks or automasks source dataset [26, 29]. |
| **`-weight`** | `<wset>` | Specifies custom 3D weighting dataset for alignment cost optimization [21, 29, 36]. |
| **`-interp` / `-final`** | `<mode>` | Interpolation mode during parameter search and final resampling (`NN`, `linear`, `cubic`, `quintic`, `wsinc5`) [28, 37-39]. |
| **`-onepass` / `-twopass`** | *None* | Selects single-pass or dual-pass optimization search [21, 31, 40]. |
| **`-warp`** | `<warp_type>` | Sets transformation model (`shift_only`, `shift_rotate`, `shift_rotate_scale`, `affine_general`) [26, 41]. |
| **`-warpfreeze`** | *None* | Freezes non-rigid body parameter search after initial sub-brick alignment [41, 42]. |
| **`-replacebase`** | *None* | Uses aligned sub-brick #0 as reference base for subsequent sub-bricks [42]. |
| **`-1Dparam_save` / `-1Dparam_apply`** | `<file.1D>` | Saves or applies pre-computed 1D transformation parameters directly [27, 28, 43, 44]. |
| **`-1Dmatrix_save`** | `<file.aff12.1D>` | Saves output 3x4 affine transformation matrix to text file [29]. |
| **`-emask`** | `<ee>` | Exclusion mask dataset; non-zero voxels in `ee` are excluded from cost calculation [32]. |
| **`-maxscl` / `-maxshr`** | `<dd>` | Maximum scaling or shearing factor allowed during search [45]. |
| **`-blok`** | `<shape(r)>` | Block shape and radius for local Pearson cost functions (`BALL`, `CUBE`, `RHDD`, `TOHD`) [36]. |

---

## 5. `3dQwarp`
`3dQwarp` computes non-linear spatial warp transformations between source and base datasets using hierarchical patch refinement [46, 47].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-base`** | `<dset>` | Specifies target base template dataset [46, 48-50]. |
| **`-source`** | `<dset>` | Specifies input source dataset to be warped [46, 48, 49, 51]. |
| **`-prefix`** | `<prefix>` | Prefix for warped output dataset (saves non-linear warp field to `<prefix>_WARP`) [39, 52, 53]. |
| **`-minpatch`** | `<n>` | Minimum patch size in voxels for multi-level patch optimization (e.g., `25`, `11`, `5`) [46, 54, 55]. |
| **`-blur`** | `<b1 b2>` | Gaussian blurring FWHM (in mm) applied to base (`b1`) and source (`b2`) datasets [52, 54, 56]. |
| **`-pblur`** | `<p1 p2>` | Applies progressive blurring across refinement levels [56, 57]. |
| **`-allineate` / `-allinfast`** | *None* | Automatically executes `3dAllineate` affine initialization prior to non-linear warping [34, 40, 58-60]. |
| **`-allineate_opts`** | `'<opts>'` | Passes custom flag string to internal `3dAllineate` call [32, 34, 61]. |
| **`-resample`** | *None* | Resamples source dataset grid to match base volume grid before warping [43, 58, 62, 63]. |
| **`-pear`** | *None* | Forces strict Pearson correlation cost functional instead of clipped Pearson [56, 57]. |
| **`-hel` \| `-mi` \| `-nmi` \| `-lpc` \| `-lpa`** | *None* | Selects alternative non-linear cost functionals (`lpc` for EPI-to-T1, `lpa` for T1-to-FA) [33, 48, 55, 64-66]. |
| **`-plusminus`** | *None* | Enables meet-in-the-middle warping for blip-up/blip-down distortion correction (outputs `_PLUS` and `_MINUS` warps) [67-71]. |
| **`-pmBASE`** | *None* | Writes full source-to-base warp and warped dataset from plusminus half-warps [72]. |
| **`-iwarp`** | *None* | Calculates and saves inverse non-linear warp field dataset (`<prefix>_WARPINV`) [39, 64, 65, 73]. |
| **`-awarp`** | *None* | Outputs incremental warp from affine-aligned intermediate volume to base (`<prefix>_AWARP`) [32, 73]. |
| **`-nowarp`** | *None* | Suppresses saving of `<prefix>_WARP` dataset [39, 73, 74]. |
| **`-nodset`** | *None* | Suppresses output of warped source dataset [73]. |
| **`-inilev`** | `<level>` | Starting hierarchical refinement level for re-starting warp optimization [54, 75, 76]. |
| **`-iniwarp`** | `<dset>` | Inputs initial non-linear warp dataset to seed warp calculations [54, 75-77]. |
| **`-useweight` / `-noweight`** | *None* | Configures automatic weight volume computation from base automask [78-80]. |
| **`-weight`** | `<www>` | Inputs custom 3D weight volume for cost evaluation [78-80]. |
| **`-wball`** | `<x y z r f>` | Enhances weight map centered at DICOM coordinates `(x,y,z)` [78-80]. |
| **`-wtprefix`** | `<p>` | Saves generated weight volume dataset to prefix `p` [81]. |
| **`-emask`** | `<ee>` | Exclusion mask dataset; non-zero voxels in `ee` are excluded from cost calculation [32]. |
| **`-lite` / `-nolite`** | *None* | Toggles fast memory/computation optimization algorithms (default: `-lite`) [11, 13, 68, 82]. |
| **`-workhard` / `-superhard` / `-Workhard`** | *None* | Increases iteration count per level [82, 83]. |
| **`-Qfinal` / `-Qonly`** | *None* | Uses Hermite quintic polynomials at final level or all refinement levels [51, 60, 83-87]. |
| **`-ballopt` / `-boxopt`** | *None* | Uses hypersphere ball or rectangular box optimization limits [88-90]. |
| **`-expad`** | `<EE>` | Extra voxel padding around warp field boundaries [91-93]. |
| **`-nopad` / `-nopadWARP`** | *None* | Disables zero-padding or truncates output warp to base grid [88, 94-97]. |
| **`-noXdis` / `-noYdis` / `-noZdis`** | *None* | Freezes displacement field along X, Y, or Z axis [55, 66, 98, 99]. |
| **`-allsave` / `-saveall`** | *None* | Saves intermediate warp datasets from each refinement level [61, 67, 89]. |

---

## 6. `3dNwarpApply`
`3dNwarpApply` applies composite non-linear spatial transformation chains to 3D/4D datasets [100, 101].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-source`** | `<dset>` | Input source dataset(s) to be warped [100-102]. |
| **`-master`** | `<dset \| NWARP>` | Output reference master dataset defining target spatial grid, orientation, and FOV [37, 101, 103]. |
| **`-nwarp`** | `'<warp_spec>'` | Ordered string specifying non-linear warps, affine matrices, and operators (`SQRT()`, `INV()`, `INVSQRT()`, `FAC:x,y,z:`, `IDENT()`, `AP:`, `RL:`, `IS:`) [38, 39, 100, 101, 104-108]. |
| **`-prefix`** | `<prefix>` | Prefix name for warped output dataset [100-103]. |
| **`-interp`** | `<mode>` | Dataset resampling interpolation mode (`wsinc5`, `quintic`, `linear`, `NN`) [37, 108]. |
| **`-ainterp`** | `<mode>` | Separate interpolation mode for discrete integer datasets (e.g., ROI masks) [59, 108]. |
| **`-newgrid` / `-dxyz`** | `<dd>` | Resizes output grid spacing in millimeters [23, 37]. |
| **`-iwarp` (`-inv_warp`)** | *None* | Inverts final composite warp before applying [103]. |
| **`-short`** | *None* | Saves output using 16-bit short integers rather than 32-bit floats [109, 110]. |
| **`-quiet` / `-verb`** | *None* | Toggles verbose progress logging [103, 105, 110]. |

---

## 7. `3dSkullStrip`
`3dSkullStrip` extracts brain tissue from T1-weighted structural MRI datasets using an expanding surface sphere model [111-113].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-input`** | `<VOL>` | Inputs 3D T1-weighted anatomical dataset [111-114]. |
| **`-prefix`** | `<VOL_PREFIX>` | Sets prefix for skull-stripped output volume [111-115]. |
| **`-human` / `-monkey` / `-marmoset` / `-rat`** | *None* | Selects species-specific brain template defaults (default: `-human`) [111-113]. |
| **`-surface_coil`** | *None* | Adjusts intensity threshold defaults for surface coil acquisition data [111, 113]. |
| **`-o_TYPE`** | `<PREFIX>` | Saves 3D brain surface mesh (`fs`, `1d`, `sf`, `ply`) [112, 113]. |
| **`-skulls`** | *None* | Generates outer skull boundary surface models [113]. |
| **`-mask_vol`** | *None* | Outputs integer mask volume (values 0–6 indicating surface boundary relations) instead of stripped volume [113]. |
| **`-norm_vol`** | *None* | Outputs intensity-normalized and thresholded brain volume (default) [113]. |
| **`-orig_vol`** | *None* | Outputs masked volume preserving original voxel intensities [113]. |
| **`-blur_fwhm`** | `<FWHM>` | Applies Gaussian blurring (FWHM in mm) prior to spatial normalization [116, 117]. |
| **`-fac`** | `<FAC>` | Multiplies input dataset by factor `FAC` if dynamic range is narrow [117]. |
| **`-visual`** | *None* | Interactive visualization mode (`-talk_suma -feed_afni -send_kth 5`) [118]. |
| **`-spat_norm` / `-no_spatnorm`** | *None* | Toggles initial spatial normalization preprocessing [112, 119]. |
| **`-spatnorm_dxyz`** | `<DXYZ>` | Grid resolution for spatially normalized volume [119]. |
| **`-niter`** | `<N_ITER>` | Number of surface expansion iterations (default: 250) [112, 116, 119]. |
| **`-ld`** | `<LD>` | Surface mesh density parameter (default: 20 or 30 with edges) [111, 112, 119]. |
| **`-shrink_fac`** | `<SF>` | Brain/non-brain intensity threshold fraction (default: 0.6) [112, 116, 119]. |
| **`-var_shrink_fac` / `-no_var_shrink_fac`** | *None* | Varies shrink factor across iterations [112, 119]. |
| **`-shrink_fac_bot_lim`** | `<SFBL>` | Lower limit for varying shrink factor (default: 0.65 or 0.4) [116, 119]. |
| **`-pushout` / `-no_pushout`** | *None* | Considers intensities above nodes during surface expansion [112, 119]. |
| **`-touchup` / `-no_touchup`** | *None* | Performs final touchup operations for missed brain regions [112, 119, 120]. |
| **`-fill_hole`** | `<R>` | Fills small surface intersection holes (max side radius `R`) [112, 120]. |
| **`-avoid_vent` / `-no_avoid_vent`** | *None* | Avoids ventricle attraction during surface expansion [112, 116, 120]. |
| **`-avoid_eyes` / `-no_avoid_eyes`** | *None* | Avoids eye structures during surface expansion [112, 116, 120]. |
| **`-use_edge` / `-no_use_edge`** | *None* | Uses edge detection to reduce meningeal leakage [112, 120]. |
| **`-push_to_edge` / `-no_push_to_edge`** | *None* | Performs aggressive final push to brain edge [111, 112, 116, 120]. |
| **`-use_skull` / `-no_use_skull`** | *None* | Uses outer skull model to constrain surface expansion [112, 116, 120]. |

---

## 8. `3dDeconvolve`
`3dDeconvolve` performs Ordinary Least Squares (OLSQ) multiple linear regression and deconvolution analysis on 3D+time functional series [121, 122].

| Category | Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- | :--- |
| **Input Data** | **`-input`** | `<fname1 fname2 ...>` | Inputs 3D+time datasets (auto-catenates multi-run lists; accepts transposed `file.1D'`) [121-124]. |
| | **`-input1D`** | `<dname>` | Inputs single 1D column text time series file [121, 122]. |
| | **`-nodata`** | `<NT TR>` | Generates regression matrix without image data (used for experimental design evaluation) [125-128]. |
| | **`-concat`** | `<rname>` | Inputs run breakpoint start TR indices (`'1D: 0 100 ...'`) [122, 123, 129-131]. |
| **Control** | **`-polort`** | `<pnum \| A \| -1>` | Baseline polynomial order (`A` auto-selects `1+int(D/150)`, `-1` removes baseline) [115, 125-127, 129, 132]. |
| | **`-noblock`** | *None* | Treats multi-file inputs as one continuous run [123, 130, 133]. |
| | **`-GOFORIT`** | `[g]` | Bypasses collinearity/matrix warnings (optional number `g` warnings allowed) [5, 8, 134-136]. |
| | **`-nocond`** | *None* | Disables matrix condition number computation [135]. |
| | **`-singvals`** | *None* | Prints matrix singular values [135]. |
| | **`-censor`** | `<1D_file>` | Inputs binary 1D censoring file (1=include, 0=censor) [122, 123, 137, 138]. |
| | **`-CENSORTR`** | `'<strings>'` | Censors specific TRs directly on command line (`'37'`, `'2:37'`, `'37..47'`, `'*:0-2'`) [131, 138, 139]. |
| **Stimulus** | **`-num_stimts`** | `<k>` | Total number of input stimulus classes [124-127, 140]. |
| | **`-stim_file`** | `<k sname>` | Directs column 1D file into design matrix for class `k` [122, 140]. |
| | **`-stim_label`** | `<k slabel>` | Assigns string label to stimulus class `k` [3, 4, 6, 8, 124, 141]. |
| | **`-stim_times`** | `<k tname Rmodel>` | Inputs stimulus onset timing file (sec) and response model `Rmodel` [3, 4, 6, 124, 126-128]. |
| | **`-stim_times_AM1`** | `<k tname Rmodel>` | First-order amplitude modulation regressor [125, 142]. |
| | **`-stim_times_AM2`** | `<k tname Rmodel>` | Second-order amplitude modulation regressor [142, 143]. |
| | **`-stim_times_IM`** | `<k tname Rmodel>` | Individual Response Modulation (estimates separate beta per trial) [144]. |
| | **`-ortvec`** | `<file label>` | Directs multi-column 1D matrix into baseline model [126]. |
| **GLT** | **`-num_glt`** | `<n>` | Total number of General Linear Tests [5, 124]. |
| | **`-gltsym`** | `'<symbolic_spec>'` | Defines symbolic GLT contrast string (e.g., `'SYM: +HH -LL'`) [1, 3-6, 8, 124, 145]. |
| | **`-glt_label`** | `<k label>` | String label for GLT contrast [1, 3-6, 8, 124]. |
| **Outputs** | **`-bucket`** | `<prefix>` | Saves full regression statistics dataset [124, 131, 146]. |
| | **`-cbucket`** | `<cprefix>` | Saves dataset containing estimated regression coefficients (betas) only [131, 141]. |
| | **`-fitts`** | `<prefix>` | Outputs full model fitted time series dataset [4, 5, 8, 141, 147]. |
| | **`-errts`** | `<prefix>` | Outputs residual error time series dataset [4, 5, 147-149]. |
| | **`-iresp`** | `<k prefix>` | Outputs estimated impulse response function for stimulus class [140]. |
| | **`-x1D`** | `<filename.1D>` | Saves 2D design matrix to ASCII 1D text file [124-127, 137, 141, 144, 147, 150, 151]. |
| | **`-xjpeg`** | `<filename.jpg>` | Outputs JPEG image preview of design matrix [147, 152]. |
| | **`-x1D_stop`** | *None* | Writes design matrix file and terminates without voxelwise regression [126, 127, 150]. |
| | **`-x1D_uncensored`** | *None* | Outputs uncensored design matrix file [147, 153]. |
| | **`-bout` / `-nobout`** | *None* | Toggles output of baseline coefficient sub-bricks in bucket dataset [5, 128, 132]. |

---

## 9. `3dREMLfit`
`3dREMLfit` performs Generalized Least Squares (GLSQ) regression accounting for ARMA(1,1) temporal autocorrelation structures [147, 150, 154].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-input`** | `<dset>` | Input 3D+time dataset (without censoring) [137, 147]. |
| **`-matrix`** | `<xmat.1D>` | Design matrix file (`.xmat.1D`) generated by `3dDeconvolve` [137, 150, 151, 155]. |
| **`-dsort`** | `<dset>` | Input voxelwise baseline regressor dataset (e.g. ANATICOR white matter maps) [130, 156]. |
| **`-addbase`** | `<1D_file>` | Adds global baseline regressor columns to design matrix [132, 156]. |
| **`-slibase`** | `<1D_file>` | Adds slice-specific baseline regressor columns [132, 156]. |
| **`-nodmbase`** | *None* | Does not remove mean from added baseline columns [132]. |
| **`-Rbeta` / `-Rbrts` / `-Rbuck` / `-Rvar` / `-Rfitts`** | `<prefix>` | Outputs for REML GLSQ estimation (coefficients, residual time series, statistics bucket, noise variance, fitted series) [5, 6, 8, 132, 144, 156]. |
| **`-Obeta` / `-Oerrts` / `-Obuck` / `-Ovar` / `-Ofitts`** | `<prefix>` | Outputs for OLSQ estimation [132, 154, 156]. |
| **`-MAXa`** | `<am>` | Sets maximum allowed AR parameter `a` (default: `0.8`) [154]. |
| **`-ABfile`** | `<a,b>` | Inputs fixed ARMA parameters `a,b` or sets `=0,0` to skip ARMA estimation [154]. |
| **`-GOFORIT`** | `[g]` | Bypasses non-fatal setup warnings (e.g., `-GOFORIT 99`) [5, 155]. |

---

## 10. `3dcalc`
`3dcalc` executes voxel-by-voxel mathematical expressions across 3D/4D datasets [113, 157-159].

| Flag / Option | Parameter / Syntax | Description |
| :--- | :--- | :--- |
| **`-a` through `-z`** | `<dset>` | Binds dataset inputs to letter variables `a` through `z` (up to 26 inputs; supports sub-brick `[n]` and range `<a..b>` selection) [113, 157-159]. |
| **`-expr`** | `'<expression>'` | Mathematical expression string enclosed in single quotes [113, 157-159]. |
| **`-prefix`** | `<pname>` | Output dataset prefix name [113, 159, 160]. |
| **`-datum`** | `<byte \| short \| float>` | Sets output voxel storage data type [145, 161, 162]. |
| **`-float` / `-short` / `-byte`** | *None* | Shortcut selector flags for output voxel storage data type [145, 162]. |
| **`-nscale`** | *None* | Disables automatic integer scaling factors when writing `short` or `byte` datasets [113]. |

### Special Functions, Variables, and Offsets in `3dcalc`
* **Functions**: `step(x)` (returns 1 if $x > 0$, else 0) [113], `amongst(a,b,c,...)` (returns 1 if $a$ matches any argument, else 0), `equals(a,b)` (returns 1 if $a = b$).
* **Voxel Relative Offsets**: `a+i`, `a-i` (X-axis offset), `a+j`, `a-j` (Y-axis offset), `a+k`, `a-k` (Z-axis offset), `a+l`, `a-l` (time-axis TR offset) for 3D erosion/dilation operations [113].
* **Predefined Coordinates & Variables**: `x`, `y`, `z` (DICOM spatial coordinates in mm), `i`, `j`, `k` (3D array voxel indices), `t` (time in seconds), `l` (TR index) [113, 161].

---
