Here is the complete reference list of Connectome Workbench (`wb_command`) command-line flags, options, syntax structures, and subcommands as documented in the notebook sources [1-4].

---

## 1. Global Command Flags & Help Utilities

Global utility flags provide top-level system options, usage information, parser rules, and list supported subcommands [1, 2].

| Global Flag | Functional Description |
| :--- | :--- |
| **`-all-commands-help`** | Displays unabridged documentation and parameter syntaxes for all `wb_command` subcommands [1, 2]. |
| **`-list-commands`** | Lists an alphabetized catalog of all available subcommands [1, 2]. |
| **`-list-deprecated-commands`** | Lists deprecated subcommands alongside recommended modern replacements [1, 2]. |
| **`-global-options`** | Displays global execution parameters, OpenMP threading options, and memory allocation controls [1, 2]. |
| **`-arguments-help`** | Summarizes parameter parsing rules and command-line argument notation conventions [1, 2]. |
| **`-parallel-help`** | Outlines multi-threading options and parallel processing configurations [1, 2]. |
| **`-cifti-help`** | Displays file structure documentation for CIFTI-1 and CIFTI-2 formats [1, 2]. |
| **`-gifti-help`** | Displays documentation covering GIFTI surface mesh, metric, and label file conventions [1, 2]. |

---

## 2. CIFTI Dataset Subcommands (`-cifti-*`)

CIFTI operations manipulate multi-modal datasets mapped across combined cortex surface vertices and subcortical volume voxels (brainordinates) [1, 3, 5-8].

### Core Syntax Examples & Flags

* **`-cifti-dilate`**: Dilates data along a designated CIFTI dimension across surface geodesic and volume spaces [5, 6].
  ```bash
  wb_command -cifti-dilate <cifti-in> <direction> <surface-distance> <volume-distance> <cifti-out> [-bad-vertex-roi <roi>] [-nearest] [-legacy-mode]
  ```
  * `<direction>`: Dimension to dilate along (`ROW` or `COLUMN`) [6].
  * `<surface-distance>`: Maximum surface geodesic distance in mm [6].
  * `<volume-distance>`: Maximum volume Euclidean distance in mm [6].
* **`-cifti-find-clusters`**: Filters connected brainordinate clusters by threshold magnitude and spatial size [9].
  ```bash
  wb_command -cifti-find-clusters <cifti> <surface-value-threshold> <surface-minimum-area> <volume-value-threshold> <volume-minimum-size> <direction> <cifti-out> [-less-than]
  ```
* **`-cifti-separate`**: Extracts GIFTI surface metrics/labels or NIfTI volume components from a CIFTI file [10].
  ```bash
  wb_command -cifti-separate <cifti-in> <direction> [-metric <structure> <metric-out>] [-label <structure> <label-out>] [-volume-all <vol-out>] [-crop]
  ```
* **`-cifti-merge-dense`**: Concatenates multiple CIFTI files along the dense brainordinate dimension [5, 11].
  ```bash
  wb_command -cifti-merge-dense <direction> <cifti-out> [-cifti <cifti-in>] [-label-collision <action>]
  ```
  * `[-label-collision]`: Handles label key conflicts (`ERROR`, `FIRST`, `SURFACES_FIRST`, or `LEGACY`) [5, 11].

### Complete List of CIFTI Operations

