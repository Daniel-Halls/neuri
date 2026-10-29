### **Functional MRI Subpackages**

#### **1. FEAT (FMRI Expert Analysis Tool)**
* **`feat <design.fsf>`**: Main execution command to run a first-level or higher-level GLM analysis pipeline using a pre-configured `.fsf` specification file [1, 2].
* **Associated FEAT Command-Line Executables**:
  * **`feat_model <fsf_file> <ev_files>`**: Uses a FEAT design specification file (`.fsf`) to generate the GLM design matrix (`.mat`) and visual design matrix representations [3-5].
  * **`updatefeatreg <featdir.feat> -gifs`**: Updates and regenerates registration summary images and transformation matrices within a FEAT directory [6].
  * **`mccutup`**: Converts motion parameter estimates stored in a FEAT directory into individual volume-level custom EV files [3].
  * **`renderhighres`**: Transforms thresholded stats images into high-resolution or standard space, overlays them onto structural/standard images, and outputs 2D PNG summary renderings [3].
  * **`easythresh <stats_image> <brain_mask> <z_thresh> <prob_thresh> <background_image> <output_prefix>`**: Performs cluster-based thresholding and overlays statistical activations onto background images [7, 8].
  * **`topup` FEAT Integration Flag**:
    * **`--featout=<filename>`**: Generates distorted-unwarped fieldmap magnitude (`_fieldmap_mag`) and phase-rads (`_fieldmap_rads`) images formatted specifically for direct ingestion into FEAT [9-11].

#### **2. featquery (FEAT Results Interrogation)**
* **Command Syntax**: `featquery <n_featdirs> <featdir1> ... <n_stats> <stat1> ... <output_name> <mask_file> [options]` [12-14].
* **Options & Parameters**:
  * **`-p`**: Automatically calculates percentage signal change for the modeled experimental paradigm [15-17].
  * **`-s`**: Selects specific statistical contrast images (e.g., `cope1`, `zstat1`) to interrogate within the mask [13, 14, 18].
  * **`-m <mask_file>`**: Specifies a binary ROI/mask file (in low-res functional, high-res structural, or standard space) [7, 12, 19].
  * **`-a <atlas_name>`**: Specifies an installed standard-space atlas to automatically query anatomical region probabilities for peak activation coordinates [19].
  * **Output Features**: Outputs non-zero voxel count, minimum, maximum, mean, median, standard deviation, peak MNI coordinates, and raw text timeseries plots [12, 14, 18, 20].

#### **3. featregapply**
* **Command Syntax**: `featregapply <featdir.feat> [options]` [7, 21, 22].
* **Options & Parameters**:
  * **`<featdir.feat>`**: Target first-level FEAT directory [7].
  * **`-warp <fnirt_warp_file>`**: Specifies the non-linear registration warp field file (e.g., `highres2standard_warp.nii.gz`) [21].
  * **`-affmat <mat_file>`**: Specifies the lowres-to-highres affine matrix (e.g., `example_func2highres.mat`) [22].
  * **`-m <mask_file>`**: Applies a custom volume mask in reference space [21].
  * **`-meldir <melodic_dir>`**: Path to pre-calculated MELODIC ICA directory [22].

#### **4. MELODIC (Multivariate Exploratory Linear Optimised Decomposition into Independent Components)**
* **`melodic [options]`**:
  * **`-i, --in=<filename(s)>`**: Input 4D time-series dataset(s) [23-25].
  * **`-o, --outdir=<directory>`**: Output ICA directory (e.g., `filtered_func_data.ica`) [23-25].
  * **`-m, --mask=<filename>`**: Binary mask image [26].
  * **`--dim=<int>`**: Dimensionality constraint / number of components to extract [27-29].
  * **`--approach=<mode>`**: Decomposition approach (e.g., `tica` for Tensor ICA, `concat` for Group ICA) [25].
  * **`--mix=<matrix_file>`**: Mixing matrix for spatial filtering or mixture modeling [24, 25, 30].
  * **`-f, --remove=<int_list>`**: Comma-separated component index numbers to remove during denoising [24, 31-34].
  * **`--nobet`**: Disables automatic BET brain extraction [25, 30].
  * **`--bgthreshold=<float>`**: Background intensity thresholding percentage [25].
  * **`--migp_shuffle`**: Randomizes MIGP data input order [25, 30].
  * **`--mmthresh=<float>`**: Mixture Model Z-threshold for central noise vs. activation classification [25, 27, 30].
  * **`--vn`**: Enables MELODIC variance-normalization on input time series [35].
  * **`--pbsc`**: Disables conversion to percent BOLD signal change [33].
  * **`--Ounmix` / `--Owhite`**: Outputs the unmixing and whitening/dewhitening matrices [33].
  * **`-v, --verbose`**: Verbose output mode [24].
* **`fsl_regfilt` (MELODIC Denoising Utility)**:
  * **`-i <input_4d>`**: Input 4D BOLD dataset (`filtered_func_data.nii.gz`) [24, 34, 36].
  * **`-o <output_4d>`**: Output denoised dataset [24, 34, 36].
  * **`-d <mixing_matrix>`**: MELODIC mixing matrix file (`melodic_mix`) [24, 34, 36].
  * **`-f "<component_list>"`**: Comma-separated list of component numbers to regress out (e.g., `"2,5,9"`) [24, 34, 36].
  * **`-A`**: Applies aggressive (full-variance) regression cleanup instead of non-aggressive unique-variance cleanup [37, 38].

#### **5. FIX (FMRIB's ICA-based Xnoise-ifier) & pyfix**
* **Unified Single-Command Workflow**: `fix <mel.ica> <model> <threshold> [cleanup_options]` [28, 29, 39].
* **Modular Stage Commands & Options**:
  * **`fix -f <mel.ica>`**: Extracts spatial, temporal, and spectral features for classification [40-44].
  * **`fix -c <mel.ica> <model/training.RData> <threshold>`**: Classifies ICA components using a trained model and a threshold (typically 5–20) [40-42, 45-47].
  * **`fix -a <labels.txt> [<mel.ica>] [options]`**: Cleans BOLD time series by regressing out noise ICs listed in `labels.txt` [37, 38, 42, 43, 45, 48, 49]:
    * **`-m`**: Regresses out 24 motion confound parameters [28, 37, 38, 49].
    * **`-h <highpass>`**: Controls high-pass filtering of motion confounds (`-h -1`: no filter; `-h 0`: linear detrending; positive float: full-width $2\sigma$ cutoff in seconds; if omitted, reads cutoff from `design.fsf`) [37, 38, 50-52]. Applies to NIfTI and CIfTI time series [50, 51].
    * **`-A`**: Performs aggressive cleanup (full variance) [37, 38, 53].
    * **`-o <nifti|cifti>` / `--only <nifti|cifti>`**: Restricts cleanup strictly to NIfTI (`filtered_func_data.nii.gz`) or CIfTI (`Atlas.dtseries.nii`) data [48].
    * **`-x <confound_file>`**: Includes additional custom text-file confound regressors [45, 49].
  * **`fix -t <mymodel> [-l] <mel1.ica> <mel2.ica> ...`**: Trains a new classifier model with an optional Leave-One-Out (`-l`) cross-validation test [41, 44, 54-58].
  * **`fix -C <model> <output> <mel1.ica> ...`**: Evaluates model performance across hand-labeled datasets [41, 45].
* **`fsl_ents`**: Extracts component time series from a MELODIC folder based on a label file into a text file formatted for use as FEAT confound EVs [59, 60].

#### **6. FLOBS (FMRIB's Linear Optimal Basis Sets)**
* **`Make_flobs` / `make_flobs`**: Interactive tool and GUI accessible via FEAT Utilities to generate optimal HRF linear basis sets using Principal Component Analysis (PCA) based on user-defined delay and height ranges [61-63].

#### **7. PNM (Physiological Noise Modelling)**
* Tool suite for converting physiological pulse-oximetry and respiratory trace signals into voxelwise harmonic EVs [60, 63-65].
* Integrated with FIX via `pnm_fix` / `fsl_ents` to combine physiological and ICA noise regressors into a unified FEAT confound matrix [59, 60].

---

### **Structural and Registration Subpackages**

