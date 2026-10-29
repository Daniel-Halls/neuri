`dcm2niix` is an open-source command-line tool written in C (developed by Chris Rorden) designed to convert raw medical imaging data from vendor DICOM (and Philips PAR/REC) formats into the standard NIfTI format [1-6].

---

### 1. What `dcm2niix` Does

* **DICOM to NIfTI Conversion**: DICOM is a complex clinical standard created by equipment manufacturers that stores 2D slice files or 3D datasets alongside extensive header metadata and protected health information (PHI) [1, 2, 7, 8]. NIfTI is a simple 3D/4D format favored by neuroimaging researchers because it explicitly defines spatial orientations, requires equidistant slices, and can be easily anonymized [1-3, 8, 9]. `dcm2niix` serves as the open-source successor to `dcm2nii` [1, 3].
* **Core Conversion Pipeline**: `dcm2niix` scans DICOM directories, parses vendor-specific private headers, sorts series by acquisition criteria, stacks 2D slices into 3D/4D NIfTI volumes, calculates correct spatial transformation matrices (qform/sform), removes PHI to anonymize datasets, and exports acquisition metadata into sidecar files [3, 9-13].
* **DICOM Organization / Renaming Mode**: In addition to NIfTI conversion, `dcm2niix` includes a DICOM organization mode (`-r y`) that copies and renames raw DICOM files into organized directory structures based on header attributes without altering DICOM header contents or converting them to NIfTI [11, 14-16].

---

### 2. Conversion Logic Across Vendor DICOMs

`dcm2niix` contains dedicated logic to handle proprietary and non-standard DICOM implementations across major manufacturers, including Siemens, General Electric (GE), Philips, Canon (Toshiba), and UIH [1, 13, 17, 18].

#### Siemens
* **Mosaic De-mosaicing**: Unpacks Siemens 2D mosaic representations of functional and diffusion images into standard 3D/4D volumes, supported by options like `-assume_dicom_mosaic` [19-21].
* **Multi-Echo & Fieldmaps**: Siemens gradient-echo fieldmaps frequently assign identical series and image numbers to multiple echoes; `dcm2niix` detects these conflicts and appends `_e2` to separate second-echo files [9, 22].
* **Motion Correction Detection**: Distinguishes raw EPI runs from scanner-generated motion-corrected runs by inspecting `ImageType (0008,0008)` and appending `_MoCo` to protocol names [9].
* **CSA Header Parsing**: Reads Siemens CSA headers to extract acquisition parameters such as `SliceTiming`, `PhaseEncodingDirection`, and `TotalReadoutTime` [19, 23-25].

#### General Electric (GE)
* **Phase Encoding & Acceleration**: Decodes private tag `0043,102A` (Ky traversal direction) to determine phase encoding polarity and private tag `0043,1083` (Asset R Factors) to calculate in-plane parallel reduction factors [26, 27].
* **Arterial Spin Labeling (ASL)**: Processes GE product ASL sequences by identifying interleaved Perfusion Weighted (PW) tag/control images and Proton Density (PD) reference volumes [28].
* **Complex Image Components**: Maps signed short values in private tag `0043,102F` to identify magnitude (`0`), phase (`1`), real (`2`), and imaginary (`3`) image components [29].
* **Localizer Filtering**: Detects 3-plane scout/localizer images via `SeriesPlane (0019,1017)` (value `256`) to ignore them when using `-i y` [29].

#### Philips
* **Precise Scaling**: Supports Philips precise float scaling versus display scaling via the `-p` flag [11].
* **Derived Volume Separation**: Philips DWI sequences often append calculated isotropic, ADC, or trace volumes to the gradient series; `dcm2niix` separates these into an `_ADC` file, which can be ignored using `-i y` [30].
* **Fieldmap Extraction**: Detects unwrapped B0 fieldmaps (in Hz) and appends `_fieldmaphz` [30].
* **Header Underspecification**: Handles cases where Philips DICOM headers lack standard entries for parameters like `SliceTiming` or `PhaseEncodingDirection` [17, 24, 31].

#### Spatial Reslicing Logic
* **Equidistant Slice Resampling**: The NIfTI standard requires uniform slice spacing across 3D volumes; `dcm2niix` detects non-equidistant slice spacing (common in CT gantry tilts or variable MRI slice acquisition) and reslices volumes to create equal spacing, tagging output files with `_Eq` or `_Tilt` [9].

---

### 3. Tool Outputs & Generated File Formats

* **NIfTI Volumes (`.nii` / `.nii.gz` / `.nii.zst`)**:
  * Outputs uncompressed `.nii` files or compressed `.nii.gz` images using internal `miniz`, system `zlib`, or external `pigz` parallel compression [3, 11, 32].
  * Supports Zstandard compression (`.nii.zst`) via `-z s` [32].
  * Allows exporting to alternative formats via `-e y/o/j/b`, such as NRRD (`.nrrd`), MGH (`.mgh`), or JNIfTI / JSON (`.json`) [11, 33].