* **`-cifti-all-labels-to-rois`**: Converts a CIFTI label map into separate binary ROI columns for each discrete label [2, 4].
* **`-cifti-average`**: Computes element-wise average across multiple CIFTI files with optional weighting and outlier rejection (`-exclude-outliers`) [2, 4].
* **`-cifti-average-dense-roi`**: Averages dense CIFTI rows across subjects within ROI masks [2, 4].
* **`-cifti-average-roi-correlation`**: Correlates ROI average time-series across brainordinates and averages results across subjects [2, 4].
* **`-cifti-change-mapping`**: Reconfigures dimension mappings (e.g., converting series step interval or changing to scalar mapping) [2, 4].
* **`-cifti-convert`**: Dumps/imports packed CIFTI matrices to/from GIFTI external binary, NIfTI, or plain text formats (`-to-gifti-ext`, `-from-gifti-ext`, `-to-nifti`, `-from-nifti`, `-to-text`, `-from-text`) [2, 4].
* **`-cifti-correlation`**: Calculates cross-correlation or covariance matrices across brainordinates [2, 4].
* **`-cifti-correlation-gradient`**: Computes spatial gradients on cross-correlation matrices across surface and volume spaces [2, 4].
* **`-cifti-create-dense-from-template`**: Creates a CIFTI dataset using spatial mapping from a reference template file [4, 12, 13].
* **`-cifti-create-dense-scalar`**: Assembles dense scalar (`.dscalar.nii`) files from left/right metric files and subcortical volume inputs [12, 13].
* **`-cifti-create-dense-timeseries`**: Assembles dense time-series (`.dtseries.nii`) datasets [3].
* **`-cifti-create-label`**: Creates a dense label (`.dlabel.nii`) dataset from GIFTI surface label inputs [3].
* **`-cifti-create-parcellated-from-template`**: Generates parcellated CIFTI files using template parcel definitions [3].
* **`-cifti-create-scalar-series`**: Constructs a scalar series CIFTI dataset [3].
* **`-cifti-cross-correlation`**: Computes cross-correlation between two distinct CIFTI files [3].
* **`-cifti-erode`**: Erodes data boundaries across CIFTI surface and volume structures [3].
* **`-cifti-estimate-fwhm`**: Estimates spatial smoothness (FWHM) across brainordinates [3].
* **`-cifti-export-dense-mapping`**: Exports index-to-brainordinate mappings to plain text format [3].
* **`-cifti-extrema`**: Identifies spatial extrema (maxima/minima) in CIFTI datasets [3].
* **`-cifti-false-correlation`**: Evaluates false correlation artifacts between neighboring brainordinates [3].
* **`-cifti-gradient`**: Computes surface geodesic and volume spatial gradients across brainordinates [3].
* **`-cifti-label-adjacency`**: Evaluates spatial adjacency boundaries between parcellated regions [3].
* **`-cifti-label-export-table`**: Exports categorical label color and key tables from CIFTI label maps [3].
* **`-cifti-label-import`**: Imports external text label tables into CIFTI label maps [3].
* **`-cifti-label-modify-keys`**: Remaps integer key values within CIFTI label files [3].
* **`-cifti-label-probability`**: Computes vertex/voxel label frequency maps across subject populations [3].
* **`-cifti-label-to-border`**: Draws vector border paths along CIFTI label boundaries [3].
* **`-cifti-label-to-roi`**: Extracts specified label keys into binary CIFTI ROI maps [3].
* **`-cifti-math`**: Evaluates mathematical expressions element-by-element across CIFTI inputs [3].
* **`-cifti-merge`**: Merges subvolume/map frames across multiple CIFTI inputs [3].
* **`-cifti-merge-parcels`**: Merges parcellated CIFTI files along the parcel dimension [3].
* **`-cifti-pairwise-correlation`**: Computes column-by-column or row-by-row pairwise correlations [3].
* **`-cifti-palette`**: Configures display color palettes, scaling thresholds, and color bar options [3, 12-14].
* **`-cifti-parcel-mapping-to-label`**: Converts parcel mapping definitions into explicit CIFTI label maps [3].
* **`-cifti-parcellate`**: Averages dense CIFTI brainordinates within parcel ROIs to create parcellated files [3].
* **`-cifti-reduce`**: Applies reduction operators (e.g., mean, max, min, stddev) across specified CIFTI dimensions [3].
* **`-cifti-reorder`**: Rearranges map/series frame ordering within CIFTI files [3].
* **`-cifti-replace-structure`**: Replaces data values for a specific anatomical structure within a CIFTI dataset [3].
* **`-cifti-resample`**: Resamples CIFTI datasets between different surface grids or volume spaces [3].
* **`-cifti-resample-dconn-memory`**: Memory-efficient algorithm for resampling large dense connectivity (`.dconn.nii`) matrices [3].
* **`-cifti-restrict-dense-map`**: Excludes brainordinates outside a designated mask/ROI [2, 7].
* **`-cifti-roi-average`**: Calculates average scalar values within designated ROI regions [2].
* **`-cifti-rois-from-extrema`**: Generates parcel ROIs surrounding spatial extrema points [2].
* **`-cifti-smoothing`**: Performs Gaussian smoothing independently along surface geodesic topology and 3D subcortical volume [3, 8].
* **`-cifti-stats`**: Computes spatial statistics (mean, percentile, variance) across CIFTI datasets [2, 15].
* **`-cifti-transpose`**: Transposes row and column dimensions in 2D CIFTI matrices [2].
* **`-cifti-vector-operation`**: Computes vector math (dot product, cross product, magnitude) on CIFTI vector fields [2].
* **`-cifti-weighted-stats`**: Computes area-weighted or voxel-volume-weighted spatial statistics [2].

