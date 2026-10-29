Here is the full breakdown of available functions, classes, and methods across the Nilearn submodules and Masker objects as documented in the notebook sources [1-5].

---

## 1. `nilearn.datasets`: Data Fetchers and Reference Templates

The **`nilearn.datasets`** module provides standardized functions to download, cache, and load widely used neuroimaging datasets, probabilistic atlases, structural/functional templates, and sample activation maps.

### Key Data Fetching & Loading Functions

* **`fetch_haxby(data_dir=None, url=None, resume=True, verbose=1, subjects=[6])`**:
  * **What it does**: Downloads the visual object recognition fMRI dataset by Haxby et al. (2001) [7, 8].
  * **Arguments**: `subjects` (list of subject indices to fetch), `data_dir` (cache folder path), `resume` (boolean to resume interrupted downloads), `verbose` [7].
  * **Use Cases**: Multi-Voxel Pattern Analysis (MVPA), classification benchmarking (face vs. house vs. cat vs. chair), and decoding tutorials [7, 8].

* **`fetch_development_fmri(n_subjects=30, reduce_confounds=True, data_dir=None, verbose=1)`**:
  * **What it does**: Fetches the Movie Watching Brain Development fMRI dataset (children vs. adults) [1, 9]. Returns preprocessed 4D BOLD NIfTI files, confound TSV tables, and phenotypic metadata [1, 9].
  * **Arguments**: `n_subjects` (number of subjects to load), `reduce_confounds` (boolean), `data_dir`, `verbose` [1].
  * **Use Cases**: Group-level functional connectivity analysis, development studies, and connectome classification [1, 9].

* **`fetch_atlas_msdl(data_dir=None, url=None, verbose=1)`**:
  * **What it does**: Downloads the Multi-Subject Dictionary Learning (MSDL) probabilistic atlas (39 functional ROIs across 9 cognitive networks) [1, 10].
  * **Arguments**: `data_dir`, `url`, `verbose` [1].
  * **Use Cases**: Seed-to-voxel connectivity, network-level functional connectome estimation, and ROI time series extraction [1, 10].

* **`fetch_atlas_harvard_oxford(atlas_name, data_dir=None, symmetric_split=False, value_type='labels')`**:
  * **What it does**: Fetches the Harvard-Oxford cortical or subcortical structural atlas (probabilistic or maximum probability thresholded) [11].
  * **Arguments**: `atlas_name` (e.g., `'cort-maxprob-thr25-2mm'`, `'sub-maxprob-thr25-1mm'`), `symmetric_split`, `value_type` [11].
  * **Use Cases**: Anatomical ROI signal extraction, parcellation-based connectomics, and structural localization [11].

* **`fetch_atlas_yeo_2011(data_dir=None, url=None, verbose=1)`**:
  * **What it does**: Downloads the Yeo et al. (2011) cortical parcellation maps based on resting-state fMRI (7-network or 17-network versions) [12, 13].
  * **Arguments**: `n_networks` (7 or 17), `data_dir`, `verbose` [13].
  * **Use Cases**: Network-based connectomics, cortical signal extraction, and parcellation masking [12, 13].

* **`fetch_atlas_difumo(dimension=64, resolution_mm=2, data_dir=None, verbose=1)`**:
  * **What it does**: Fetches the Dictionaries of Functional Modes (DiFuMo) probabilistic atlas at various dimensions (64, 128, 256, 512, 1024 modes).
  * **Arguments**: `dimension` (number of components), `resolution_mm` (2mm or 3mm), `data_dir`.
  * **Use Cases**: High-resolution probabilistic ROI extraction and functional network decomposition.

* **`fetch_atlas_surf_destrieux(data_dir=None, url=None, verbose=1)`**:
  * **What it does**: Fetches the Destrieux cortical surface parcellation atlas in `fsaverage5` surface space [14].
  * **Arguments**: `data_dir`, `url`, `verbose` [14].
  * **Use Cases**: Cortical surface ROI visualization, vertex-level time series extraction, and surface connectomics [14].

* **`load_mni152_template(resolution=2)`**:
  * **What it does**: Loads the MNI152 ICBM T1-weighted anatomical reference template as an in-memory NIfTI image [15].
  * **Arguments**: `resolution` (isotropic resolution in mm: 1 or 2) [15].
  * **Use Cases**: Anatomical background display for statistical overlay plots and image registration target [15].

* **`load_sample_motor_activation_image()`**:
  * **What it does**: Returns a sample 3D statistical t-map of motor activation distributed directly with Nilearn [15, 16].
  * **Arguments**: None [16].
  * **Use Cases**: Rapid testing of plotting functions (`plot_stat_map`, `plot_glass_brain`, `plot_surf_stat_map`) [15, 16].

