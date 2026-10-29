**FreeSurfer** is an open-source software suite for analyzing, segmenting, and modeling human structural brain MRI data [1-3]. It provides automated volume-based and surface-based processing streams to perform tissue classification, subcortical structure labeling, cortical surface extraction, atlas parcellation, and high-resolution morphometric quantification [1, 2, 4, 5].

---

### 1. What FreeSurfer Does

* **Conform & Preprocess Volumetric Data**: Converts raw T1-weighted inputs into a standardized conformed space (\\(1\text{ mm}\\) isotropic, \\(256 \times 256 \times 256\\) matrix) [6, 7].
* **Intensity Non-Uniformity Correction & Skull-Stripping**: Removes B1 magnetic field inhomogeneities and extracts brain tissue from extra-cerebral structures [4, 7].
* **Subcortical Segmentation (`aseg`)**: Labels subcortical structures (e.g., hippocampus, amygdala, thalamus, caudate, ventricles) and measures their volumes [8-11].
* **Cortical Surface Extraction**: Tessellates and deforms triangular meshes to reconstruct the inner gray/white matter boundary (`white`) and outer gray matter/CSF boundary (`pial`) for each hemisphere [10, 12-14].
* **Topology Correction & Inflation**: Automatically identifies and fixes topological defects (e.g., handles and tunnels) to yield spherical topology (\\(g=0\\)) [10, 15], and inflates surfaces for visualization of deep sulci [10, 12, 13].
* **Spherical Surface Registration & Parcellation**: Registers individual surface meshes to a spherical template (`fsaverage`) [16-19] and parcellates the cortex into region-of-interest (ROI) atlases (Desikan-Killiany, Destrieux, DKT) [8, 14, 20, 21].
* **Morphometric Quantification**: Extracts vertex-wise and ROI-level structural metrics, including cortical thickness, surface area, gray matter volume, sulcal depth, and curvature [9, 10, 20, 22].

---

### 2. `recon-all` Pipeline Stages

The full automated anatomical pipeline is controlled by the `recon-all` command [3, 23, 24]. It executes in three main sequential stages [25-27]:

#### Stage 1: `autorecon1` (Preprocessing & Volume Conform)
Focuses on initial volumetric preprocessing, alignment, and skull-stripping [4, 7]:
1. **Motion Correction & Conform**: `mri_convert` and `mri_robust_template` average multiple T1w inputs (if available) and conform the image to \\(1\text{ mm}^3\\) isotropic \\(256^3\\) axial slices (`orig/001.mgz` \\(\rightarrow\\) `rawavg.mgz` \\(\rightarrow\\) `orig.mgz`) [6, 7, 28].
2. **Talairach Transformation**: `talairach_avi` computes the linear affine matrix aligning the volume to Talairach space (`transforms/talairach.auto.xfm` and `transforms/talairach.xfm`) [7, 9].
3. **Intensity Non-Uniformity (N3/N4) Correction**: `mri_nu_correct.mni` corrects intensity non-uniformities caused by RF field bias (`orig_nu.mgz` and `nu.mgz`) [7].
4. **Intensity Normalization**: `mri_normalize` scales image intensities so white matter clusters around a value of 110 (`T1.mgz`) [7].
5. **Skull-Stripping**: `mri_em_register` and `mri_watershed` remove skull and scalp tissue (`brainmask.auto.mgz` \\(\rightarrow\\) `brainmask.mgz`) [4, 7, 26].

#### Stage 2: `autorecon2` (Volume Segmentation & Surface Generation)
Performs subcortical segmentation, initial surface tessellation, and topology fixing [4, 10]:
1. **GCA / CA Registration & Normalization**: `mri_em_register` and `mri_ca_normalize` compute non-linear atlas alignments (`talairach.lta`, `norm.mgz`) [10].
2. **Subcortical Segmentation & Corpus Callosum**: `mri_ca_register` (\\(\rightarrow\\) `talairach.m3z`), `mri_ca_label`, and `mri_cc` label subcortical gray matter structures (`aseg.auto.mgz`, `aseg.presurf.mgz`) [10].
3. **Second Normalization & Brain Masking**: `mri_normalize` and `mri_mask` create final intensity-normalized brain volumes (`brain.mgz`, `brain.finalsurfs.mgz`) [10].
4. **White Matter Segmentation & Editing**: `mri_segment` and `mri_edit_wm_with_aseg` classify white matter voxels, followed by `mri_pretess` to clean voxel boundaries (`wm.mgz`) [10].
5. **Hemispheric Fill & Tessellation**: `mri_fill` cuts subcortical boundaries and fills hemispheres (`filled.mgz`) [10]. `mri_tessellate` generates initial surface meshes (`lh.orig.nofix`, `rh.orig.nofix`) [10].
6. **Smooth, Inflate, & Quick Sphere**: `mris_smooth`, `mris_inflate`, and `mris_sphere -q` generate intermediate smoothed, inflated, and spherical surface files (`?h.smoothwm.nofix`, `?h.inflated.nofix`, `?h.qsphere.nofix`) [10].
7. **Automatic Topology Fixing**: `mris_fix_topology` removes handles/tunnels, verified via `mris_euler_number` to ensure a spherical topology, yielding `?h.orig` [10, 15].
8. **White Matter Surface Reconstruction**: `mris_make_surfaces -whiteonly` deforms `?h.orig` to follow gray/white matter intensity gradients, producing `?h.white`, `?h.curv`, `?h.area`, and `?h.cortex.label` [10].
9. **Surface Inflation**: `mris_smooth` creates `?h.smoothwm`, and `mris_inflate` generates `?h.inflated` along with sulcal depth maps `?h.sulc` [10].