#### **8. BET / BET2 (Brain Extraction Tool)**
* **Command Syntax**: `bet <input> <output> [options]` [66-68].
* **Core Options**:
  * **`-f <frac>`**: Fractional intensity threshold (0..1, default=0.5; smaller values yield larger brain estimates) [27, 66-72].
  * **`-g <grad>`**: Vertical threshold gradient (-1..1, default=0; positive values expand bottom, shrink top) [67, 73].
  * **`-r <radius>`**: Initial head radius in mm [67, 74].
  * **`-c <x y z>`**: Initial mesh center-of-gravity coordinates in voxels [67, 73, 75].
  * **`-m`**: Outputs a binary brain mask (`_mask.nii.gz`) [66, 67].
  * **`-o`**: Generates a brain surface outline image [67, 76].
  * **`-s`**: Generates a rough skull surface image [67, 77].
  * **`-n`**: Suppresses generation of extracted brain volume [67, 76].
  * **`-e`**: Outputs brain surface mesh in VTK format [66, 67].
  * **`-t`**: Applies intensity thresholding to brain image and mask [67].
  * **`--ct`**: CT image processing mode (Hounsfield transform scaling) [67].
* **Specialized Mutually Exclusive Modes**:
  * **`-R`**: Robust brain center estimation (iterates BET center of gravity up to 10 times) [72, 77].
  * **`-S`**: Cleans up residual eye and optic nerve tissue (useful for SIENA) [72, 74].
  * **`-B`**: Performs bias field reduction and neck cleanup using FAST [72, 74].
  * **`-Z`**: Pads Z-axis end slices for small axial FOV inputs [72, 76].
  * **`-F`**: 4D fMRI brain extraction (calculates mask from 1st volume using reduced `-f 0.3` threshold and dilates) [27, 66, 72].
  * **`-A`**: Calls `bet2` and `betsurf` to extract inner/outer skull and scalp surfaces [77, 78].
  * **`-A2 <T2w_image>`**: Uses both T1 and T2 images for surface estimation [78].

#### **9. FAST (FMRIB's Automated Segmentation Tool)**
* **Command Syntax**: `fast [options] <input_file(s)>` [79, 80].
* **Options & Parameters**:
  * **`-n, --class <int>`**: Number of tissue classes (default=3) [79].
  * **`-t, --type <1|2|3>`**: Image contrast type (1=T1, 2=T2, 3=PD; default=1) [79].
  * **`-b`**: Outputs estimated bias field image [79, 81].
  * **`-B`**: Outputs bias-corrected (restored) image [79, 81].
  * **`-S, --channels <int>`**: Number of multi-channel input images (default=1) [79, 80].
  * **`-o, --out <basename>`**: Output file basename [79, 81].
  * **`-p`**: Outputs individual probability maps for each class [81].
  * **`-g`**: Outputs separate binary segmentation masks for each tissue [82].
  * **`-s, -manual_seg <file>`**: Text file with initial tissue class mean intensities [79, 83].
  * **`-a, -init_transform <mat>`**: Affine transformation matrix for standard-space prior alignment [83].
  * **`-P`**: Uses spatial tissue priors throughout segmentation iterations [82].
  * **`-l <value>`**: Bias field smoothing FWHM in mm [84].
  * **`-i <int>`**: Total segmentation iterations [71, 85].
  * **`-W, -segment_iters <int>`**: Segmentation-initialization iterations [82].
  * **`-O, -iters_afterbias <int>`**: Iterations after bias-field removal [83].
  * **`-R, -mixel_smooth <float>`**: Mixeltype spatial smoothness factor (0.0 to 1.0) [83].
  * **`-v, --verbose`**: Switches on verbose diagnostic messages [82].

#### **10. FIRST (Subcortical Structural Segmentation)**
* **`run_first_all` (Automated Subcortical Pipeline)**:
  * **`-i <t1_image>`**: Input T1 structural image [86, 87].
  * **`-o <output_basename>`**: Base output filename [87].
  * **`-s <structure_list>`**: Comma-separated list of target structures (`L_Accu`, `L_Amyg`, `L_Caud`, `L_Hipp`, `L_Pall`, `L_Puta`, `L_Thal`, `R_Accu`, `R_Amyg`, `R_Caud`, `R_Hipp`, `R_Pall`, `R_Puta`, `R_Thal`, `BrStem`) [88].
  * **`-b`**: Specifies that the input image is already brain-extracted [88].
  * **`-a <mat>`**: Uses a pre-calculated `first_flirt` registration matrix [88].
  * **`-d`**: Retains intermediate files for debugging [89].
* **`run_first` (Individual Structure Fitting)**:
  * **`-i <t1_image>`**: Input T1 image [90].
  * **`-t <matrix>`**: Registration matrix from `first_flirt` [90].
  * **`-n <modes>`**: Number of variation modes (up to 336) [90].
  * **`-m <model.bmv>`**: Subcortical model file path [90].
  * **`-o <basename>`**: Output basename (generates `.vtk`, `.nii.gz`, `.bvars`) [90, 91].
  * **`-loadBvars <bvars_file>`**: Initializes fitting with a prior shape estimate [91].
  * **`-shcond`**: Conditional shape fitting relative to a fixed structure [91].
  * **`-intref <model>`**: Intensity reference structure model [92].
  * **`-multipleImages <list_file>`**: 3-column text list (`image`, `matrix`, `basename`) for batch fitting [92, 93].
* **`first_flirt`**:
  * `first_flirt <input_t1> <output_name>`: Subcortical-focused linear registration [94].
  * **`-b`**: Input image is brain-extracted [88, 94, 95].
  * **`-d`**: Prevents deletion of intermediate registration files [94].
  * **`-inweight <image>`**: Applies cost function weighting to input image [95].
  * **`-cort`**: Runs second stage registration with a brain mask (for cerebellum models) [95].
* **`first_boundary_corr`**:
  * **`-s <seg_image>`**: FIRST raw segmented image [96].
  * **`-i <t1_image>`**: T1 structural image [96].
  * **`-b <fast|thresh>`**: Boundary correction method [96].
  * **`-t <thresh>`**: Threshold value if using `thresh` boundary correction [96].

#### **11. fsl_anat (Anatomical Processing Pipeline)**
* **Command Syntax**: `fsl_anat [options] -i <structural_image>` or `-d <anat_dir>` [84].
* **Options & Parameters**:
  * **`-i <filename>`**: Input structural image [84].
  * **`-d <anat_dir>`**: Path to an existing `.anat` directory to rerun in-place [84].
  * **`-o <output_dir>`**: Base directory name for output (default: `<input>.anat`) [84].
  * **`--clobber`**: Overwrites existing output directory [84].
  * **`--strongbias`**: Optimizes for strong bias fields (high-field / multi-coil arrays) [84, 97].
  * **`--weakbias`**: Default setting for smoother/typical bias fields [84, 97].
  * **`--noreorient`**: Disables reorientation to standard MNI orientation (`fslreorient2std`) [84].
  * **`--nocrop`**: Disables automated FOV cropping (`robustfov`) [84].
  * **`--nobias`**: Disables bias field correction [84].
  * **`--noreg`**: Disables standard space linear and non-linear registration [84].
  * **`--nononlinreg`**: Disables FNIRT non-linear registration [84].
  * **`--noseg`**: Disables FAST tissue-type segmentation [84].
  * **`--nosubcortseg`**: Disables FIRST subcortical segmentation [84].
  * **`-s <value>`**: Bias field smoothing value passed to FAST (`-l` option) [84].
  * **`-t <T1|T2|PD>`**: Input image modality type (default: T1) [84].
  * **`--nosearch`**: Passes `-nosearch` flag to FLIRT linear registration [84].
  * **`--betfparam <value>`**: Sets BET `-f` fractional intensity threshold when FNIRT is omitted [84, 97].
  * **`--nocleanup`**: Retains intermediate files [84].

#### **12. SIENA (Structural Image Evaluation, using Normalisation, of Atrophy)**
* **Command Syntax**: `siena <input1> <input2> [options]` [69].
* **Options & Parameters**:
  * **`-o <output_dir>`**: Output directory name (default: `<input1>_to_<input2>_siena`) [69].
  * **`-d`**: Debug mode (retains intermediate files) [69].
  * **`-B "<bet_options>"`**: Quoted BET options passed to brain extraction (e.g., `-B "-f 0.3"`) [69].
  * **`-2`**: Two-class segmentation (disables separate GM/WM segmentation) [98, 99].
  * **`-t2`**: Specifies that input images are T2-weighted [98, 99].
  * **`-m`**: Applies standard-space brain masking alongside BET [99].
  * **`-t <t>`**: Ignores tissue above $t$ mm in MNI152 space [98, 99].
  * **`-b <b>`**: Ignores tissue below $b$ mm in MNI152 space [85, 98].
  * **`-S "<siena_diff_options>"`**: Quoted options passed directly to `siena_diff` [85].
  * **`-V`**: Executes VIENA ventricular atrophy analysis [85, 100].
  * **`-v <mask_image>`**: User-supplied ventricle mask for VIENA [85].
  * **`siena_flow2std <input1> <input2> [-s <smoothing>]`**: Transforms voxelwise atrophy edge flow images to standard space and applies Gaussian smoothing [101].