---

## 3. Surface Mesh & Geometry Subcommands (`-surface-*`)

Surface subcommands handle 3D vertex coordinate transformations, mesh geometry calculations, geodesic distance measurements, inflation, and spherical registration resampling [2, 16-20].

### Core Syntax Examples & Flags

* **`-surface-cortex-layer`**: Generates an intermediate surface approximating a target cortical volume fraction between white matter and pial meshes [16, 20].
  ```bash
  wb_command -surface-cortex-layer <white-surface> <pial-surface> <location> <out-surface> [-placement-out <placement-metric>]
  ```
* **`-surface-distortion`**: Quantifies areal or edge length strain distortion between reference and registered surfaces [17, 20].
  ```bash
  wb_command -surface-distortion <surface-reference> <surface-distorted> <metric-out> [-smooth <sigma>] [-fwhm] [-match-surface-area] [-caret5-method] [-edge-method] [-local-affine-method] [-log2]
  ```
* **`-surface-geodesic-distance`**: Measures exact geodesic path distances along surface mesh edges from a seed vertex [20].
  ```bash
  wb_command -surface-geodesic-distance <surface> <vertex> <metric-out> [-naive] [-limit <limit-mm>] [-corrected-areas <area-metric>]
  ```
* **`-surface-wedge-volume`**: Computes per-vertex cortical volume enclosed between two vertex-matched surfaces [19, 21].
  ```bash
  wb_command -surface-wedge-volume <inner-surface> <outer-surface> <metric-out>
  ```

### Complete List of Surface Operations