* **BIDS JSON Sidecars**:
  * Generated automatically alongside NIfTI volumes when enabled with `-b y` [11, 34].
  * Stores vendor-agnostic metadata required by BIDS pipelines, such as `EchoTime`, `RepetitionTime`, `FlipAngle`, `PhaseEncodingDirection`, `TotalReadoutTime`, `SliceTiming`, and `Manufacturer` [11, 23, 24, 35].
  * **`BidsGuess` Metadata**: Inserts an experimental `BidsGuess` field into JSON sidecars (v1.0.20230731+) to assist automated BIDS conversion tools (e.g., `ezBIDS`, `niix2bids`) by suggesting probable BIDS datatypes (e.g., `anat`) and filename entities (e.g., `_acq-`, `_run-`, `_T1w`) [17, 36, 37].
* **Diffusion Gradient Text Files (`.bvecs` / `.bvals`)**:
  * For Diffusion-Weighted Imaging (DWI) scans, `dcm2niix` exports unit normal gradient vectors into a 3-row `.bvec` (or `.bvecs`) file and b-values into a single-row `.bval` (or `.bvals`) file [33, 38-41].
* **Disambiguation Postfixes**:
  * Appends suffixes to distinguish multiple images or dimensions generated from a single DICOM series [9, 12]:
    * `_e1.._eN`: Echo numbers in multi-echo sequences [9, 22].
    * `_c1.._cN`: Uncombined antenna/coil channels [9].
    * `_ph`, `_real`, `_imaginary`: Phase, real, or imaginary components of complex images [9].
    * `_MoCo`: Scanner motion-corrected runs [9].
    * `_t`: Cardiac trigger delay times [9].
    * `_ADC`: Derived Philips isotropic/trace DWI volumes [30].
    * `_fieldmaphz`: Unwrapped Philips B0 fieldmaps in Hz [30].

---

### 4. Required File Structures, CLI Usage & Configuration

#### Directory Search & Input Structure
* `dcm2niix` recursively searches input directories up to a specified search depth (`-d`, default 5) [11].
* DICOM files belonging to a specific scan or series are best isolated into separate subfolders or series directories to prevent file naming conflicts or unintended batching [10, 42, 43].

#### Command-Line Flags Reference

| Option Flag | Description | Values / Defaults |
| :--- | :--- | :--- |
| `-o` | Output directory path | Default: input folder [6, 11, 44] |
| `-f` | Output filename template string | Default: `%f_%p_%t_%s` [11, 44] |
| `-z` | Gzip compression mode | `y` (pigz), `i` (internal miniz), `n` (no), `o` (optimal pigz), `3` (no, 3D) [11, 34, 44] |
| `-1` .. `-9` | Compression level | `1`=fastest, `9`=smallest, default `6` [11] |
| `-b` | Generate BIDS sidecar JSON | `y` (yes), `n` (no), `o` (sidecar JSON only) [11, 34] |
| `-ba` | Anonymize BIDS sidecar output | `y` (yes), `n` (no), default `y` [11, 34] |
| `-i` | Ignore derived, localizer, and 2D images | `y` (yes), `n` (no), default `n` [11, 29, 45, 46] |
| `-m` | Merge 2D slices from same series | `0` (no), `1` (yes), `2` (auto), default `2` [11, 46] |
| `-r` | Rename/organize DICOMs without converting | `y` (yes), `n` (no), default `n` [11, 16] |
| `-w` | Write behavior on filename conflicts | `0` (skip), `1` (overwrite), `2` (add suffix), default `2` [11, 46] |
| `-p` | Philips precise float scaling | `y` (yes), `n` (no), default `y` [11] |
| `-d` | Directory search depth | `0`..`9`, default `5` [11] |

#### Filename Format Specifiers (`-f`)
* `%p`: Protocol name [11, 18, 44]
* `%s`: Series number [11, 18, 44]
* `%t`: Study date/time [11, 18, 44]
* `%i`: Patient ID [11, 18]
* `%n`: Patient name [11, 18]
* `%m`: Manufacturer short name [11, 18]
* `%v`: Vendor long name [11, 18]
* `%e`: Echo number [11, 18]
* `%a`: Antenna / coil name [11, 18]
* `%f`: Target folder name [11, 18]
* `%h`: Experimental BIDS file naming scheme [11, 18, 47]

#### Batch Processing (`dcm2niibatch`)
* `dcm2niibatch` acts as a wrapper around `dcm2niix` that accepts a YAML configuration file (e.g., `dcm2niibatch batch_config.yml`) [4, 48-50].
* The YAML file lists conversion targets with parameters such as `in_dir` (input DICOM directory), `out_dir` (output directory), and `filename` (naming template) to automate processing across multi-subject studies [49, 51, 52].

#### Defaults Configuration File
* Default options can be managed in the persistent `.dcm2nii.ini` file using the `-g` flag (`-g y` writes defaults; `-g o` resets and writes defaults; `-g i` ignores defaults) [11].