#### **13. SIENAX (Cross-sectional Brain Volume & Atrophy)**
* **Command Syntax**: `sienax <input> [options]` [70].
* **Options & Parameters**:
  * **`-o <output_dir>`**: Output directory (default: `<input>_sienax`) [70].
  * **`-d`**: Debug mode [70].
  * **`-B "<bet_options>"`**: Quoted BET options passed to brain extraction [70].
  * **`-2`**: Two-class tissue segmentation [98].
  * **`-t2`**: Specifies T2-weighted input image [98].
  * **`-t <t>`**: Ignores upper brain above $t$ mm in MNI space [98].
  * **`-b <b>`**: Ignores lower brain below $b$ mm in MNI space [98].
  * **`-r`**: Estimates regional volumes (peripheral cortex GM and ventricular CSF) [98].
  * **`-lm <mask_file>`**: Lesion/CSF mask file to exclude incorrectly classified GM voxels [71].
  * **`-S "<fast_options>"`**: Quoted options passed directly to FAST [71].

#### **14. FLIRT (FMRIB's Linear Image Registration Tool) & Utilities**
* **`flirt` (Main Linear/Affine Registration Tool)**:
  * **`-in <input_volume>`**: Moving input dataset [102-104].
  * **`-ref <ref_volume>`**: Target reference dataset [102-104].
  * **`-out <output_volume>`**: Output registered image [102-104].
  * **`-omat <matrix_file>`**: Output 4x4 ASCII affine matrix file [102, 103, 105, 106].
  * **`-dof <6|7|9|12>`**: Degrees of freedom for 3D alignment [103, 107-110].
  * **`-2D`**: 2D-to-2D rigid body alignment mode (3 DOF) [107, 108, 111].
  * **`-cost <mutualinfo|corratio|normcorr|normmi|leastsq|labeldiff|bbr>`**: Registration cost function (default: `corratio`) [103, 109, 110, 112].
  * **`-searchcost <cost>`**: Cost function used during initial search stage [104, 109, 110].
  * **`-wmseg <wm_seg>`**: White matter segmentation image required for BBR cost function [113, 114].
  * **`-bbrtype <signed|global_abs|local_abs>`**: BBR cost function variant [112].
  * **`-bbrslope <float>`**: BBR slope value [112].
  * **`-refweight <weight_image>` / **`-inweight <weight_image>`**: Voxelwise cost weighting masks [95, 108].
  * **`-interp <trilinear|nearestneighbour|sinc|spline>`**: Spatial interpolation method [102, 115, 116].
  * **`-sincwindow <rectangular|hanning|blackman>`**: Sinc windowing function [113, 114].
  * **`-applyxfm`**: Applies an existing transformation matrix supplied by `-init` without re-optimizing [102, 112, 116, 117].
  * **`-init <matrix_file>`**: Input initial transformation matrix [102, 116, 118, 119].
  * **`-usesqform`**: Initializes alignment using NIfTI qform/sform header world coordinates [102, 107, 113, 114, 117, 120].
  * **`-paddingsize <int>`**: External interpolation padding size [105, 106].
  * **`-datatype <char|short|int|float|double>`**: Forces output dataset data type [109, 110].
  * **`-displayinit`**: Displays initial alignment matrix [109, 110].
  * **`-schedule <schedule_file>`**: Custom optimization schedule script [108, 111, 121, 122].
* **FLIRT Utilities**:
  * **`applyxfm4D <in_4d> <ref> <out_4d> <matrix|mat_dir> [options]`**: Applies 3D FLIRT matrices to 4D time series datasets (includes `-userprefix <prefix>`) [27, 116].
  * **`convert_xfm`**:
    * **`-concat <mat2> -omat <out_mat> <mat1>`**: Concatenates two affine matrices [115, 123, 124].
    * **`-inverse <in_mat> -omat <out_mat>`**: Inverts an affine matrix [124].
  * **`avscale [--allparams] <mat_file>`**: Extracts scale factors, translations, rotations, and skews from a FLIRT matrix [125-127].

#### **15. FNIRT (FMRIB's Non-linear Image Registration Tool) & fnirtfileutils**
* **`fnirt` (Main Non-linear Registration Tool)**:
  * **`--ref=<target_image>`**: Target reference space image [128-130].
  * **`--in=<moving_image>`**: Moving image to register [128-130].
  * **`--aff=<matrix_file>`**: Initial affine transformation matrix from FLIRT [131, 132].
  * **`--inwarp=<coef/field_file>`**: Initial non-linear warp starting estimate [131, 133].
  * **`--intin=<intensity_map>`**: Initial intensity mapping file [131, 134, 135].
  * **`--config=<config_file>`**: Parameter configuration preset file (e.g., `T1_2_MNI152_2mm.cnf`, `FA_2_FMRIB58_1mm`) [23, 128, 129, 136].
  * **`--cout=<coef_file>`**: Outputs B-spline non-linear coefficient warp field [130, 137-140].
  * **`--iout=<warped_image>`**: Outputs warped image in reference space [130, 137, 141].
  * **`--fout=<field_file>`**: Outputs 4D deformation field image [137, 141].
  * **`--refmask=<mask_file>`**: Binary mask in reference space [129, 131, 135, 142].
  * **`--inmask=<mask_file>`**: Binary mask in moving image space [143].
  * **`--subsamp=<scheme>`**: Subsampling resolution levels (e.g., `4,2,1,1`) [129, 130].
  * **`--warpres=<x,y,z>`**: B-spline knot-spacing resolution in mm (e.g., `6,6,6`) [130, 144].
  * **`--infwhm=<fwhm_list>`**: Input image Gaussian smoothing FWHM per iteration level [130].
  * **`--reffwhm=<fwhm_list>`**: Reference image Gaussian smoothing FWHM per iteration level [142].
  * **`--regmod=<bending_energy|membrane_energy>`**: Regularization energy model [136].
  * **`--intmod=<global_linear|global_non_linear_with_bias|...>`**: Intensity mapping model [135].
  * **`--intout=<filename>`**: Output intensity mapping base filename [135].
  * **`--imprefm` / `--imprefval` / `--impinm` / `--impinval`**: Excludes specific FOV intensity values [142, 143].
  * **`--applyrefmask=<1|0>`**: Enables/disables reference mask application across iterations [129].
* **`fnirtfileutils`**:
  * **`--in=<coef_or_field>`**: Input coefficient or field file [141, 145-148].
  * **`--ref=<ref_vol>`**: Reference image grid [141, 145-148].
  * **`--out=<output_file>`**: Output file [141, 145, 146].
  * **`--outformat=<field|spline>`**: Output file format [141, 146].
  * **`--warpres=<mm>`**: Spline knot spacing for output field [141].
  * **`--jac=<jac_file>`**: Outputs 3D map of Jacobian determinants [141, 145, 149].
  * **`--withaff`**: Includes affine transformation displacements inside the output field [141, 145, 149, 150].
  * **`--verbose`**: Verbose logging [149, 151].

#### **16. applywarp & invwarp**
* **`applywarp`**:
  * **`--in=<file>`**: Input image to warp [140, 151-155].
  * **`--ref=<file>`**: Target reference space image [140, 151-153, 156, 157].
  * **`--warp=<file>`**: Non-linear warp coefficient or field file [140, 151-155].
  * **`--out=<file>`**: Output warped image [140, 152, 153, 157, 158].
  * **`--premat=<matrix_file>`**: Affine pre-transform matrix (e.g., `func2struct.mat`) [152, 157-159].
  * **`--postmat=<matrix_file>`**: Affine post-transform matrix [157].
  * **`--mask=<mask_file>`**: Target space mask file [157].
  * **`--interp=<nn|trilinear|sinc|spline>`**: Resampling interpolation model (default: `trilinear`) [153, 160].
  * **`--abs`**: Interprets warps as absolute coordinates [153, 155, 156].
  * **`--rel`**: Interprets warps as relative displacements (default for FNIRT) [153, 157, 159].
  * **`--datatype=<char|short|int|float|double>`**: Forces output data type [155, 156].
  * **`--superlevel=<a|int>`**: Intermediate supersampling level [157, 159].
  * **`--verbose`**: Displays diagnostic messages [153, 160].
* **`invwarp`**:
  * **`--warp=<warp_file>`**: Input non-linear warp field/coefficient file [161-163].
  * **`--ref=<ref_file>`**: Target reference image in inverse space [161-163].
  * **`--out=<output_file>`**: Output inverted non-linear warp field [161].
  * **`--niter=<int>`**: Gradient-descent iterations [163, 164].
  * **`--regularise=<float>`**: Regularization strength (default=1.0) [163-165].
  * **`--noconstraint`**: Disables Jacobian constraint [163-165].
  * **`--jmin=<val>` / `--jmax=<val>`**: Minimum and maximum Jacobian constraint boundaries (defaults: 0.01 to 100.0) [164, 165].
  * **`--abs` / `--rel`**: Specifies absolute vs. relative warp coordinates [161, 164, 166].