* **`-surface-affine-regression`**: Regresses a 4x4 affine matrix aligning two surface meshes on the same topology [2, 20].
* **`-surface-apply-affine`**: Transforms surface 3D XYZ coordinates using a 4x4 affine matrix (supports `-flirt` matrices) [2, 20].
* **`-surface-apply-warpfield`**: Deforms surface vertex coordinates using non-linear 3D volumetric warpfields (supports `-fnirt`) [2, 20].
* **`-surface-average`**: Averages 3D vertex coordinates across multiple surface meshes with weightings [2, 20].
* **`-surface-closest-vertex`**: Finds closest surface vertex index for target 3D Cartesian coordinates [2, 20].
* **`-surface-coordinates-to-metric`**: Extracts 3D surface XYZ vertex coordinates into a 3-map surface metric file [2, 20].
* **`-surface-create-sphere`**: Generates a regular spherical surface mesh with uniform vertex distribution [2, 20].
* **`-surface-curvature`**: Computes mean curvature (`-mean`) and Gaussian curvature (`-gauss`) across mesh vertices [2, 20].
* **`-surface-cut-resample`**: Resamples cut surface meshes between registered spherical grids [2, 20].
* **`-surface-flip-lr`**: Mirrors surface mesh through the YZ plane and flips triangle normal orientations [2, 20].
* **`-surface-flip-normals`**: Inverts triangle normal orientations across surface mesh faces [2, 20].
* **`-surface-generate-inflated`**: Generates inflated and very-inflated surface representations from anatomical meshes [2, 20, 22].
* **`-surface-geodesic-distance-all-to-all`**: Computes geodesic distances between all vertex pairs into a single-hemisphere `.dconn.nii` file [2, 18, 20].
* **`-surface-geodesic-distance-sparse-text`**: Outputs vertex-pair geodesic distances exceeding a distance threshold to CSV text [2, 20].
* **`-surface-geodesic-distance-to-roi`**: Measures shortest geodesic distances from vertices to ROI boundaries [20].
* **`-surface-geodesic-rois`**: Draws circular geodesic ROIs centered at specified surface vertices [2].
* **`-surface-inflation`**: Runs iterative surface mesh inflation algorithms [2, 23].
* **`-surface-information`**: Displays mesh header details, vertex/tile counts, bounding box dimensions, and surface structure [2, 23].
* **`-surface-match`**: Aligns surface translation and scale to match a target mesh [2, 23].
* **`-surface-modify-sphere`**: Rescales spherical surface radius and re-centers origin coordinates [2, 23].
* **`-surface-normals`**: Calculates unit surface normal vectors at each vertex into a 3-map metric file [2, 23].
* **`-surface-resample`**: Resamples surface meshes between registered spherical grids (`BARYCENTRIC` or `ADAP_BARY_AREA`) [2, 23, 24].
* **`-surface-set-coordinates`**: Updates 3D vertex coordinates in a surface file using a metric file input [2, 23].
* **`-surface-smoothing`**: Applies spatial smoothing to vertex coordinates to reduce high-frequency mesh noise [2, 23].
* **`-surface-sphere-project-unproject`**: Copies registration deformation fields across different spherical meshes [2, 25].
* **`-surface-sphere-triangular-patches`**: Subdivides standard spherical surfaces into equal-sized triangular patches [2, 21].
* **`-surface-to-surface-3d-distance`**: Computes 3D Euclidean distances and displacement vectors between corresponding vertices [2, 21].
* **`-surface-vertex-areas`**: Calculates the surface area responsible by each vertex in \\(\text{mm}^2\\) [2, 21, 26, 27].

---

## 4. Metric Processing Subcommands (`-metric-*`)

Metric subcommands process continuous scalar data files associated with surface vertices (e.g., cortical thickness, curvature, myelin maps, functional activations) [2, 28-35].

### Core Syntax Examples & Flags

* **`-metric-dilate`**: Dilates metric map data on a surface using distance-weighted averaging [28, 36].
  ```bash
  wb_command -metric-dilate <metric> <surface> <distance> <metric-out> [-bad-vertex-roi <roi>] [-nearest] [-exponent <n>]
  ```
* **`-metric-math`**: Evaluates mathematical expression strings on surface metrics [31, 37].
  ```bash
  wb_command -metric-math '<expression>' <metric-out> [-fixnan <replace>] [-var <name> <metric>]
  ```
* **`-metric-resample`**: Resamples surface metric maps between registered spherical surface meshes [12, 32, 38].
  ```bash
  wb_command -metric-resample <metric-in> <current-sphere> <new-sphere> <method> <metric-out> [-area-surfs <cur-surf> <new-surf>]
  ```
* **`-metric-tfce`**: Runs Threshold-Free Cluster Enhancement (TFCE) on surface metrics [2, 34].
  ```bash
  wb_command -metric-tfce <surface> <metric-in> <metric-out> [-presmooth <kernel>] [-fwhm] [-parameters <E> <H>]
  ```

### Complete List of Metric Operations