* **`load_fsaverage(mesh='fsaverage5')`** & **`load_fsaverage_data(data_type='sulcal')`**:
  * **What it does**: Downloads and loads FreeSurfer `fsaverage` surface mesh structures (`pial`, `inflated`, `white`) and associated background morphometry map data (sulcal depth, curvature) [14, 17].
  * **Arguments**: `mesh` (`'fsaverage5'`, `'fsaverage'`), `data_type` (`'sulcal'`, `'curvature'`) [14, 17].
  * **Use Cases**: Surface mesh visualization targets and background shading maps [14, 17].

---

## 2. `nilearn.image`: Image Processing, Spatial Operations, and Arithmetic

The **`nilearn.image`** module provides spatial processing and mathematical operations that operate directly on 3D/4D Niimg-like objects or `SurfaceImage` instances [2].

### Core Functions

* **`smooth_img(imgs, fwhm)`**:
  * **What it does**: Applies 3D or surface Gaussian spatial smoothing with a specified Full-Width at Half-Maximum (FWHM in mm) [18-20].
  * **Arguments**: `imgs` (3D/4D NIfTI or SurfaceImage), `fwhm` (smoothing kernel width in mm or `None`) [18, 19].
  * **Use Cases**: Enhancing signal-to-noise ratio (SNR) and suppressing high-frequency spatial noise prior to statistical analysis [18, 19].

* **`resample_img(img, target_affine=None, target_shape=None, interpolation='continuous', copy=False)`**:
  * **What it does**: Resamples a 3D/4D image onto a new spatial grid defined by a target $4 \times 4$ affine matrix and/or target array shape [20, 21].
  * **Arguments**: `img`, `target_affine`, `target_shape`, `interpolation` (`'continuous'`, `'linear'`, `'nearest'`), `copy` [21].
  * **Use Cases**: Re-grid image spatial resolution, align images across acquisitions, or adjust bounding boxes [21].

* **`resample_to_img(source_img, target_img, interpolation='continuous')`**:
  * **What it does**: Wraps `resample_img` to automatically match the spatial dimensions, grid shape, and voxel orientation of `source_img` to a reference `target_img` [15, 20].
  * **Arguments**: `source_img`, `target_img`, `interpolation` (`'continuous'`, `'nearest'`) [15, 22].
  * **Use Cases**: Matching statistical maps or custom masks to MNI template grids [15, 22].

* **`math_img(formula, copy_header_from=None, **kwargs)`**:
  * **What it does**: Evaluates a mathematical Python/NumPy string expression over input NIfTI images passed as named keyword arguments [23, 24].
  * **Arguments**: `formula` (e.g., `"-np.log10(np.minimum(1, img * 1000))"`), `kwargs` (named NIfTI images) [23, 24].
  * **Use Cases**: Voxelwise image arithmetic, negative log p-value conversions, contrast differences, and image ratio calculations [23].

* **`mean_img(imgs, target_affine=None, target_shape=None)`**:
  * **What it does**: Computes the voxelwise arithmetic mean across time (4D to 3D) or across a list of 3D/4D images [24, 25].
  * **Arguments**: `imgs` (4D NIfTI file or list of 3D NIfTI files), `target_affine`, `target_shape` [25].
  * **Use Cases**: Creating anatomical or functional background underlays for plotting [25].

* **`concat_imgs(niimgs, dtype=None, ensure_ndim=None, auto_resample=False)`**:
  * **What it does**: Concatenates a list of 3D or 4D images along the 4th (time/subject) dimension into a single 4D NIfTI object [24, 26].
  * **Arguments**: `niimgs` (list of images), `dtype`, `ensure_ndim`, `auto_resample` [26].
  * **Use Cases**: Grouping multiple subject volumes or multi-run time series into a single 4D file [26].

* **`index_img(imgs, index)`**:
  * **What it does**: Extracts specific 3D volume slices from a 4D NIfTI image along the last dimension using integer indices, lists, or boolean masks [7, 24].
  * **Arguments**: `imgs` (4D image), `index` (integer, slice, or boolean array) [7, 27].
  * **Use Cases**: Subsetting task fMRI runs to specific trial conditions (e.g., face vs. house trials) [7, 27].

* **`iter_img(imgs)`**:
  * **What it does**: Yields individual in-memory 3D NIfTI image objects sequentially from a 4D image or list of 3D images [24, 28].
  * **Arguments**: `imgs` (4D image) [28].
  * **Use Cases**: Batch processing individual 3D volumes without exhausting memory [28].

* **`clean_img(imgs, runs=None, detrend=True, standardize=True, confounds=None, low_pass=None, high_pass=None, t_r=None)`**:
  * **What it does**: Applies temporal signal cleaning to unmasked 3D/4D image series (detrending, standardization, confound regression, bandpass filtering) [24, 29].
  * **Arguments**: `imgs`, `runs`, `detrend`, `standardize`, `confounds`, `low_pass`, `high_pass`, `t_r` [29].
  * **Use Cases**: Temporal noise reduction on unmasked BOLD image files [29].