#### **17. convertwarp**
* **Command Syntax**: `convertwarp --ref=<reference> --out=<output> [options]` [165, 167-171].
* **Options & Parameters**:
  * **`--ref=<file>`**: Target reference volume [167, 168, 170].
  * **`--out=<output_file>`**: Combined output warp field file [167, 169, 170].
  * **`--premat=<file>`**: Pre-transform affine matrix [167, 170, 172].
  * **`--warp1=<file>`**: Initial non-linear warp field/coefficient file [167, 172, 173].
  * **`--midmat=<file>`**: Intermediate affine transform matrix [170, 174].
  * **`--warp2=<file>`**: Secondary non-linear warp field/coefficient file [167, 172, 173, 175, 176].
  * **`--postmat=<file>`**: Post-transform affine matrix [170, 172, 175].
  * **`--shiftmap=<file>`**: FUGUE B0 unwarping shiftmap [172, 173, 175, 177].
  * **`--shiftdir=<x|y|z|-x|-y|-z>`**: Phase-encoding distortion direction of shiftmap [173, 175, 178, 179].
  * **`--abs` / `--rel`**: Interprets input warps as absolute or relative [168, 170, 173, 178, 179].
  * **`--absout` / `--relout`**: Outputs combined warp as absolute coordinates or relative displacements [169, 170, 172, 174].
  * **`--jstats`**: Prints Jacobian statistics [178].
  * **`--constrainj`**: Constrains Jacobian determinant within min/max bounds [178].
  * **`--jmin=<val>` / `--jmax=<val>`**: Jacobian constraint limits [170, 174, 178].

#### **18. MCFLIRT (Motion Correction FLIRT)**
* **Command Syntax**: `mcflirt -in <infile> [options]` [180-182].
* **Options & Parameters**:
  * **`-in <infile>`**: Input 4D time-series image [180-182].
  * **`-out <outfile>`**: Output motion-corrected dataset [182].
  * **`-cost <mutualinfo|corratio|normcorr|normmi|leastsq>`**: Cost function [181, 182].
  * **`-bins <int>`**: Histogram bin count [104].
  * **`-dof <int>`**: Degrees of freedom (default=6) [103].
  * **`-refvol <int>`**: Volume number used as registration reference [180].
  * **`-reffile <file>`**: External reference target image [182].
  * **`-meanvol`**: Registers all volumes to the temporal mean volume [182].
  * **`-mats`**: Saves a FLIRT-compatible transformation matrix for every 3D volume (`MAT_XXXX`) [116, 180].
  * **`-plots`**: Saves estimated 6D motion parameters (3 rotations in radians, 3 translations in mm) to a `.par` text file [50, 180, 183].
  * **`-rmsabs` / `-rmsrel`**: Outputs absolute and relative displacement RMS values [184].
  * **`-stages <int>`**: Number of search optimization stages [180].
  * **`-scaling <float>` / `-smooth <float>`**: Rescaling and smoothing factors [180].
  * **`-gcut`**: Performs automatic brain cropping on the reference volume [180].

#### **19. SUSAN (Structure-Preserving Noise Reduction)**
* **Command Syntax**: `susan <input> <brightness_threshold> <fwhm> <dimension> <use_median> <n_usans> [usan1 usan2...] <output>` [185-187].
* **Options & Parameters**:
  * **`<input>`**: Input image dataset [185, 186].
  * **`<brightness_threshold>`**: Noise threshold for edge preservation [185, 186].
  * **`<fwhm>`**: Spatial smoothing kernel FWHM in mm [185, 186].
  * **`<dimension>`**: `3` for 3D spatial smoothing, `2` for slice-by-slice smoothing [186].
  * **`--slices` / `--force3D`**: Flags specifying 2D slice-wise vs. 3D spatial filtering [186].
  * **`<use_median>`**: Enables median filtering when local USAN area is small [185, 186].
  * **`<n_usans>`**: Number of local USAN area masks used (0, 1, or 2) [185, 186].

#### **20. FUGUE & prelude (EPI Distortion Correction)**
* **`fugue` (EPI Unwarping / Forward Warping)**:
  * **`-i <epi_image>`**: Input EPI dataset [188, 189].
  * **`-u <unwarped_file>` / `--unwarp=<file>`**: Outputs unwarped EPI dataset [188, 190-192].
  * **`-w <warped_file>` / `--warp=<file>`**: Outputs forward-warped EPI image [189, 191, 192].
  * **`-p <phasemap>` / `--phasemap=<file>`**: Input unwrapped phase map image [188-190, 192].
  * **`--loadfmap=<fmap_file>`**: Input pre-calculated fieldmap in rad/s [188, 190, 193, 194].
  * **`--savefmap=<fmap_file>`**: Saves processed fieldmap in rad/s [193, 194].
  * **`--dwell=<dwelltime>`**: EPI dwell time (echo spacing in seconds) [188-190].
  * **`--asym=<asymtime>`**: Fieldmap echo time difference ($\Delta TE$ in seconds) [188-190].
  * **`--unwarpdir=<x|y|z|x-|y-|z->`**: Phase-encoding direction (default: `y`) [191, 192, 195, 196].
  * **Fieldmap Regularization Options**:
    * **`-s <sigma>`**: 2D Gaussian smoothing factor [188-190].
    * **`--smooth3=<sigma>`**: 3D Gaussian smoothing factor [189].
    * **`-m` / `--median`**: 2D median filtering [189, 194].
    * **`--poly=<n>`**: 3D polynomial fitting degree $n$ [189, 192].
    * **`--fourier=<n>`**: 3D Fourier/sinusoidal fitting degree $n$ [189, 193, 194].
    * **`--pava`**: Enforces monotonic fieldmap constraints via PAVA [192].
  * **`--mask=<mask_file>`**: User-defined processing mask [195, 196].
  * **`--nokspace`**: Disables k-space forward warping [189, 194].
  * **`--noextend` / `--nofill`**: Disables rigid-body fieldmap extrapolation and gap-filling [194].
  * **`--icorr`**: Applies intensity correction term for pixel shift method [195, 196].
  * **`--phaseconj`**: Unwarps via phase conjugate method [192].
  * **`--saveshift=<file>`**: Outputs voxel shiftmap [192, 197].
* **`prelude` (3D Phase Unwrapping)**:
  * **`-c <complex_image>` / `--complex=<file>`**: Input complex image dataset [190, 196].
  * **`-p <phase_image>` / `-a <abs_image>`**: Separate input phase and magnitude images [196].
  * **`-u <unwrapped_phase>` / `--unwrap=<file>`**: Outputs unwrapped phase map in radians [185, 186, 190, 196].
  * **`--rawphase=<file>`**: Outputs raw phase image [186].
  * **`--slices` / `--force3D`**: 2D slice-wise vs. 3D phase unwrapping flags [186].

💡 **Next Step**: Would you like me to generate a structured reference cheat-sheet or Markdown report of these CLI tools with example pipeline calls for your workspace?

---

Below is the comprehensive, source-grounded documentation of command-line flags, arguments, and options for the requested FSL tools and subpackages.

---

### 1. FSL Diffusion Subpackages

#### **TOPUP (`topup`)**
`topup` estimates and corrects susceptibility-induced off-resonance field distortions in EPI images acquired with different phase-encoding directions [1-3].

* **Compulsory / Main Input Arguments:**
  * `--imain=<file>`: Path to the 4D input NIfTI image containing $b=0$ (or EPI) volumes acquired with differing phase-encoding directions [1, 2, 4, 5].
  * `--acqp=<file>` / `--datain=<file>`: ASCII text file specifying phase-encoding vectors and total readout times per volume [1, 2, 4-6].
  * `--config=<cnf_file>`: Configuration file containing predefined algorithmic options (e.g., `b02b0.cnf`, `b02b0_1.cnf`, `b02b0_2.cnf`, `b02b0_4.cnf`) [1, 2, 7-9].
  * `--out=<basename>`: Output basename for saved field coefficients and movement parameters [1, 2, 5, 10].
* **Output Control Options:**
  * `--fout=<file>`: Save the estimated off-resonance field map in Hz [5, 11].
  * `--iout=<file>`: Save the unwarped/corrected 4D output image [1, 5, 11].
  * `--logout=<file>`: Save detailed runtime log messages [5, 12].
  * `--rbmout=<file>`: Output estimated rigid-body motion parameters (`movpar.txt`) [5].
  * `--dfout=<file>`: Output spline warpfields [5].
  * `--jacout=<file>`: Save estimated Jacobian modulation maps [5].