* **`-metric-convert`**: Converts GIFTI metric files to/from legacy NIfTI-1 formats [2].
* **`-metric-erode`**: Erodes metric boundary data by setting surrounding vertices to zero or unlabeled state [2, 28].
* **`-metric-estimate-fwhm`**: Estimates spatial smoothness (FWHM) along surface geodesic topology [2].
* **`-metric-extrema`**: Finds spatial local maxima or minima on surface metric maps [2].
* **`-metric-false-correlation`**: Identifies false correlation patterns between surface vertices [2].
* **`-metric-fill-holes`**: Fills interior zero-holes within binary surface metric ROIs [2, 29].
* **`-metric-find-clusters`**: Filters surface metric clusters based on scalar thresholds and minimum area limits (\\(\text{mm}^2\\)) [2, 30].
* **`-metric-gradient`**: Computes spatial gradients on surface metrics, outputting magnitude and 3D vector directions [2].
* **`-metric-label-import`**: Imports label tables into surface metrics [2].
* **`-metric-mask`**: Applies binary mask metrics to zero out values outside regions of interest [2, 37-39].
* **`-metric-merge`**: Concatenates multiple metric files or column maps into a single output file [2].
* **`-metric-palette`**: Sets color display palettes, threshold ranges, and inversion settings on metric files [2].
* **`-metric-reduce`**: Applies reduction operators across metric maps/columns [2].
* **`-metric-regression`**: Performs linear regression between surface metric maps [2].
* **`-metric-remove-islands`**: Cleans up isolated noise vertices from surface ROI maps [2].
* **`-metric-rois-from-extrema`**: Creates geodesic ROI circles surrounding local metric extrema [2, 33].
* **`-metric-rois-to-border`**: Converts metric ROI boundaries into vector border paths [2].
* **`-metric-smoothing`**: Smooths surface metrics using Gaussian kernels along geodesic surface topology [2].
* **`-metric-stats`**: Computes summary statistics (mean, stddev, max, min, percentiles) across surface metrics [2].
* **`-metric-to-volume-mapping`**: Projects surface metric scalar values into 3D volume spaces [2, 35].
* **`-metric-vector-operation`**: Computes vector mathematical operations on multi-column vector metric files [2].
* **`-metric-vector-toward-roi`**: Evaluates whether surface vector fields point toward a target ROI [2].
* **`-metric-weighted-stats`**: Calculates area-weighted spatial statistics across surface metrics [2].

---

## 5. Volumetric Operations Subcommands (`-volume-*`)

Volumetric subcommands handle 3D/4D NIfTI images, spatial resamplings, TFCE statistics, parcel resamplings, and surface-to-volume interpolation algorithms [2, 40-47].

### Core Syntax Examples & Flags

* **`-volume-to-surface-mapping`**: Projects 3D/4D voxel data onto 2D surface meshes [2, 46].
  ```bash
  wb_command -volume-to-surface-mapping <volume> <surface> <metric-out> [-trilinear] [-enclosing] [-cubic] [-ribbon-constrained <inner-surf> <outer-surf>]
  ```
* **`-volume-resample`**: Resamples volume datasets using affine matrices or non-linear warpfields [2, 48].
  ```bash
  wb_command -volume-resample <volume-in> <volume-space> <method> <volume-out> [-affine <affine-file>] [-warpfield <warp-file>]
  ```
* **`-volume-math`**: Evaluates voxel-by-voxel mathematical expressions across 3D/4D volumes [2, 48].
  ```bash
  wb_command -volume-math '<expression>' <volume-out> [-fixnan <replace>] [-var <name> <volume>]
  ```
* **`-volume-tfce`**: Computes Threshold-Free Cluster Enhancement (TFCE) on 3D volumetric images [2, 45].
  ```bash
  wb_command -volume-tfce <volume-in> <volume-out> [-presmooth <kernel>] [-fwhm] [-roi <roi-volume>]
  ```

### Complete List of Volumetric Operations