* **`threshold_img(img, threshold, cluster_threshold=0, two_sided=True, copy=True)`**:
  * **What it does**: Applies intensity or percentile thresholds to statistical or atlas maps [20, 30]. Discards clusters smaller than `cluster_threshold` [30].
  * **Arguments**: `img`, `threshold` (numeric value or percentile string like `'97%'`), `cluster_threshold` (minimum voxel count), `two_sided` [30].
  * **Use Cases**: Statistical map thresholding and isolated noise removal [30].

* **`binarize_img(img, threshold=0, mask_img=None)`**:
  * **What it does**: Binarizes an image into integer 0 and 1 arrays where values strictly above the threshold become 1 [24].
  * **Arguments**: `img`, `threshold`, `mask_img` [24].
  * **Use Cases**: Creating binary masks from probability maps or thresholded activation maps [24].

* **`crop_img(img, rtol=1e-8, copy=True, pad=True)`**:
  * **What it does**: Crops zero-value or background padding out of an image to produce the tightest bounding box [24].
  * **Arguments**: `img`, `rtol`, `copy`, `pad` [24].
  * **Use Cases**: Reducing memory footprint and file size of masked images [24].

* **`new_img_like(ref_niimg, data, affine=None, copy_header=False)`**:
  * **What it does**: Constructs a new `Nifti1Image` sharing the same affine, header, and spatial dimensions as `ref_niimg`, populated with replacement NumPy array `data` [21, 24].
  * **Arguments**: `ref_niimg`, `data` (NumPy array), `affine`, `copy_header` [21].
  * **Use Cases**: Converting custom NumPy analytical outputs back into valid NIfTI files [21].

* **`get_data(img)`**:
  * **What it does**: Safely extracts image voxel array data as a `numpy.ndarray` [23, 24].
  * **Arguments**: `img` (Niimg object) [23].
  * **Use Cases**: Direct numerical manipulation of voxel intensity arrays [23].

* **`load_img(img, wildcards=True, dtype=None)`**:
  * **What it does**: Converts file paths, glob-style wildcard strings (`'subj*/anat*.nii.gz'`), or existing nibabel objects into in-memory NIfTI images [15, 24].
  * **Arguments**: `img`, `wildcards`, `dtype` [15].
  * **Use Cases**: Standardizing input image loading across file paths and wildcards [15].

* **`high_variance_confounds(imgs, n_confounds=5, percentile=2.0, detrend=True)`**:
  * **What it does**: Identifies and extracts confound time series corresponding to high-variance signals (e.g., CompCor noise components) from unmasked BOLD images [24].
  * **Arguments**: `imgs`, `n_confounds`, `percentile`, `detrend` [24].
  * **Use Cases**: Extracting physiological noise regressors without anatomical tissue segmentation [24].

---

## 3. `nilearn.masking`: Brain Mask Generation and Extraction Utilities

The **`nilearn.masking`** module provides explicit functions to compute binary spatial masks from functional EPI series, anatomical scans, or background intensities, as well as applying masks to transform 4D images into 2D matrices and vice versa [4].

### Core Functions

* **`compute_epi_mask(epi_img, lower_cutoff=0.2, upper_cutoff=0.85, connected=True, opening=2)`**:
  * **What it does**: Computes a binary brain mask from 3D/4D raw functional EPI scans based on image intensity histograms and morphological operations [4, 31, 32].
  * **Arguments**: `epi_img`, `lower_cutoff`, `upper_cutoff`, `connected`, `opening` [31, 32].
  * **Use Cases**: Generating subject-specific functional brain masks directly from EPI BOLD scans [31, 32].

* **`compute_brain_mask(target_img, threshold=0.5, mask_type='whole-brain')`**:
  * **What it does**: Computes whole-brain, gray-matter (`mask_type='gm'`), or white-matter (`mask_type='wm'`) binary masks by resampling MNI template masks into the `target_img` field of view [4].
  * **Arguments**: `target_img`, `threshold`, `mask_type` [4].
  * **Use Cases**: Standard MNI template-based masking tailored to target image geometry [4].

* **`compute_background_mask(data_imgs, opening=2)`**:
  * **What it does**: Generates a brain mask by analyzing background intensity levels sampled from image borders [4, 33].
  * **Arguments**: `data_imgs`, `opening` [33].
  * **Use Cases**: Structural T1w image masking where clear background contrast exists [33].

* **`compute_multi_epi_mask(epi_imgs)` / `compute_multi_brain_mask(target_imgs)` / `compute_multi_background_mask(data_imgs)`**:
  * **What it does**: Computes a consensus binary mask across multiple subjects or runs by taking their spatial intersection or thresholded union [4].
  * **Arguments**: `epi_imgs` / `target_imgs` / `data_imgs` (list of images), `threshold` [4].
  * **Use Cases**: Group-level consensus mask creation across subject cohorts [4].

* **`intersect_masks(mask_imgs, threshold=0.5, connected=True)`**:
  * **What it does**: Computes the spatial intersection of multiple binary masks based on a overlap proportion `threshold` [4].
  * **Arguments**: `mask_imgs` (list of masks), `threshold` (e.g., `0.5` for 50% overlap), `connected` [4].
  * **Use Cases**: Group masking and overlapping ROI construction [4].

