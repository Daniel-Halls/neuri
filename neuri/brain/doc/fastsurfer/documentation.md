**FastSurfer** is a fast, automated deep learning-based neuroimaging pipeline designed for the processing of structural human brain MRI scans [1, 2]. Developed as a rapid alternative to FreeSurfer's traditional `recon-all` pipeline, FastSurfer replicates both volumetric anatomical segmentation and cortical surface reconstruction [1, 3]. 

Below are the complete details on its capabilities, algorithmic stages, directory outputs, and required file structures.

---

### 1. What FastSurfer Does

* **Full Structural Processing**: Takes a raw T1-weighted (T1w) full-head MRI volume and outputs complete whole-brain volumetric segmentations, cortical surface meshes, thickness maps, and region-of-interest (ROI) statistics [1, 2, 4].
* **High Processing Speed**: Completes whole-brain volumetric segmentation in **under 1 minute on a GPU** (~14 minutes on CPU) [1, 5-7]. Full surface reconstruction finishes in approximately **1 to 1.7 hours** (or ~54 minutes with hemisphere parallelization), compared to 4–7 hours for standard FreeSurfer [3, 7].
* **Resolution Independence**: Incorporates FastSurferVINN to handle sub-millimeter isotropic voxel sizes (e.g., 0.7–1.0 mm) dynamically [4, 8].
* **High Mesh Quality**: Reconstructs cortical surfaces with significantly fewer topological defects (handles/tunnels) and higher geometric triangle quality than traditional methods [9, 10].

---

### 2. Deep Learning Segmentation & Surface Reconstruction Stages

FastSurfer consists of two primary sequential execution streams: deep learning volumetric segmentation (`FastSurferCNN` / `FastSurferVINN`) and surface reconstruction (`recon-surf`) [3, 4, 11, 12].

#### Stage A: Deep Learning Volumetric Segmentation (`FastSurferCNN` / `FastSurferVINN`)
1. **Image Conformation**: The input T1w volume is conformed and resampled to a uniform voxel size (defaulting to 1.0 mm isometric, or preserved at sub-millimeter isotropic resolution if \\(\le 0.98\text{ mm}\\)) [4].
2. **2.5D Tri-Planar F-CNNs**: The volume is fed into three 2D Fully Convolutional Neural Networks operating independently across coronal, axial, and sagittal slice orientations [5, 6].
3. **Competitive Dense Blocks (CDB)**: Feature concatenation in dense blocks and skip connections is replaced with Maxout competition operations [5, 6, 13]. This reduces trainable network weights by half (~1.8 million parameters) while improving boundary precision [6, 13].
4. **Spatial Information Aggregation (SPI)**: Multi-slice image context is aggregated to maintain spatial awareness for subtle cortical folding patterns and subcortical boundaries [5, 6, 13].
5. **View Aggregation & Parcellation**: Predictions from all three views are combined via view aggregation to segment the volume into **95 anatomical classes**, covering subcortical structures and Desikan-Killiany-Tourville (DKT) atlas cortical parcellations [1, 4-6].
6. **Optional Preprocessing Steps**: Performs optional bias-field correction (`orig_nu.mgz`) and Talairach registration for estimated Total Intracranial Volume (eTIV) calculation [12].

#### Stage B: Surface Reconstruction (`recon-surf`)
Because a high-quality 3D segmentation is already established, FastSurfer bypasses time-intensive traditional steps such as skull stripping and non-linear atlas registration [14]:
1. **Marching Cubes Mesh Generation**: Replaces FreeSurfer's `mri_tessellate` with the Marching Cubes algorithm on the white matter segmentation, creating initial surface meshes with fewer topological defects and fewer degenerate triangles [9, 10, 14, 15].
2. **Spectral Spherical Embedding**: Replaces standard spherical mapping (`mris_sphere`) by solving the Laplace-Beltrami Eigenvalue problem (\\(\Delta f = -\lambda f\\)) directly on the cortical surface mesh [14-16]. The first three non-constant eigenfunctions smoothly parameterize the surface across anterior-posterior, superior-inferior, and lateral-medial axes, enabling rapid projection onto a unit sphere [16].
3. **Topology Fixing & Surface Placement**: Corrects remaining topological defects on the spherical representation and fine-tunes vertex positions to build inner white matter (`white`) and outer gray matter (`pial`) surfaces [11, 16].
4. **Direct Image-to-Surface Parcellation**: Directly projects the 3D volume-based DKT cortical parcellation labels onto the reconstructed surface mesh [14, 16]. This avoids non-linear spherical atlas registration unless explicit cross-subject vertex-wise alignment is requested [16].