* **`-volume-all-labels-to-rois`**: Converts a 3D label volume into separate binary volume frames for each label key [2, 21].
* **`-volume-capture-plane`**: Interpolates a 2D cross-sectional slice image from an arbitrary plane through a 3D volume [2, 21, 41].
* **`-volume-components-to-frames`**: Splits complex or RGB volume channels into separate scalar volume subvolume frames [2, 21].
* **`-volume-copy-extensions`**: Copies volume metadata extension blocks between NIfTI headers [2, 21].
* **`-volume-create`**: Creates a blank, zero-filled NIfTI volume with defined dimensions, voxel spacings, and sform/qform spatial orientation [2, 21].
* **`-volume-dilate`**: Dilates volumetric masks or scalar data using nearest-neighbor or distance-weighted Gaussian methods [2, 21].
* **`-volume-distortion`**: Quantifies isotropic and anisotropic local strain distortion from 3D non-linear warpfields [2, 21].
* **`-volume-erode`**: Erodes volumetric binary masks along 3D voxel face neighborhoods [2, 21].
* **`-volume-estimate-fwhm`**: Estimates spatial smoothness (FWHM) along X, Y, Z voxel axes [2, 21].
* **`-volume-extrema`**: Identifies 3D spatial local maxima/minima within volume images [2].
* **`-volume-fill-holes`**: Fills interior void holes inside 3D volume ROI masks [2].
* **`-volume-find-clusters`**: Identifies connected 3D spatial clusters exceeding voxel value and cluster volume limits (\\(\text{mm}^3\\)) [2].
* **`-volume-gradient`**: Computes 3D spatial gradient vector fields across volumetric datasets [2, 48].
* **`-volume-label-export-table`**: Exports volume label color and key lookup tables to text format [2, 48].
* **`-volume-label-import`**: Imports label lookup tables into categorical label volumes [2, 48].
* **`-volume-label-modify-keys`**: Modifies or remaps integer label keys in 3D volume label files [2, 48].
* **`-volume-label-probability`**: Calculates voxel-wise label frequency maps across subject label volumes [2, 48].
* **`-volume-label-resample`**: Transforms and resamples volume label images using nearest-neighbor interpolation [2, 48].
* **`-volume-label-to-roi`**: Extracts specified volumetric label keys into binary ROI volumes [2, 48].
* **`-volume-label-to-surface-mapping`**: Projects 3D categorical label volumes onto surface label maps [2, 48].
* **`-volume-merge`**: Concatenates multiple volume files or subvolume frames into a 4D volume dataset [2, 42, 48].
* **`-volume-palette`**: Configures thresholding, color maps, and palette settings for volume files [2, 48].
* **`-volume-parcel-resampling`**: Smooths and resamples parcel datasets within the same volumetric space [2, 48].
* **`-volume-parcel-resampling-generic`**: Smooths and resamples parcel volumes across differing volumetric coordinate spaces [2, 43, 48].
* **`-volume-parcel-smoothing`**: Applies Gaussian smoothing independently within individual volume parcel ROIs [2, 48].
* **`-volume-reduce`**: Reduces 4D volume frames along the time dimension using reduction operations [2, 48].
* **`-volume-remove-islands`**: Removes small isolated voxel clusters from volume ROI masks [2, 48].
* **`-volume-reorient`**: Reorders 3D voxel storage axes to standard orientation codes (e.g., `RAS`, `LPI`) [2, 48].
* **`-volume-rois-from-extrema`**: Generates spherical 3D ROI volumes surrounding spatial extrema voxels [2, 48].
* **`-volume-set-space`**: Modifies NIfTI volume header spatial reference information without altering voxel arrays [2, 48].
* **`-volume-smoothing`**: Applies 3D Gaussian spatial smoothing across volume voxels [2, 48].
* **`-volume-stats`**: Computes spatial summary statistics (mean, percentiles, min, max) across 3D/4D volumes [2, 44, 48].
* **`-volume-vector-operation`**: Performs vector math (dot products, cross products, magnitudes) on 3D vector volumes [2, 47, 48].
* **`-volume-warpfield-affine-regression`**: Regresses a 4x4 rigid/affine approximation matrix from a non-linear 3D warpfield [2, 48].
* **`-volume-weighted-stats`**: Calculates voxel-volume-weighted spatial statistics [2, 48].