* **`apply_mask(imgs, mask_img, dtype=None, smoothing_fwhm=None)`**:
  * **What it does**: Extracts voxel time series from a 3D/4D NIfTI image using `mask_img`, returning a 2D NumPy array of shape (`n_samples`, `n_voxels`) [4].
  * **Arguments**: `imgs`, `mask_img`, `dtype`, `smoothing_fwhm` [4].
  * **Use Cases**: Converting 4D image volumes into 2D matrices for machine learning or signal analysis [4].

* **`unmask(X, mask_img, order='F')`**:
  * **What it does**: Reconstructs 3D/4D NIfTI images from a 1D/2D feature array `X` using the spatial geometry defined by `mask_img` [4, 34].
  * **Arguments**: `X` (NumPy matrix), `mask_img`, `order` [4, 34].
  * **Use Cases**: Mapping decoded weights or model outputs back into 3D MNI brain space [34, 35].

---

## 4. `nilearn.maskers` (including `NiftiMasker` & `SurfaceMasker`)

Masker objects (located in **`nilearn.maskers`**) encapsulate spatial masking, signal extraction, temporal cleaning, and data reduction into scikit-learn-compatible estimator classes implementing `.fit()`, `.transform()`, `.fit_transform()`, and `.inverse_transform()` [3, 36].

### Volumetric and Surface Masker Classes

* **`NiftiMasker`**:
  * **What it does**: Applies a 3D volumetric binary mask to 4D NIfTI images, extracting 2D signal matrices (`n_timepoints` $\times$ `n_voxels`) [3, 31, 37].
  * **Key Parameters**: `mask_img`, `mask_strategy` (`'epi'`, `'background'`, `'whole-brain-template'`, `'gm-template'`), `smoothing_fwhm`, `detrend`, `standardize`, `standardize_confounds`, `high_pass`, `low_pass`, `t_r`, `memory` [31, 37].
  * **Use Cases**: Single-subject voxelwise signal extraction, MVPA decoding, ICA/PCA decomposition [31, 37, 38].

* **`SurfaceMasker`**:
  * **What it does**: Operates directly on `SurfaceImage` objects, extracting vertex-level cortical signals while supporting surface-based detrending and temporal filtering [3, 39].
  * **Key Parameters**: `mask_img`, `smoothing_fwhm`, `standardize`, `detrend`, `high_pass`, `low_pass`, `t_r` [39].
  * **Use Cases**: Surface-based MVPA, vertexwise decoding, and cortical time series analysis [39].

* **`NiftiLabelsMasker`**:
  * **What it does**: Extracts mean (or median) time series from discrete, non-overlapping parcellation atlases (e.g., Harvard-Oxford, Yeo 17-network) [3, 40].
  * **Key Parameters**: `labels_img`, `background_label`, `strategy` (`'mean'`, `'median'`), `resampling_target`, `standardize_confounds` [40].
  * **Use Cases**: ROI time series extraction for discrete atlases, ROI-to-ROI functional connectomics [40].

* **`NiftiMapsMasker`**:
  * **What it does**: Extracts region signals from overlapping, continuous, or 4D probabilistic atlases (e.g., MSDL, DiFuMo, ICA components) via spatial regression [1, 3, 41].
  * **Key Parameters**: `maps_img`, `mask_img`, `allow_overlap=True`, `resampling_target`, `high_variance_confounds` [1, 41, 42].
  * **Use Cases**: Component-based functional connectivity and time series extraction from probabilistic/overlapping networks [1, 41].

* **`NiftiSpheresMasker`**:
  * **What it does**: Extracts average time series from spherical seed regions centered at specified 3D MNI coordinates [3, 43].
  * **Key Parameters**: `seeds` (list of `(x, y, z)` tuples), `radius` (in mm, e.g., `5.0`), `allow_overlap` [43].
  * **Use Cases**: Seed-to-voxel correlation analysis and coordinate-based ROI connectomics [43].

* **`MultiNiftiMasker` / `MultiNiftiLabelsMasker` / `MultiNiftiMapsMasker`**:
  * **What it does**: Multi-subject parallelized versions of `NiftiMasker`, `NiftiLabelsMasker`, and `NiftiMapsMasker` that process lists of subject images simultaneously across CPU cores (`n_jobs`) [3, 44-46].
  * **Key Parameters**: Inherit single-subject parameters plus `n_jobs` [45, 46].
  * **Use Cases**: Batch cohort functional connectivity pipeline execution and large-dataset signal extraction [45, 46].

### Core Masker Methods (Common to all Masker Classes)

* **`.fit(X=None, y=None)`**: Computes spatial masks or loads atlas labels/maps, generating internal transformation metadata [31, 37].
* **`.transform(imgs, confounds=None, sample_mask=None)`**: Extracts signals from 3D/4D images, regressing out `confounds` (motion, CSF/WM) and applying `sample_mask` for frame scrubbing [29, 47].
* **`.fit_transform(imgs, confounds=None, sample_mask=None)`**: Executes `.fit()` and `.transform()` in a single optimized pass [31, 47].
* **`.inverse_transform(X)`**: Takes a 2D feature matrix `X` or 1D array and projects it back into 3D/4D NIfTI or `SurfaceImage` format [34, 35].
* **`.generate_report()`**: Generates an interactive HTML summary report displaying the estimated mask overlaid on background anatomy [31, 42].