* **Multi-Resolution & Processing Tuning Flags:**
  * `--subsamp=<levels>`: Subsampling factors per level (e.g., `4,2,1` or `1,1,1,1`) [7, 12, 13].
  * `--fwhm=<mm>`: Full-Width at Half-Maximum (mm) Gaussian smoothing kernel per level (e.g., `8,4,0`) [7, 14].
  * `--regmod=<model>`: Regularization model (`bending_energy` [default] or `membrane_energy`) [15-17].
  * `--ssqlambda=<0|1>`: Weight regularization parameter $\lambda$ by current sum-of-squares (`1` = yes [default], `0` = no) [17-19].
  * `--splineorder=<2|3>`: B-spline interpolation order (`2` = quadratic, `3` = cubic [default]) [17, 19].
  * `--numprec=<float|double>`: Hessian representation precision (`double` by default) [17].
  * `--interp=<linear|spline>`: Interpolation model for off-grid evaluation [10, 17].
  * `--scale=<0|1>`: Rescale image intensities to common mean across volumes [18].
  * `--nthr=<int>`: Number of threads for CPU multi-threading [12, 20].
  * `--verbose`: Print diagnostic execution progress [12].

---

#### **EDDY (`eddy_cpu`, `eddy_cuda`, `eddy_openmp`)**
`eddy` corrects eddy current-induced distortions and subject movement in diffusion-weighted images [21-24].

* **Compulsory / Main Inputs:**
  * `--imain=<file>`: Path to the 4D input DWI series [21, 24, 25].
  * `--mask=<file>`: 3D binary brain mask in diffusion space [21, 24, 25].
  * `--acqp=<file>`: Acquisition parameters file (same format as `topup` `--acqp`) [6, 21, 24, 25].
  * `--index=<file>`: Text file containing 1-based indices mapping each DWI volume to a line in `--acqp` [21, 24, 26].
  * `--bvecs=<file>`: Text file containing normalized gradient directions ($3 \times N$) [21, 24, 25, 27].
  * `--bvals=<file>`: Text file containing $b$-values ($1 \times N$) [21, 24, 25].
  * `--out=<basename>`: Basename for all output files [21, 24, 25, 28, 29].
* **Secondary Input & Distortion Model Options:**
  * `--topup=<basename>`: Results basename from a prior `topup` run [1, 21, 25, 30, 31].
  * `--field=<file>`: TOPUP/GE off-resonance fieldmap in Hz [32, 33].
  * `--json=<file>` / `--slspec=<file>`: JSON metadata or text file specifying exact slice acquisition order/times (required for slice-to-volume motion correction) [21, 25, 30, 34, 35].
* **Correction Flags & Parameters:**
  * `--flm=<linear|quadratic|cubic>`: First-level spatial model for eddy current fields (default: `quadratic`) [24, 28, 29].
  * `--slm=<none|linear|quadratic>`: Second-level model linking diffusion gradients to eddy currents (default: `none`) [24, 28, 35].
  * `--niter=<int>`: Number of estimation iterations (e.g., `5` or `8`) [21, 24, 36].
  * `--fwhm=<values>`: Filter widths (mm) applied per iteration (e.g., `10,8,4,2,0,0,0,0`) [21, 28, 31, 36].
  * `--repol`: Detect and replace outlier slices using Gaussian Process predictions [21, 36-39].
  * `--ol_type=<sw|gw|both>`: Outlier detection scope across slice-wise (`sw`), group-wise (`gw`), or both [21, 25, 40].
  * `--ol_pos` / `--ol_sqr`: Detect positive-only intensity drops or squared difference outliers [41].
  * `--mporder=<int>`: Movement parameter order for slice-to-volume intra-volume motion correction [21, 34, 36].
  * `--s2v_niter=<int>` / `--s2v_lambda=<val>` / `--s2v_interp=<trilinear|spline>`: Iterations, regularization weight, and interpolation for slice-to-volume correction [21, 34].
  * `--estimate_move_by_susceptibility`: Estimate dynamic changes in susceptibility fields caused by head motion [36, 42].
  * `--cnr_maps`: Generate 4D SNR ($b=0$) and CNR ($b>0$) maps [38, 43, 44].
  * `--residuals`: Output 4D residual error image [33, 39].
  * `--dont_peas`: Disable post-eddy alignment of shells [43, 45].
  * `--dont_sep_offs_move`: Do not separate field offset from subject translation [43].
  * `--data_is_shelled`: Bypass internal heuristics that enforce strict $b$-value shell acquisition [44, 46-48].
  * `--session=<file>`: Text file containing session indices for multi-session datasets [39].
  * `--ff=<float>`: Fudge factor for hyperparameter error variance (default: `10.0`) [24, 31].
  * `--interp=<spline|trilinear>`: Interpolation model during estimation [24, 48].
  * `--resamp=<jac|lsr>`: Final resampling method: Jacobian modulation (`jac`) or Least-Squares Resampling (`lsr`) [10, 24].
  * `--nvoxhp=<int>`: Number of voxels used to sample hyperparameters (default: `1000`) [24, 44].
  * `--nthr=<int>`: Number of CPU threads (for `eddy_cpu` / `eddy_openmp`) [22, 49].
  * `--verbose` / `--very_verbose`: Screen output verbosity [49, 50].

---

#### **BEDPOSTX (`bedpostx` / `xfibres`)**
`bedpostx` runs Markov Chain Monte Carlo (MCMC) sampling to estimate crossing fiber distributions per voxel [51-53].

* **Usage Syntax:** `bedpostx <subject_directory> [options]` [53, 54]
  * *Requires in input directory:* `data.nii.gz`, `nodif_brain_mask.nii.gz`, `bvals`, `bvecs` [54-56].
* **Flags & Options:**
  * `-n <int>`: Maximum number of fibers modeled per voxel (default: `3`) [57, 58].
  * `-w <float>` / `--ardweight=<float>`: Automatic Relevance Determination (ARD) weight (higher values penalize secondary fibers; default: `1`) [58].
  * `-b <int>` / `--burnin=<int>`: Number of burn-in MCMC samples (default: `1000`) [58].
  * `-j <int>` / `--njumps=<int>`: Total number of MCMC jumps/samples (default: `1250`) [58].
  * `-s <int>` / `--sampleevery=<int>`: Sampling interval / thin factor (default: `25`) [58, 59].
  * `-model <1|2|3>`: Diffusion model type: `1` = monoexponential sticks; `2` = Gamma-distributed diffusivities [default]; `3` = zeppelins [51, 52, 58].
  * `-g` / `--gradnonlin`: Account for gradient non-linearities (expects `grad_dev` in subject directory) [54, 58].
  * `--noard`: Turn off Automatic Relevance Determination [58].
  * `--cnonlinear`: Initialize MCMC using non-linear model fitting [58, 60].
  * `--rician`: Use Rician noise modeling [60].
  * `--seed=<int>`: Pseudo-random number generator seed [59].
  * `--updateproposalevery=<int>`: Jumps per proposal density std update (default: `40`) [59].
  * `bedpostx_gpu`: Executable for GPU-accelerated execution [51, 54, 59, 61].
  * `bedpostx_datacheck`: Command-line sanity check for input directory contents [56, 57].

---

#### **PROBTRACKX (`probtrackx` / `probtrackx2`)**
`probtrackx` calculates probabilistic fiber connectivity distributions using `bedpostx` outputs [51, 62, 63].

* **Core Inputs & Execution Modes:**
  * `-m <file>`, `--mask=<file>`: Binary mask file in diffusion space [63-65].
  * `-s <file>`, `--samples=<basename>`: Basename of bedpostx samples (default: `merged`) [63].
  * `--seed=<file|coords>`: Seed volume, binary mask, list of coordinates, or surface label [63, 65].
  * `--mode=<simple|seedmask|twomask_symm>`: Tracking mode [63, 66].
  * `-o <dir>`, `--dir=<dir>`: Output directory name [63].