---

## 6. Labels, Borders, Foci, and GIFTI Subcommands

These subcommands manage discrete parcellation labels, vector border contours, stereotaxic foci points, and GIFTI file structures [2, 4, 36, 49-52].

### Label Subcommands (`-label-*`)

* **`-label-dilate`**: Dilates surface label boundaries along geodesic surface distances [2, 36].
* **`-label-erode`**: Erodes surface labels, converting boundary vertices to unlabeled state [2].
* **`-label-export-table`**: Exports label color/key tables to plain text or JSON format [2].
* **`-label-mask`**: Applies binary metric masks to surface label maps [2].
* **`-label-merge`**: Combines multiple surface label files into a single map [2].
* **`-label-modify-keys`**: Remaps integer key definitions using text remapping files [2].
* **`-label-probability`**: Calculates vertex-wise label frequency probabilities across subject groups [2, 50].
* **`-label-resample`**: Resamples surface label maps between registered spherical grids [2].
* **`-label-to-border`**: Draws vector border paths surrounding surface label boundaries [2].
* **`-label-to-volume-mapping`**: Projects surface label maps into 3D volume label files [2].

### Border Subcommands (`-border-*`)

* **`-border-export-color-table`**: Writes border names and RGB colors to text format [2, 51].
* **`-border-file-export-to-caret5`**: Exports Workbench border files to Caret5 legacy formats [2, 4, 51].
* **`-border-length`**: Reports geodesic path lengths of surface borders in mm [2, 4, 51].
* **`-border-merge`**: Merges multiple border files into a unified file [2, 4, 51].
* **`-border-resample`**: Resamples border vector paths between registered spherical meshes [2, 4, 51].
* **`-border-to-rois`**: Generates binary metric ROIs enclosed within surface border boundaries [2, 4, 51].
* **`-border-to-vertices`**: Draws border contours directly as 1/0 binary vertex metric maps [2, 4, 51].

### Foci & GIFTI Subcommands

* **`-foci-create`**: Creates 3D stereotaxic foci point files [2, 52].
* **`-foci-get-projection-vertex`**: Identifies closest surface vertex projections for foci point coordinates [2, 49, 52].
* **`-foci-list-coords`**: Outputs foci Cartesian coordinates to plain text [2, 52].
* **`-foci-resample`**: Projects foci points across different surface meshes [2, 52].
* **`-gifti-all-labels-to-rois`**: Converts GIFTI label columns into binary ROI metrics [2, 52].
* **`-gifti-convert`**: Converts GIFTI file encoding (e.g., ASCII, Base64 binary, GZip) [2, 52].
* **`-gifti-label-add-prefix`**: Prepends string prefixes to GIFTI label names [2].
* **`-gifti-label-to-roi`**: Converts designated GIFTI label names into binary metric ROIs [2, 52].

---

## 7. Metadata, Spec Files, and Offscreen Scene Capture

These subcommands manage specification project files (`.spec`), metadata records, and offscreen high-resolution image rendering from visualization scenes (`.scene`) [1, 2, 48, 53-55].

### Offscreen Scene Capture Syntax