---

## 5. `nilearn.plotting`: Publication-Grade Static and Interactive Visualization

The **`nilearn.plotting`** module implements static and web-interactive plotting routines tailored for neuroimaging data [5].

### 1. Static Volumetric & Surface Plotting Functions

* **`plot_anat(anat_img=None, cut_coords=None, display_mode='ortho', title=None, dim='auto')`**:
  * **What it does**: Plots slice cuts of a 3D structural image on a grayscale background [5, 25].
  * **Key Arguments**: `anat_img`, `cut_coords`, `display_mode` (`'ortho'`, `'x'`, `'y'`, `'z'`, `'xz'`, `'lyrz'`), `title` [25].
  * **Use Cases**: Structural scan quality control and anatomical underlay display [25].

* **`plot_epi(epi_img=None, cut_coords=None, display_mode='ortho', cmap='spectral')`**:
  * **What it does**: Plots slice cuts of a 3D/4D mean functional EPI image [5, 25].
  * **Key Arguments**: `epi_img`, `cut_coords`, `display_mode`, `cmap` [25].
  * **Use Cases**: Inspecting low-resolution functional BOLD image contrast and coverage [25].

* **`plot_stat_map(stat_map_img, bg_img=MNI152, cut_coords=None, threshold=1e-6, cmap='RdBu_r', symmetric_cbar='auto', radiological=False)`**:
  * **What it does**: Plots color-coded statistical activation maps overlaid on top of an anatomical background image [5, 16, 30].
  * **Key Arguments**: `stat_map_img`, `bg_img`, `cut_coords`, `threshold`, `cmap`, `radiological` [16, 25, 30].
  * **Use Cases**: Displaying GLM z-score/t-score maps or decoding weight maps [16, 30].

* **`plot_glass_brain(stat_map_img, display_mode='ortho', threshold='auto', plot_abs=True, black_bg=False)`**:
  * **What it does**: Computes Maximum Intensity Projections (MIP) onto 2D glass brain schematics [5, 16, 48].
  * **Key Arguments**: `stat_map_img`, `display_mode` (`'ortho'`, `'xz'`, `'yz'`, `'lyrz'`, `'lr'`), `threshold`, `plot_abs`, `black_bg` [16, 49].
  * **Use Cases**: Summary visualization of brain-wide activation foci without slice selection [16, 49].

* **`plot_roi(roi_img, bg_img=MNI152, cut_coords=None, view_type='continuous', alpha=0.7)`**:
  * **What it does**: Plots region-of-interest contour/solid color overlays on an anatomical background [5, 25].
  * **Key Arguments**: `roi_img`, `bg_img`, `cut_coords`, `alpha` [25].
  * **Use Cases**: Visualizing binary brain masks or anatomical ROI boundaries [25].

* **`plot_prob_atlas(maps_img, bg_img=MNI152, view_type='auto', threshold='auto')`**:
  * **What it does**: Plots 4D probabilistic atlas maps overlaid on anatomical templates [5].
  * **Key Arguments**: `maps_img`, `bg_img`, `view_type` (`'contours'`, `'filled_contours'`, `'continuous'`) [5].
  * **Use Cases**: Visualizing overlapping probabilistic functional networks (e.g., MSDL) [5].

* **`plot_connectome(adjacency_matrix, node_coords, node_color='auto', node_size=50, edge_threshold=None, edge_cmap='RdBu_r')`**:
  * **What it does**: Plots functional connectome graph edges and nodes over 3D glass brain schematics [5, 47, 50].
  * **Key Arguments**: `adjacency_matrix` ($N \times N$), `node_coords` ($N \times 3$), `edge_threshold` (e.g., `'90%'`), `edge_cmap` [47, 50].
  * **Use Cases**: Functional connectome network visualization [47, 50].

* **`plot_matrix(mat, title=None, labels=None, vmin=-1, vmax=1, cmap='RdBu_r', reorder=False, tri='lower')`**:
  * **What it does**: Displays 2D covariance, correlation, or precision matrices as heatmaps [1, 5, 43].
  * **Key Arguments**: `mat`, `title`, `labels`, `vmin`, `vmax`, `reorder`, `tri` [1, 51].
  * **Use Cases**: Visualizing pairwise ROI connectivity matrices [1, 51].

* **`plot_markers(node_values, node_coords, node_cmap=cm.YlOrRd, title=None)`**:
  * **What it does**: Plots spherical node markers sized/colored by nodal strength over glass brain schematics [5].
  * **Key Arguments**: `node_values` (1D vector), `node_coords`, `node_cmap` [5].
  * **Use Cases**: Visualizing nodal centrality or region-level summary metrics [5].