* **Tracking Parameters:**
  * `--nsamples=<int>` / `-n <int>`: Number of Monte Carlo streamlines generated per seed voxel (default: `5000`) [63, 66].
  * `--nsteps=<int>`: Maximum number of steps per streamline (default: `2000`) [63, 66].
  * `--steplength=<float>`: Step size in mm (default: `0.5`) [67, 68].
  * `--cthr=<float>` / `--distthresh=<float>`: Curvature threshold (cosine of maximum allowed angle) [69, 70].
  * `--fibthresh=<float>`: Minimum volume fraction $f$ threshold for choosing fiber orientations (default: `0.01`) [70, 71].
  * `--usef`: Constrain tracking using fiber volume fractions [72, 73].
  * `--loopcheck`: Perform self-intersection loop checks to discard looping paths [70, 74].
  * `--modeuler`: Use modified Euler integration instead of Euler method [66, 75].
  * `--stop=<file>`: Stop mask; streamlines terminate upon entering this mask [67, 68].
  * `--waypoints=<file>`: Waypoint mask or text file listing masks; retains paths passing through waypoints [72].
  * `--waycond=<AND|OR>`: Logical condition across waypoint masks (default: `AND`) [73].
  * `--wayorder`: Reject streamlines that do not traverse waypoints in specified list order [73].
  * `--avoid=<file>` / `--exclude=<file>`: Exclusion mask; discards streamlines entering this region [76, 77].
  * `--targetmasks=<file>`: Text file listing target masks for seeds-to-targets classification [63, 67].
* **Matrix & Network Options:**
  * `--matrix1`, `--matrix2`, `--matrix3`: Output voxel-by-voxel connectivity matrices [78].
  * `--target2=<file>`: Low-resolution reference mask for storing connectivity in `--matrix2` mode [68].
  * `--network`: Network mode; only keeps paths connecting at least two seed masks [75].
  * `--s2tastext`: Save seed-to-target counts as plain text files [71, 79].
  * `--randfib=<0|1|2|3>`: Random fiber selection strategy (`0` = default, `1` = random $f > \text{fibthresh}$, `2` = proportional to $f$, `3` = all populations) [71, 79].
  * `--rseed=<int>`: Seed for random number generator [71, 79].
  * `--xfm=<file>` / `--invxfm=<file>`: FLIRT matrix or FNIRT warpfield mapping seed space to DTI space [63, 72, 74].
  * `--mesh=<file>`: FreeSurfer surface mesh file in ASCII format [74].
  * `--opd`: Save output path density maps (`fdt_paths.nii.gz`) [63].
  * `--os2t`: Output seed-to-target maps [63].

---

### 2. FSL Statistical Tools

#### **randomise (`randomise`)**
`randomise` performs non-parametric permutation testing for General Linear Models on 3D/4D neuroimaging data [80-82].

* **Compulsory Options:**
  * `-i <file>`: Input 4D dataset (e.g., concatenated subject maps) [82-84].
  * `-o <prefix>`: Output file prefix [82-84].
  * `-d <file>`: GLM design matrix (`design.mat` in VEST or ASCII format) [80, 82-84].
  * `-t <file>`: $t$-contrasts file (`design.con`) [80, 82-84].
* **Contrasts & Masking Options:**
  * `-f <file>`: $F$-contrasts file (`design.fts`) [80, 83, 85].
  * `-m <file>`: 3D binary brain mask image [82-85].
  * `-e <file>`: Exchangeability blocks / repeated measures design file (`design.grp`) [86-88].
* **Permutations & Demeaning:**
  * `-n <int>`: Number of permutations (default: `5000`; set to `0` for exhaustive testing) [83, 86, 89].
  * `-1`, `--one_sample_group_mean`: Perform 1-sample group-mean test with sign-flipping [89].
  * `-D`: Demean data and design matrix columns prior to testing [84, 90].
  * `--seed=<int>`: Specific integer seed for pseudo-random number generator [91].
* **Multiple Comparison Correction & Thresholding Flags:**
  * `-T`, `--tfce`: Enable Threshold-Free Cluster Enhancement (TFCE) [83, 84, 88].
  * `--tfce2D`: Set TFCE parameters for 2D data (TBSS or surface: $H=2, E=1, C=26$) [92].
  * `-c <thresh>`: Cluster-extent thresholding for $t$-contrasts [93].
  * `-C <thresh>`: Cluster-mass thresholding for $t$-contrasts [93].
  * `-F <thresh>`: Cluster-extent thresholding for $F$-contrasts [85, 93].
  * `-S <thresh>`: Cluster-mass thresholding for $F$-contrasts [85, 93].
  * `--fonly`: Calculate $F$-statistics only [85, 90].
  * `-v <mm>`: Carry out variance smoothing with Gaussian kernel FWHM (mm) [94].
  * `-x`: Output voxelwise $1-p$ uncorrected statistic maps.
* **Output Diagnostics & Parallelization:**
  * `-R`, `--raw_stats_imgs`: Output raw (unpermuted) statistic images [91].
  * `-P`, `--p_vec_n_dist_files`: Output permutation vector and null distribution text files [89].
  * `-q`: Print total unique permutations available and exit [91].
  * `-Q`: Print cluster parallel mode submission info and exit [91].

---

#### **PALM (`palm`)**
PALM (Permutation Analysis of Linear Models) handles surface/volume data, multi-modality joint inference, and complex exchangeability trees [95-98].

* **Main Input & Design Arguments:**
  * `-i <file>`: Input dataset (NIfTI, GIFTI, CIFTI, CSV); multiple `-i` options allow multi-modality testing [99-102].
  * `-d <file>`: Design matrix (`.mat`, `.csv`, or VEST) [103, 104].
  * `-t <file>`: $t$-contrasts file (`.con`, `.csv`, or VEST); multiple `-t` allowed [103, 104].
  * `-f <file>`: $F$-contrasts file (`.fts`, `.csv`, or VEST); multiple `-f` allowed [103, 104].
  * `-fonly`: Run $F$-contrasts only [103, 104].
  * `-m <file>`: Mask file(s) corresponding to inputs [100, 102].
  * `-s <surf> [area]`: Surface file and optional vertex/face area file for 2D spatial stats [100, 102, 105].
  * `-eb <file>`: Exchangeability blocks structure file [86, 101, 103, 106].
  * `-within`, `-whole`: Run within-block and/or whole-block permutations [86, 87].
  * `-ee` / `-ise`: Specify Exchangeable Errors (permutations) or Independent & Symmetric Errors (sign-flips) [86, 87, 99, 107].
  * `-vg <file>` / `-vg auto`: Define variance groups for heteroscedastic data [87, 108].
* **Statistical Inference & Multiple Testing:**
  * `-n <int>`: Number of permutations (`0` = exhaustive; default: `10000`) [86, 87, 103, 109].
  * `-T`: Enable TFCE inference [92, 105].
  * `-tfce1D`, `-tfce2D`: Set 1D ($H=2, E=2, C=6$) or 2D ($H=2, E=1, C=26$) TFCE parameters [92, 110].
  * `-C <z_thresh>`: Cluster-forming threshold equivalent $z$-score [92, 95].
  * `-Cstat <extent|mass>`: Choose cluster extent or cluster mass statistic [92].
  * `-npcmethod <method>`: Non-Parametric Combination function (`Fisher`, `Tippett`, `Stouffer`, `Wilkinson`, `Edgington`, `Zaykin`, etc.) [97, 108].
  * `-npcmod` / `-npccon`: Enable NPC combination across modalities or contrasts [108].
  * `-corrmod` / `-corrcon`: FWER-correction across modalities or contrasts [92, 99, 111].
  * `-fdr`: Compute FDR-adjusted $p$-values [92].
  * `-o <prefix>`: Output file prefix [92, 95, 109, 112, 113].
  * `-save1-p`: Output $1-p$ maps [92, 95, 112].
  * `-logp`: Output $-\log_{10}(p)$ maps [92, 105, 112].
  * `-demean`: Mean-center data and design columns [92].
  * `-twotail`: Perform two-tailed hypothesis tests [92].
  * `-accel <negbin|tail|noperm|gamma|lowrank>`: Speed-up acceleration algorithms [92, 114-116].
  * `-seed <int|twist>`: Pseudo-random generator seed [117].
  * `-quiet`: Suppress progress output [92].

---

#### **GLM / `fsl_glm`**
`fsl_glm` fits a GLM design matrix to time series or spatial data via linear regression [81, 118].

* **Command Flags:**
  * `-i <file>`: Input 3D/4D image or text matrix [119].
  * `-d <file>`: Design matrix file (text or image) [119].
  * `-c <file>`: Matrix of $t$-statistic contrasts [120].
  * `-m <file>`: Binary brain mask image [121].
  * `-o <file>`: Output file name for estimated GLM parameter estimates ($\beta$ maps) [119].
  * `--out_p=<file>`: Save $p$-value maps.
  * `--out_z=<file>`: Save $z$-score maps.
  * `--out_t=<file>`: Save $t$-statistic maps.
  * `--out_f=<file>`: Save $F$-statistic maps.
  * `--out_res=<file>`: Save residual timecourses.
  * `--out_varcb=<file>`: Save variance of contrast estimates.
  * `--demean`: Demean design matrix and data time series [120].
  * `--dat_norm`: Normalize data time series to unit standard deviation [120].
  * `--des_norm`: Normalize design matrix columns to unit standard deviation [121].
  * `--dof=<int>`: Explicitly set degrees of freedom [121].