* **`-scene-capture-image`**: Renders saved `.scene` display layouts directly to static image files offscreen [2, 53, 55].
  ```bash
  wb_command -scene-capture-image <scene-file> <scene-name-or-number> <image-file-name> [-size-width-height <width> <height>]
  ```
  * Supported image formats: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.ppm` [53].

### Spec, Metadata, & Scene Management Commands

* **`-metadata-remove-provenance`**: Removes pipeline command execution history from file metadata headers [2, 55].
* **`-metadata-string-replace`**: Searches and replaces text strings across file metadata and map headers [2, 55].
* **`-scene-file-merge`**: Combines or rearranges scene configurations across multiple `.scene` files [2, 55].
* **`-scene-file-relocate`**: Updates internal relative data paths when moving `.scene` files to new folder directories [2, 54, 55].
* **`-scene-file-restructure`**: Reorganizes internal scene file structures and linked data assets [2, 55].
* **`-scene-file-update`**: Updates data file linkages and color palette settings within `.scene` files [2, 55].
* **`-spec-file-merge`**: Combines two `.spec` specification files into a unified master spec [2, 55].
* **`-spec-file-modify`**: Adds, removes, or modifies data file entries in specification files [1, 2, 55].
* **`-spec-file-relocate`**: Updates relative file paths in specification files [2, 20, 55].
* **`-zip-scene-file`**: Packages a `.scene` file along with all linked data assets into a portable `.zip` archive [2, 48].
* **`-zip-spec-file`**: Packages a `.spec` file and all associated surface/volume datasets into a `.zip` archive [1, 2, 48].

---

## 8. Interoperability, Fiber Tracking, and Matrix Conversions

Specialized subcommands handle diffusion fiber orientation distributions, distance fields, and format matrix transformations [2, 40, 48, 52, 55].

* **`-backend-average-dense-roi` / `-backend-average-roi-correlation`**: Backend database commands for automated CIFTI group averaging operations [51].
* **`-class-add-member`, `-class-create`, `-class-create-algorithm`, `-class-create-enum`, `-class-create-operation`**: Programmatic API class generation commands [2].
* **`-convert-affine`**: Converts 4x4 affine transformation matrices between FLIRT, NIfTI world, World, and Caret formats [2, 52].
* **`-convert-fiber-orientations`**: Converts diffusion fiber orientation formats between FSL BedpostX and Workbench representations [2, 52].
* **`-convert-matrix4-to-matrix2`**: Converts trajectory Matrix4 outputs into Matrix2 connectivity representations [2, 52].
* **`-convert-matrix4-to-workbench-sparse`**: Converts Matrix4 outputs into sparse Workbench `.wbsparse` matrices [2, 52].
* **`-convert-warpfield`**: Converts 3D non-linear deformation warpfields between FNIRT, NIfTI world, and ITK formats [2, 52].
* **`-create-signed-distance-volume`**: Generates 3D signed distance volumetric fields from surface mesh geometries [2, 40, 52].
* **`-estimate-fiber-binghams`**: Fits Bingham distributions to BedpostX fiber orientation sample distributions [2, 52].
* **`-fiber-dot-products`**: Calculates dot products between surface normal vectors and diffusion fiber orientations [2, 52].
* **`-file-convert`**: Converts underlying file format versions across Workbench specifications [2, 52].
* **`-file-information`**: Displays detailed header information, map names, series steps, and metadata key-value pairs for any supported file [2, 52].
* **`-nifti-information`**: Inspects standard NIfTI-1/2 and CIFTI XML metadata headers [2, 55].
* **`-probtrackx-dot-convert`**: Converts FSL Probtrackx `.dot` output files into CIFTI dense matrices [2, 55].
* **`-set-map-names`**: Renames individual map headers or column titles in multi-map files [2, 12, 13, 55].
* **`-set-structure`**: Modifies the anatomical structure tag (e.g., `CORTEX_LEFT`, `CORTEX_RIGHT`, `CEREBELLUM`) in file headers [2, 22, 55].
* **`-signed-distance-to-surface`**: Calculates distance metrics from volume voxels to target surface meshes [2, 55].
* **`-unit-test`**: Runs internal software unit test routines [1, 2, 25].
* **`-wbsparse-merge-dense`**: Merges sparse `.wbsparse` connectivity files along dense brainordinate dimensions [1, 2, 48].

---

💡 **Next Step**: Would you like to write a Python or Bash pipeline script to automate any specific task—such as volume-to-surface mapping, spherical mesh resampling, or automated offscreen scene rendering?