* **`plot_surf_stat_map(stat_map, surf_mesh='fsaverage5', hemi='left', view='lateral', bg_map=None, threshold=None, engine='matplotlib')`**:
  * **What it does**: Projects statistical maps or surface images onto 3D cortical meshes [5, 14, 52, 53].
  * **Key Arguments**: `stat_map`, `surf_mesh`, `hemi` (`'left'`, `'right'`, `'both'`), `view` (`'lateral'`, `'medial'`, `'ventral'`), `bg_map`, `threshold`, `engine` (`'matplotlib'`, `'plotly'`) [17, 52].
  * **Use Cases**: Surface-based activation mapping and cortical surface connectivity visualization [14, 52].

* **`plot_surf_roi(roi_map, surf_mesh='fsaverage5', hemi='left', view='lateral', bg_map=None)`**:
  * **What it does**: Plots surface parcellation atlas maps on cortical meshes [5, 54].
  * **Key Arguments**: `roi_map`, `surf_mesh`, `hemi`, `view`, `bg_map` [54].
  * **Use Cases**: Displaying surface ROIs or atlas parcels (e.g., Destrieux atlas) [54].

* **`plot_surf_contours(roi_map, hemi='left', labels=None, levels=None, figure=None)`**:
  * **What it does**: Draws delineated ROI boundary contour curves on top of existing surface figures [5, 55, 56].
  * **Key Arguments**: `roi_map`, `hemi`, `labels`, `levels`, `figure` [55].
  * **Use Cases**: Overlaying cortical parcellation outlines on surface activation maps [55].

* **`plot_design_matrix(design_matrix, rescale=True)`** & **`plot_contrast_matrix(contrast_def, design_matrix)`**:
  * **What it does**: Visualizes GLM design matrices as heatmaps and plots contrast vector weights [5, 57-59].
  * **Key Arguments**: `design_matrix`, `contrast_def`, `rescale` [57-59].
  * **Use Cases**: GLM design specification inspection and quality control [57, 59].

* **`plot_carpet(img, mask_img=None, detrend=True, t_r=None)`**:
  * **What it does**: Plots voxel intensity heatmaps across time (raster/carpet plot) for quality control [5].
  * **Key Arguments**: `img` (4D fMRI image), `mask_img`, `detrend`, `t_r` [5].
  * **Use Cases**: QC inspection for head motion artifacts and global signal drifts [5].

### 2. Interactive HTML Visualization Functions

* **`view_img(stat_map_img, bg_img='MNI152', threshold=1e-6, cmap='RdBu_r', width_view=600, opacity=1.0)`**:
  * **What it does**: Generates an interactive Brainsprite 3D slice viewer for volumetric statistical maps [5, 25, 60].
  * **Key Arguments**: `stat_map_img`, `bg_img`, `threshold`, `cmap`, `radiological` [25, 60].
  * **Use Cases**: Real-time interactive slice navigation and intensity inspection in Jupyter or web browsers [25, 60].

* **`view_connectome(adjacency_matrix, node_coords, edge_threshold=None, linewidth=6.0, node_size=3.0)`**:
  * **What it does**: Generates a dynamic 3D WebGL glass brain viewer for interactive connectome graph rotation and inspection [5, 61, 62].
  * **Key Arguments**: `adjacency_matrix`, `node_coords`, `edge_threshold`, `linewidth`, `node_size` [62].
  * **Use Cases**: Interactive 3D graph exploration [62].

* **`view_surf(surf_mesh, surf_map, bg_map=None, cmap='gist_ncar', engine='plotly')`**:
  * **What it does**: Generates a 3D interactive cortical surface viewer using `plotly` or `niivue` engines [5, 63-65].
  * **Key Arguments**: `surf_mesh`, `surf_map`, `bg_map`, `hemi`, `engine` (`'plotly'`, `'niivue'`) [63, 64].
  * **Use Cases**: Interactive web-based cortical surface data exploration [63, 64].

* **`view_img_on_surf(stat_map_img, surf_mesh='fsaverage5', threshold='90%', vol_to_surf_kwargs=None)`**:
  * **What it does**: Projects 3D volumetric NIfTI statistical images onto interactive 3D surface meshes in a single step [5, 63, 66].
  * **Key Arguments**: `stat_map_img`, `surf_mesh`, `threshold`, `vol_to_surf_kwargs` [63, 66].
  * **Use Cases**: Rapid 3D volumetric statistical map projection to interactive surface views [63, 66].

* **`view_markers(marker_coords, marker_color=None, marker_size=5.0)`**:
  * **What it does**: Interactive 3D brain plot displaying point markers [5, 67].
  * **Key Arguments**: `marker_coords`, `marker_color`, `marker_size` [67].
  * **Use Cases**: Interactive coordinate marker visualization [67].

---

## 6. `nilearn.connectome`: Functional Connectomics and Covariance Modeling

The **`nilearn.connectome`** module provides tools to estimate functional connectivity matrices from ROI time series [47, 50].

### 1. `ConnectivityMeasure`