---

### 3. FSL Spectroscopy Tools (FSL-MRS)

#### **FSL-MRS Wrapper (`fsl_mrs`)**
`fsl_mrs` fits basis sets to Single Voxel Spectroscopy (SVS) data [122-124].

* **Required Arguments:**
  * `--data <file>`: Input NIfTI-MRS SVS dataset [124, 125].
  * `--basis <file|dir>`: Basis spectra set (JSON or directory) [122, 124, 125].
  * `--output <folder>`: Output results directory [124, 125].
* **Model & Spectral Fitting Options:**
  * `--algo <Newton|MH>`: Optimization algorithm [124].
  * `--ignore <metab>` / `--keep <metab>` / `--combine <metab>`: Exclude, retain, or combine specific metabolite basis spectra [124].
  * `--ppmlim <low> <high>`: Spectral fitting range limits in PPM (e.g., `0.2 4.2`) [124].
  * `--h2o <file>`: Water reference dataset for phase/shift/quantification [124].
  * `--baseline <type_or_order>`: Baseline fitting model [124].
  * `--metab_groups <groups>`: Group metabolites for independent lineshape/broadening parameters [124].
  * `--lorentzian`: Enforce pure Lorentzian lineshape [124].
  * `--free_shift`: Enable independent frequency shifts per metabolite [124].
  * `--ind_scale <scale>`: Individual metabolite scaling [124].
  * `--disable_MH_priors`: Turn off priors during Metropolis-Hastings fitting [124].
  * `--mh_samples <int>`: Number of Metropolis-Hastings MCMC samples [124].
* **Quantification & Structural Flags:**
  * `--t1 <image>`: Structural T1-weighted image for tissue fraction estimation [124].
  * `--TE <ms>` / `--TR <s`>: Sequence Echo Time and Repetition Time [124].
  * `--tissue_frac <WM GM CSF|file>`: Volume fractions of White Matter, Gray Matter, and CSF [125].
  * `--t1-values <file>` / `--t2-values <file>`: Tissue $T_1$ and $T_2$ relaxation constants [125].
  * `--internal_ref <metab>`: Internal reference metabolite (e.g., Creatine) [125].
  * `--wref_metabolite <metab>`: Water reference metabolite [125].
  * `--ref_protons <int>` / `--ref_int_limits <low> <high>`: Reference proton counts and integration limits [125].
  * `--h2o_scale <float>`: Water scaling factor [125].
* **Execution & Output Options:**
  * `--report`: Output interactive HTML report [122, 125].
  * `--verbose`: Print detailed logs [125].
  * `--overwrite`: Overwrite existing outputs [125].
  * `--conj_fid` / `--no_conj_fid`: Force/forbid conjugation of FID [125].
  * `--conj_basis` / `--no_conj_basis`: Force/forbid conjugation of basis set [125, 126].
  * `--no_rescale`: Forbid internal rescaling of FID/basis/water [126].
  * `--config <file>`: Configuration option text file [126].

---

#### **Processing Tool (`fsl_mrs_proc`)**
`fsl_mrs_proc` executes modular preprocessing steps on MRS data [122, 127].

* **Command Syntax:** `fsl_mrs_proc <subcommand> [options]` [127]
* **Available Subcommands:**
  * `coilcombine`: Combine multi-channel receiver coil signals [122, 127].
  * `average`: Average FID repetitions [127].
  * `align`: Spectral alignment via registration [122, 127].
  * `align-diff`: Align edited spectral differences [127].
  * `ecc`: Eddy current correction using water reference [127].
  * `remove`: Remove unwanted residual signals [127].
  * `model`: Model spectral components [127].
  * `tshift`: Time-shift FID points [127].
  * `truncate`: Truncate FID data points [127].
  * `apodize`: Apply exponential/Gaussian apodization filtering [127].
  * `fshift`: Apply frequency shift [127].
  * `unlike`: Discard bad/outlier averages [127].
  * `phase` / `fixed_phase`: Zero/first-order phase correction [127].
  * `subtract` / `add`: Perform FID subtraction or addition [127, 128].
  * `conj`: Conjugate FID data [127, 128].
  * `mrsi-align`: Align phase/frequency across MRSI spatial grid voxels [127, 128].
  * `mrsi-lipid`: Remove lipid contamination in MRSI via $L_2$ regularization [127, 128].

---

#### **Pipeline Preprocessing (`fsl_mrs_preproc` / `fsl_mrs_preproc_edit`)**
Batch scripts that execute consensus-recommended SVS preprocessing pipelines [122, 129, 130].

* **Required Arguments:**
  * `--data <files>`: Raw non-water-suppressed/suppressed FID input files [129, 130].
  * `--reference <file>`: Non-water suppressed reference file [129, 130].
  * `--output <folder>`: Output directory [129, 130].
* **Flags & Options:**
  * `--quant <file>`: Water reference data for quantification [129, 130].
  * `--ecc <file>`: Water reference data for eddy current correction [129, 130].
  * `--noise <file>`: Noise measurement dataset for coil covariance estimation [129, 130].
  * `--fmrs`: Functional MRS mode (automatically sets `--noremoval` and `--noaverage`) [126, 131].
  * `--noremoval`: Do not discard unlike/outlier averages [126, 131].
  * `--noaverage`: Retain individual repetitions without averaging [126, 131, 132].
  * `--noalign`: Disable dynamic frame alignment [126, 131, 132].
  * `--align_limits <low> <high>`: PPM spectral window for alignment (default: `0.2 4.2`) [126, 131].
  * `--align_window <size>`: Alignment window size for low-SNR data [126, 131].
  * `--align_ppm_dynamic`, `--align_window_dynamic`, `--align_ppm_edit`: Advanced dynamic alignment options for edited MRS [132].
  * `--dynamic_align`, `--dynamic_align_edit`, `--dynamic_basis`: Dynamic alignment options [132].
  * `--remove-water`: Remove residual water peak using HLSVD [126, 131, 132].
  * `--truncate-fid <points>`: Remove initial points from the FID [126, 131, 132].
  * `--t1 <image>`: T1 structural image [126, 132].
  * `--conjugate`: Force phase conjugation [126, 132].
  * `--report`: Generate HTML report [126, 132].
  * `--overwrite`: Overwrite existing files [126, 132].
  * `--config <file>`: Path to configuration file [126, 132].

---

#### **NIfTI-MRS Utilities (`mrs_tools`)**
`mrs_tools` provides command-line manipulation of NIfTI-MRS formatted files [133].

* **Available Subcommands:**
  * `info <file>`: Print header dimensions, intent, and metadata [133].
  * `vis <file>`: Quick visualization of NIfTI-MRS spectra or basis sets [133].
  * `merge --dim <dim> --files <files>`: Merge NIfTI-MRS files along specified higher dimensions [133].
  * `split --dim <dim> <file>`: Split NIfTI-MRS file along specified higher dimensions [133].
  * `reorder`: Reorder higher data dimensions [124].
  * `reshape`: Reshape higher data dimensions [124].
  * `conjugate`: Phase-conjugate data to match standard conventions [124].

---

#### **Basis Simulation (`fsl_mrs_sim`)**
Simulates density-matrix basis spectra for fitting [122, 128].

* **Positional Argument:**
  * `SEQUENCE`: Path to pulse sequence description file [128].
* **Options:**
  * `-m <metab>` / `-b <file>` / `-s <json>`: Specify target metabolite, text file list, or spin system JSON [128].
  * `-o <folder>`: Output directory [128].
  * `-e <echo_time>`: Echo Time ($TE$) in ms [128].
  * `--parallel` / `--parallel-workers <int>`: Parallelization across workers/cores [128, 134].
  * `--overwrite` / `--verbose` [134].

---

### 4. FSL Utility Tools

#### **Grid Submission Wrapper (`fsl_sub`)**
`fsl_sub` submits tasks to HPC cluster backends (Slurm, SGE) or executes them locally [61, 135-137].