#### Stage 3: `autorecon3` (Spherical Registration, Parcellation, & Morphometric Stats)
Handles atlas alignment, pial surface extraction, cortical parcellation, and summary table generation [9, 14, 16]:
1. **Spherical Surface Registration**: `mris_sphere` creates spherical meshes (`?h.sphere`), and `mris_register` aligns them to the `fsaverage` atlas curvature template (`?h.sphere.reg`) [16].
2. **Cortical Parcellation (Atlas Labeling)**: `mris_ca_label` applies surface atlas priors using `?h.sphere.reg` to create annotation files [14, 20, 21]:
   * **Desikan-Killiany Atlas**: `label/?h.aparc.annot` [8, 14]
   * **Destrieux Atlas**: `label/?h.aparc.a2009s.annot` [8, 20]
   * **DKT Atlas**: `label/?h.aparc.DKTatlas.annot` [21]
3. **Pial Surface Extraction**: `mris_make_surfaces` expands `?h.white` outwards to the gray matter/CSF boundary, generating `?h.pial`, cortical thickness maps (`?h.thickness`), `?h.area.pial`, and `?h.curv.pial` [12, 14].
4. **Cortical Ribbon & Parcellation-to-Volume**: `mri_aparc2aseg` maps cortical surface parcellations back into volume space (`aparc+aseg.mgz`, `aparc.a2009s+aseg.mgz`, `aparc.DKTatlas+aseg.mgz`, and `wmparc.mgz`) [20, 29, 30].
5. **Statistical Summary Generation**: 
   * `mri_segstats` extracts volume and intensity stats (`stats/aseg.stats`, `stats/wmparc.stats`) [9, 11, 30].
   * `mris_anatomical_stats` extracts cortical ROI metrics (`stats/?h.aparc.stats`, `stats/?h.aparc.a2009s.stats`, `stats/?h.aparc.DKTatlas.stats`) [9, 20-22].

---

### 3. Pipeline Outputs & Folder Structure

Every completed subject directory contains five primary output folders [31]:

```text
<subject_id>/
├── mri/         # Volumetric datasets (.mgz) and spatial transform matrices
├── surf/        # Surface mesh files and vertex-wise scalar overlays
├── label/       # Cortical masks, ROI labels, and parcellation annotation files
├── stats/       # ASCII text tables summarizing volume and surface morphometry
└── scripts/     # Execution logs, environmental status, and rerun command scripts
```

#### A. `mri/` Folder (Volumes & Transforms)
* **`orig.mgz` / `rawavg.mgz`**: Conformed T1w volume (\\(1\text{ mm}^3\\), \\(256^3\\)) [6, 7].
* **`nu.mgz`**: Non-uniformity/bias-corrected volume [7].
* **`T1.mgz`**: Intensity-normalized whole-head volume [7].
* **`norm.mgz`**: Normalized volume after CA atlas registration [10].
* **`brainmask.mgz`**: Skull-stripped brain volume [7, 32].
* **`brain.mgz` / `brain.finalsurfs.mgz`**: Intensity-normalized skull-stripped volume used as surface generation input [10, 32].
* **`aseg.mgz` / `aseg.auto.mgz`**: Automated subcortical structure segmentation volume [9-11].
* **`wm.mgz`**: Segmented white matter volume [10, 32].
* **`filled.mgz`**: Hemisphere-filled volume [10].
* **`ribbon.mgz`**: Binary cortical gray matter ribbon mask [20, 29].
* **`aparc+aseg.mgz` & `wmparc.mgz`**: Cortical and white matter parcellations mapped into volume space [29, 30].
* **`mri/transforms/`**: Registration transform files (`talairach.xfm`, `talairach.auto.xfm`, `talairach.lta`, non-linear `talairach.m3z`) [7, 9, 10].