A scikit-learn compatible transformer class that computes functional connectivity matrices from subject ROI time series matrices (`shape = [n_timepoints, n_rois]`) [50, 51, 68].

* **`kind` Parameter Options**:
  * `'correlation'`: Standard Pearson full (marginal) correlation coefficient [50, 68].
  * `'covariance'`: Sample covariance matrix [1].
  * `'partial correlation'`: Direct pairwise connection strength calculated using sparse inverse covariance [51, 69].
  * `'precision'`: Inverted covariance matrix [1].
  * `'tangent'`: Tangent space embedding, modeling connectivity matrices as displacements relative to a Riemannian group mean connectome [51, 70]. Superior for downstream classification/regression models [71].
* **Key Parameters & Attributes**:
  * `vectorize=True`: Flattens output matrices into 1D feature vectors (extracting unique triangular entries) for scikit-learn classifiers [71, 72].
  * `cov_estimator`: Custom covariance estimator (e.g., `LedoitWolf()`, `GraphicalLassoCV()`) [73].
  * `mean_`: Group mean connectivity matrix computed during `.fit()` [50, 70].
* **Use Cases**: Extracting connectome feature matrices for group comparisons and machine learning decoding [71, 72].

### 2. `GroupSparseCovarianceCV`

A group-sparse precision matrix estimator for multi-subject connectomics based on group Graphical Lasso with cross-validated penalty selection [47, 74-76].

* **What it does**: Enforces a shared sparsity pattern across subjects while allowing subject-specific edge weight variations [74, 77].
* **Key Parameters & Attributes**: `max_iter`, `verbose`, `covariances_`, `precisions_`, `alpha_` [74-76].
* **Use Cases**: Multi-subject group sparse connectivity structure recovery [47, 74].

---

## 7. `nilearn.glm`: General Linear Modeling for Task and Resting-State fMRI

The **`nilearn.glm`** module implements parametric voxelwise and surface-level General Linear Modeling [57, 78, 79].

### 1. First-Level Modeling (`nilearn.glm.first_level`)

* **`FirstLevelModel`**:
  * **What it does**: Fits single-run or multi-run voxelwise/surface General Linear Models on BOLD time series [78, 80-82].
  * **Key Parameters**: `t_r`, `slice_time_ref`, `hrf_model` (`'spm'`, `'glover'`, `'glover + derivative'`, `'fir'`), `drift_model` (`'cosine'`, `'polynomial'`), `high_pass`, `noise_model` (`'ar1'`, `'ols'`), `smoothing_fwhm`, `mask_img`, `signal_scaling` [81-83].
  * **Core Methods**:
    * `.fit(run_imgs, events=None, design_matrices=None, confounds=None)`: Fits the GLM [80, 81, 84].
    * `.compute_contrast(contrast_def, stat_type=None, output_type='z_score')`: Computes statistical contrast maps (`'z_score'`, `'stat'`, `'p_value'`, `'effect_size'`, `'effect_variance'`, `'all'`) [57, 80, 85].
    * `.generate_report(contrasts, bg_img=None)`: Generates an HTML summary report displaying design matrices and activation overlays [86].
  * **Use Cases**: Single-subject task activation mapping and contrast estimation [80, 82].

* **`make_first_level_design_matrix(frame_times, events=None, hrf_model='spm', drift_model='cosine', high_pass=0.01, add_regs=None)`**:
  * **What it does**: Generates a first-level GLM design matrix DataFrame from frame timestamps and event tables [78, 87].
  * **Use Cases**: Constructing customized task design matrices [87].

* **`first_level_from_bids(dataset_path, task_label, space_label='', sub_labels=None, img_filters=None, n_jobs=1)`**:
  * **What it does**: Parses BIDS datasets directly, instantiating pre-configured `FirstLevelModel` objects alongside run images, event tables, and confound TSVs [78].
  * **Use Cases**: Automated first-level pipeline execution on BIDS datasets [78].

### 2. Second-Level Group Modeling (`nilearn.glm.second_level`)

* **`SecondLevelModel`**:
  * **What it does**: Fits group-level random-effects and fixed-effects GLM analysis across multiple subject contrast maps [30, 57, 79, 88].
  * **Key Parameters**: `mask_img`, `smoothing_fwhm`, `n_jobs`, `verbose` [23, 57, 88].
  * **Core Methods**:
    * `.fit(second_level_input, design_matrix=None)`: Fits group GLM on contrast images or `FirstLevelModel` objects [30, 57, 88].
    * `.compute_contrast(second_level_contrast=None, output_type='z_score')`: Computes group-level statistical z-maps [23, 30, 89].
  * **Use Cases**: One-sample t-tests, two-sample group comparisons, and phenotypic covariate regressions [23, 57, 88].

* **`make_second_level_design_matrix(subjects_label, extra_info_subjects=None)`**:
  * **What it does**: Sets up second-level DataFrame design matrices [79].
  * **Use Cases**: Group-level covariate design construction [79].