* **Task Execution & Queue Settings:**
  * `args`: Command and arguments to execute [138].
  * `-q <queue>`, `--queue=<queue>`: Target cluster queue/partition (e.g., `long.q`, `gpu`) [137, 139].
  * `-a <arch>`, `--arch=<arch>`: Target CPU architecture [137].
  * `-c {cuda}`, `--coprocessor={cuda}`: Request GPU co-processor execution [137, 140].
  * `-j <jobid>`, `--jobhold=<jobid>`: Hold execution until specified job ID completes [137, 138].
  * `--array_hold=<jobid>`: Hold array tasks on specified job ID [137].
  * `-l <logdir>`, `--logdir=<logdir>`: Directory for stdout/stderr log output files [137].
  * `-m <options>` / `-M <email>`: Mail notifications settings and address [137].
  * `-N <name>`, `--jobname=<name>`: Job identifier name in queue [137].
  * `-p <int>`, `--priority=<int>`: Job priority [137].
  * `-R <GB>`, `--resource=<GB>` / `--memory=<GB>`: Total RAM requested in Gigabytes [137].
  * `-s [threads,]SLOTS`, `--parallelenv`: Requested parallel environment threads/slots [137, 141].
  * `-T <minutes>`, `--time=<minutes>`: Maximum job walltime limit in minutes [137].
  * `-t <file>`, `--array_task=<file>`: Submit array job using task list file [137].
  * `-x <int>`, `--array_limit=<int>`: Max number of array sub-tasks running concurrently [137, 142].
  * `--extra="<args>"`: Pass raw extra flags directly to underlying scheduler (e.g. `--extra "--qos=deadline"`) [137, 141].
  * `--keep_jobscript`: Generate and preserve wrapper shell script (`wrapper_.sh`) [137, 142].
  * `--delete_job=<jobid>`: Cancel/delete running or queued job ID [137, 141].
  * `--has_coprocessor`, `--has_queues`, `--show_config`: Query `fsl_sub` configuration and cluster capabilities [137, 140, 143].

---

#### **Image Mathematics (`fslmaths`)**
`fslmaths` allows arithmetic, spatial, temporal, and morphological image processing [144-146].

* **Usage Syntax:** `fslmaths [-dt <datatype>] <input> [operations] <output> [-odt <datatype>]` [144]
* **Datatype Specification:**
  * `-dt <type>`: Precision for internal calculations (`char`, `short`, `int`, `float` [default], `double`, `input`) [144, 147].
  * `-odt <type>`: Output volume data precision (`char`, `short`, `int`, `float`, `double`, `input`) [144, 148].
* **Arithmetic & Basic Logic:**
  * `-add <file|val>`: Add image or scalar constant [149-151].
  * `-sub <file|val>`: Subtract image or scalar constant [149, 151].
  * `-mul <file|val>`: Multiply by image or scalar constant [149, 150, 152].
  * `-div <file|val>`: Divide by image or scalar constant [149-151, 153].
  * `-rem <file|val>`: Modulus remainder division [149].
  * `-mas <file>`: Apply binary mask [154].
  * `-max <file|val>` / `-min <file|val>`: Voxelwise maximum or minimum comparison [149].
* **Unary Mathematical Operations:**
  * `-exp`, `-log`, `-sqr`, `-sqrt`, `-recip`, `-abs`: Exponential, natural log, square, square root, reciprocal, or absolute value [151, 155].
  * `-sin`, `-cos`, `-tan`, `-asin`, `-acos`, `-atan`: Trigonometric operators [155].
  * `-bin`: Binarize image (voxels $>0$ set to $1$) [155].
  * `-binv`: Binarize inverted (voxels $>0$ set to $0$; voxels $\le 0$ set to $1$) [155].
  * `-nan`: Convert NaN voxels to 0 [155-157].
  * `-nanm`: Create binary mask of NaN voxels [155].
* **Spatial Filtering & Morphology:**
  * `-kernel <3D|2D|box|sphere|gauss>`: Set morphological structuring element or smoothing kernel.
  * `-dilM` / `-dilD` / `-dilF`: Dilate mask using modal, mean, or maximum filtering [158].
  * `-ero` / `-eroF`: Erode mask image [159].
  * `-fmean` / `-fmedian`: Apply 3D mean or median spatial filter.
  * `-s <sigma_mm>`: Smooth image with Gaussian kernel of standard deviation $\sigma$ (in mm) [145].
  * `-subsamp2`: Subsample image dimensions by a factor of 2.
* **Temporal Filtering & Statistics:**
  * `-bptf <hp_sigma> <lp_sigma>`: Highpass and lowpass bandpass temporal filtering in TR volumes.
  * `-Tmean`, `-Tstd`, `-Tmin`, `-Tmax`, `-Tmedian`: Compute mean, std, min, max, or median along 4th dimension.
  * `-Tmaxn`: Output 3D volume containing index of maximum value along 4th dimension [160].
* **Thresholding & Normalization:**
  * `-thr <val>`: Set voxels below threshold value to zero [161].
  * `-uthr <val>`: Set voxels above upper threshold value to zero.
  * `-inm <target_mean>`: Intensity normalize 4D volume to global target mean.
  * `-tfce <H> <E> <C>`: Compute Threshold-Free Cluster Enhancement map [145].

---

#### **Summary Statistics (`fslstats`)**
`fslstats` calculates summary statistics across 3D/4D volumes [162, 163].

* **Usage Syntax:** `fslstats [-t] <input> [options]` [163, 164]
* **Options & Flags:**
  * `-t`: Evaluate statistics separately for each 3D volume in a 4D timeseries [164].
  * `-k <mask>`: Calculate statistics only within non-zero voxels of mask image [162, 164].
  * `-l <lower>` / `-u <upper>`: Set lower and upper intensity thresholds for voxel selection.
  * `-r`: Report robust intensity range (approx. 2nd and 98th percentiles) [162].
  * `-R`: Report true minimum and maximum voxel intensities [162].
  * `-m`: Report mean of non-zero voxels [163, 165].
  * `-M`: Report mean of all voxels [163].
  * `-s`: Report standard deviation of non-zero voxels [165].
  * `-S`: Report standard deviation of all voxels.
  * `-w`: Report center of mass in voxel coordinates.
  * `-W`: Report center of mass in world/mm coordinates.
  * `-v`: Report total volume in voxels and mm$^3$.
  * `-V`: Report non-zero volume in voxels and mm$^3$.
  * `-p <n>`: Report $n$-th percentile intensity.
  * `-P <n>`: Report $n$-th percentile intensity of non-zero voxels.
  * `-a`: Operate on absolute values of voxel intensities.
  * `-h <nbins>`: Output histogram across $n$ bins [162].
  * `-H <nbins> <min> <max>`: Output histogram across $n$ bins between specified bounds.
  * `-e` / `-E`: Report image entropy or non-zero entropy.
  * `-x` / `-X`: Report voxel coordinates corresponding to min/max intensities.

---

#### **Mean Time Series Extraction (`fslmeants`)**
`fslmeants` extracts average timeseries from 4D datasets [162, 166].

* **Usage Syntax:** `fslmeants -i <input_4D> [options]` [166]
* **Options:**
  * `-i <file>`: Input 4D timeseries dataset [166].
  * `-o <file>`: Output text file for extracted timeseries (prints to terminal if omitted) [166].
  * `-m <file>`: Binary mask image; computes mean timecourse across mask voxels [162, 166].
  * `-c <x y z>`: Extract timeseries from specific voxel coordinate ($x, y, z$).
  * `--usemm`: Interpret `-c` coordinates in mm instead of voxel indices.
  * `--showall`: Output timecourses for all individual voxels in mask rather than taking the average [162].
  * `--label=<atlas_img>`: Compute separate average timecourse for each unique integer label in a 3D atlas/label volume.
  * `--transpose`: Transpose output text matrix.
  * `-v`, `--verbose`: Print diagnostic messages.

---

#### **Image Concatenation (`fslmerge`)**
`fslmerge` concatenates multiple 3D or 4D image volumes along a chosen dimension [167, 168].

* **Usage Syntax:** `fslmerge -<dim> <output> <input1> <input2> ... [tr]` [168, 169]
* **Dimension Flags:**
  * `-t`: Concatenate images along the time / 4th dimension (e.g., merging 3D files into 4D) [167-170].
  * `-x`: Concatenate images along X spatial axis [167, 168].
  * `-y`: Concatenate images along Y spatial axis [167, 168].
  * `-z`: Concatenate images along Z spatial axis [167, 168].
  * `-tr <TR_sec>`: Concatenate along time and specify time Repetition ($TR$) in seconds (e.g., `fslmerge -tr out_4d in1 in2 2.0`) [168].

---

#### **Image Splitting (`fslsplit`)**
`fslsplit` splits a 4D dataset into 3D volumes or 2D slice files [145, 171].

* **Usage Syntax:** `fslsplit <input> [output_basename] -<dim>` [171]
* **Dimension Flags:**
  * `-t`: Split 4D volume into 3D volumes along time dimension [default] [145, 171].
  * `-x`: Split image into 2D/3D slices along X axis [171].
  * `-y`: Split image into 2D/3D slices along Y axis [171].
  * `-z`: Split image into 2D/3D slices along Z axis [171].

---