#### B. `surf/` Folder (Surface Geometry & Scalar Maps)
Files are prefixed with `lh.` or `rh.` for left and right hemispheres [13]:
* **Surface Meshes**:
  * `?h.orig`: Initial topology-corrected surface mesh [10].
  * `?h.white`: Inner cortical surface boundary (gray/white matter interface) [10, 12, 13].
  * `?h.pial`: Outer cortical surface boundary (gray matter/CSF interface) [12-14].
  * `?h.midthickness`: Surface computed halfway between `white` and `pial` [12, 33, 34].
  * `?h.inflated`: Smoothly inflated cortical surface for viewing sulci [10, 12, 13].
  * `?h.sphere`: Spherical projection of the cortical surface [12, 16].
  * `?h.sphere.reg`: Spherical mesh non-linearly aligned to `fsaverage` atlas [16, 18, 19].
* **Vertex-Wise Scalar Maps**:
  * `?h.thickness`: Cortical thickness measurements at each vertex (\\(mm\\)) [9, 14, 35].
  * `?h.area` / `?h.area.pial`: Vertex-wise surface area (\\(mm^2\\)) [10, 14].
  * `?h.curv` / `?h.curv.pial`: Mean curvature values [10, 14, 35].
  * `?h.sulc`: Sulcal depth maps [10, 35].
  * `?h.jacobian_white`: Distortion/expansion factors from spherical warping [16].

#### C. `label/` Folder (Annotations & Masks)
* `?h.cortex.label`: Binary mask restricting analysis to cortical gray matter [10, 14].
* `?h.aparc.annot`: Desikan-Killiany parcellation annotation file [8, 14].
* `?h.aparc.a2009s.annot`: Destrieux parcellation annotation file [8, 20].
* `?h.aparc.DKTatlas.annot`: DKT atlas annotation file [21].
* `aparc.annot.ctab`: Color lookup table detailing structure IDs, names, and RGB colors [20].

#### D. `stats/` Folder (Tabular Text Statistics)
* **`aseg.stats`**: Subcortical ROI volumes (\\(mm^3\\)), estimated Total Intracranial Volume (eTIV / ICV), total cortical volume, and mean intensities [9, 11].
* **`wmparc.stats`**: Volume statistics for per-parcel white matter regions [30].
* **`lh.aparc.stats` & `rh.aparc.stats`**: ROI-level statistics for the Desikan-Killiany atlas [9, 20].
* **`lh.aparc.a2009s.stats` & `rh.aparc.a2009s.stats`**: ROI-level statistics for the Destrieux atlas [21].
* **`lh.curv.stats` & `rh.curv.stats`**: Surface curvature distribution summary [10].

#### E. Morphometry Metrics Summary
* **Volumetric Metrics**: Structure volume (\\(mm^3\\)), estimated Total Intracranial Volume (eTIV / ICV), total gray matter volume, subcortical gray matter volume, ventricular volume, mean voxel intensity [9, 11, 22, 36].
* **Surface Metrics**:
  * **Cortical Thickness (\\(mm\\))**: Perpendicular distance between white and pial surfaces [9, 20, 22].
  * **Surface Area (\\(mm^2\\))**: Total surface area of individual parcels/vertices [9, 10, 14, 22].
  * **Gray Matter Volume (\\(mm^3\\))**: Product of surface area and cortical thickness per parcel [9, 22].
  * **Curvature (\\(mm^{-1}\\) / \\(mm^{-2}\\))**: Integrated Rectified Mean Curvature and Integrated Rectified Gaussian Curvature [10, 22].
  * **Sulcal Depth (\\(mm\\))**: Displacement of sulci/gyri relative to the average surface [10, 35].
  * **Shape Indices**: Folding Index and Intrinsic Curvature Index [22].

---

### 4. Required File Structures & `SUBJECTS_DIR` Layout

FreeSurfer relies on environment variables to structure workspace inputs and outputs [3, 37, 38]:
* **`FREESURFER_HOME`**: Absolute path to the main FreeSurfer software installation directory [7, 11, 39, 40].
* **`SUBJECTS_DIR`**: Root directory containing subject output folders [3, 24, 31, 37, 38, 41]. (Specified in commands via `-sd <directory>`) [3, 37, 42].

#### Standard `SUBJECTS_DIR` Layout
```text
$SUBJECTS_DIR/
├── fsaverage/             <-- Shared atlas template directory (copied/symlinked from $FREESURFER_HOME) [40, 43, 44]
└── <subject_id>/          <-- Output folder generated for an individual subject [3, 31]
    ├── mri/
    │   ├── orig/          <-- Raw input files (001.mgz, 002.mgz, T2raw.mgz) [7]
    │   └── transforms/    <-- Registration matrix files (talairach.xfm, talairach.m3z) [7, 9, 10]
    ├── surf/              <-- Surface geometry files (lh.white, rh.pial) and scalar maps [13, 31]
    ├── label/             <-- Cortical masks and annotation files (lh.aparc.annot) [8, 14, 31]
    ├── stats/             <-- Summary statistics text files (aseg.stats, lh.aparc.stats) [9, 31]
    ├── scripts/           <-- Execution logs and status files (recon-all.log, recon-all.status) [31, 41]
    └── trash/             <-- Intermediary files marked for cleanup
```