* **`non_parametric_inference(second_level_input, design_matrix, second_level_contrast=None, model_intercept=True, n_perm=5000, two_sided_test=True, n_jobs=1)`**:
  * **What it does**: Performs non-parametric permutation testing with max-statistic family-wise error (FWER) or cluster-level correction [79, 90, 91].
  * **Use Cases**: Robust non-parametric group inference without Gaussian assumption constraints [90, 91].

### 3. Thresholding, Cluster Inference, and Derivatives

* **`threshold_stats_img(stat_img, mask_img=None, alpha=0.05, height_control='fdr', cluster_threshold=0, two_sided=True)`**:
  * **What it does**: Applies FDR, Bonferroni, or FPR statistical thresholding to z/t-score images [23, 30, 89].
  * **Use Cases**: Controlling false positives in statistical maps [23, 30].

* **`cluster_level_inference(stat_img, mask_img=None, threshold=3.0, alpha=0.05)`**:
  * **What it does**: Implements All-Resolution Inference (ARI) to compute true positive proportion (TPP) maps within activation clusters [86, 92].
  * **Use Cases**: Cluster-level true discovery proportion estimation [86, 92].

* **`compute_fixed_effects(contrast_imgs, variance_imgs, mask_img=None)`**:
  * **What it does**: Computes fixed-effects meta-analytic summary statistics across multiple runs/sessions [80].
  * **Use Cases**: Combining run-specific contrast and variance maps [80].

* **`save_glm_to_bids(model, contrasts, contrast_types, out_dir, prefix=None, threshold=None, cluster_threshold=0)`**:
  * **What it does**: Exports fitted GLM statistical maps, masks, design matrix plots, and summary reports into a BIDS-compliant derivatives directory structure [85].
  * **Use Cases**: Standardized BIDS derivatives export [85].

---

## 8. `nilearn.decoding`: Multivariate Pattern Analysis (MVPA) & Machine Learning

The **`nilearn.decoding`** module provides high-level machine learning estimators specifically designed to decode cognitive states or phenotypic targets directly from 3D/4D neuroimaging data [7, 93, 94].

### Estimator Classes

* **`Decoder`**:
  * **What it does**: Composite classification estimator combining masking (`NiftiMasker`/`SurfaceMasker`), ANOVA univariate feature selection (`SelectPercentile`), hyperparameter-tuned linear classifiers (`'svc'`, `'svc_l1'`, `'logistic'`, `'ridge_classifier'`), and cross-validation [7, 93-95].
  * **Key Parameters**: `estimator`, `mask`, `cv` (e.g., `LeaveOneGroupOut()`), `screening_percentile`, `screening_n_features`, `scoring`, `n_jobs`, `verbose` [93, 95-97].
  * **Exposes**: `.cv_scores_` (fold accuracies), `.coef_img_` (reconstructed 3D/surface weight maps in MNI space) [39, 96, 98].
  * **Use Cases**: Stimulus condition classification (e.g., face vs. house decoding) and spatial weight map visualization [7, 96].

* **`DecoderRegressor`**:
  * **What it does**: Composite regression estimator paired with continuous target models (`estimator='svr'`, `'ridge'`) [99, 100].
  * **Key Parameters**: `estimator`, `mask`, `scoring` (`'neg_mean_absolute_error'`), `screening_percentile`, `n_jobs` [99, 100].
  * **Use Cases**: Predicting continuous behavioral or phenotypic variables (e.g., age prediction from VBM maps) [99, 100].

* **`FREMClassifier` / `FREMRegressor`**:
  * **What it does**: Fast Ensembling of Regularized Models. Uses implicit spatial clustering and aggregates multiple estimators trained across randomized splits [101-103].
  * **Key Parameters**: `estimator`, `mask`, `cv`, `n_jobs` [102, 103].
  * **Use Cases**: Delivering robust, spatially structured weight maps at lower computational cost than TV-$L_1$ [101, 103].

* **`SearchLight`**:
  * **What it does**: Implements volumetric or surface Searchlight decoding by scanning a spherical neighborhood (`radius` in mm) across every voxel/vertex, fitting a local classifier [104, 105].
  * **Key Parameters**: `mask_img`, `process_mask_img`, `radius` (e.g., `5.6`), `cv`, `n_jobs` [104].
  * **Exposes**: `.scores_img_` (3D local accuracy/score map) [104].
  * **Use Cases**: Uncovering localized cognitive information content across brain volumes or surface meshes [104, 105].

* **`SpaceNetClassifier` / `SpaceNetRegressor`**:
  * **What it does**: Spatially regularized decoding algorithms utilizing graph-net or Total Variation ($L_1 + \text{TV}$) penalties (`penalty='graph-net'`, `'tv-l1'`) [101, 106, 107].
  * **Key Parameters**: `penalty`, `screening_percentile`, `memory`, `n_jobs` [107].
  * **Use Cases**: Yielding compact, structured, and interpretable spatial weight maps [101, 106].

---

Would you like to explore setting up a complete Nilearn fMRI preprocessing, GLM, or decoding script using these modules?