---

### 3. Pipeline Output Directories

FastSurfer outputs follow the standard FreeSurfer subject directory layout inside `$SUBJECTS_DIR/$SID/` [4, 17]:

| Directory | Key Output Files | Description & Contents |
| :--- | :--- | :--- |
| **`mri/`** | `orig.mgz`<br>`orig_nu.mgz`<br>`aparc.DKTatlas+aseg.deep.mgz`<br>`brainmask.mgz`<br>`wm.mgz` | **Volumetric Files**: Conformed T1w input (`orig.mgz`), bias-field corrected volume (`orig_nu.mgz`), whole-brain DKT cortical parcellation + subcortical segmentation (`aparc.DKTatlas+aseg.deep.mgz`), skull-stripped mask, and white matter mask [4, 12, 18]. |
| **`surf/`** | `?h.white`<br>`?h.pial`<br>`?h.inflated`<br>`?h.sphere`<br>`?h.thickness`<br>`?h.sulc`, `?h.curv` | **Surface Geometry & Maps**: Hemisphere-specific (`lh.` and `rh.`) white matter meshes, pial surfaces, inflated visualization meshes, spherical spectral maps, vertex-wise cortical thickness maps, sulcal depth, and curvature files [11, 16, 19-21]. |
| **`label/`** | `?h.aparc.DKTatlas.annot`<br>`?h.cortex.label` | **Surface Parcellation Labels**: Surface annotation files containing DKT cortical labels per vertex and binary cortex masks [16, 22-24]. |
| **`stats/`** | `aseg.stats`<br>`?h.aparc.DKTatlas.stats`<br>`wmparc.stats` | **Tabular Summary Statistics**: Text tables summarizing subcortical volumes, eTIV, white matter parcellations, and per-region cortical metrics (surface area, mean thickness, thickness standard deviation, volume, and curvature) [11, 16, 20, 25-27]. |
| **`scripts/`**| `deep-seg.log` | **Execution Logs**: Detailed log file capturing the segmentation pipeline parameters and runtime progress [12]. |

---

### 4. Required File Structures and Invocation Syntax

#### Subject Directory Hierarchy
To execute FastSurfer, the output environment requires a target `$SUBJECTS_DIR` organized as follows:
```text
$SUBJECTS_DIR/
└── <subject_id>/
    ├── mri/
    ├── surf/
    ├── label/
    ├── stats/
    └── scripts/
```

#### Execution Options (`run_fastsurfer.sh`)
The main entry point for the pipeline is the `run_fastsurfer.sh` shell script [4]:

```bash
run_fastsurfer.sh --sid <subject_id> --sd <subjects_dir> --t1 <path_to_t1> --fs_license <path_to_license> [OPTIONS]
```

* **Required Arguments**:
  * `--sid <subjectID>`: Subject identifier folder created inside `$SUBJECTS_DIR` [4].
  * `--sd <subjects_dir>`: Path to the output subjects directory [4].
  * `--t1 <T1_input>`: Absolute path to the raw, non-bias-corrected T1w MRI volume [4].
  * `--fs_license <license>`: Absolute path to a valid FreeSurfer license key file (`license.txt`) [4].

* **Key Pipeline Flags**:
  * `--seg_only`: Runs only the deep learning volumetric segmentation stream, bypassing surface reconstruction (`recon-surf`) [12].
  * `--vox_size <0.7-1|min>`: Enforces processing at a specific voxel resolution (defaults to `min`, auto-detecting sub-millimeter acquisitions) [4].
  * `--no_biasfield`: Generates a bias-corrected volume (`orig_nu.mgz`) and calculates partial-volume statistics [12].
  * `--tal_reg`: Computes Talairach affine registration for estimated Total Intracranial Volume (`eTIV`) [12].
  * `--edits`: Enables manual editing workflows by allowing substitution of manual edit files (`*.manedit.<ext>`) for segmentations, brain masks, or control points [4].
