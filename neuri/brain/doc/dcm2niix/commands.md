### Syntax & Usage

The general command-line syntax for **`dcm2niix`** is:

```bash
dcm2niix [options] <in_folder>
``` [1]

The minimal command-line call passes only the path to the input DICOM folder:
```bash
dcm2niix /path/to/dicom/folder
``` [2]

---

### Command-Line Flags and Options

#### Short Option Flags

| Flag | Argument Type & Allowed Values | Default | Description |
| :--- | :--- | :--- | :--- |
| **`-1..-9`** | `integer` (`1..9`) | `6` | Set GZ compression level (`1` = fastest compression, `9` = smallest file size) [1]. |
| **`-a`** | `character` (`n`/`y`) | `n` | Adjacent DICOM mode; assumes images from the same series are always in the same folder for faster conversion [1]. |
| **`-b`** | `character` (`y`/`n`/`o`) | `y` | Generate BIDS sidecar JSON file (`y` = yes, `n` = no, `o` = only create JSON sidecar without NIfTI output) [1]. |
| **`-ba`** | `character` (`y`/`n`) | `y` | Anonymize BIDS sidecar JSON file [1]. |
| **`-c`** | `string` (up to 24 characters) | `""` | Comment stored in NIfTI `aux_file` field (e.g., `-c VIP`, or `""` to anonymize tag `0020,4000`) [1]. |
| **`-d`** | `integer` (`0..9`) | `5` | Set directory search depth for sub-folders within `in_folder` [1]. |
| **`-e`** | `character` (`y`/`n`/`o`/`j`/`b`) | `n` | Export alternative formats (`y` = NRRD, `o` = MGH, `j` = JSON/JNIfTI, `b` = BJNIfTI, `n` = NIfTI) [1]. |
| **`-f`** | `string` | `"%f_%p_%t_%s"` | Filename format template using string tokens [1, 3]. |
| **`-g`** | `character` (`y`/`n`/`o`/`i`) | `n` | Defaults file handling (`o` = reset and write defaults, `i` = ignore and reset defaults) [1]. |
| **`-h`** | None | — | Display help information [1]. |
| **`-i`** | `character` (`y`/`n`) | `n` | Ignore derived, localizer, and 2D images [1]. |
| **`-l`** | `character` (`y`/`n`/`o`) | `o` | Losslessly scale 16-bit integers to utilize full dynamic range (`y` = scale, `n` = no scale but convert `uint16` to `int16`, `o` = original) [1]. |
| **`-m`** | `character`/`integer` (`n`/`y` or `0`/`1`/`2`) | `2` | Merge 2D slices from the same series regardless of echo, exposure, etc. (`0` = no, `1` = yes, `2` = auto) [1]. |
| **`-n`** | `integer` | convert all | Convert only a specific series CRC number (can be specified up to 16 times) [1]. |
| **`-o`** | `path` | input folder | Specify the output directory [1]. |
| **`-p`** | `character` (`y`/`n`) | `y` | Use Philips precise float scaling instead of display scaling [1]. |
| **`-q`** | `character` (`y`/`l`/`n`) | `y` | Directory search verbosity (`y` = show count of DICOMs found, `l` = additionally list DICOMs found, `n` = quiet) [1]. |
| **`-r`** | `character` (`y`/`n`) | `n` | Rename DICOM files according to the `-f` naming scheme instead of converting to NIfTI [1, 4]. |
| **`-s`** | `character` (`y`/`n`) | `n` | Single file mode; do not convert other images present in the folder [1]. |
| **`-u`** | None | — | Perform an up-to-date version check [1]. |
| **`-v`** | `character`/`integer` (`n`/`y` or `0`/`1`/`2`) | `0` | Verbosity level (`0` = no/quiet, `1` = yes, `2` = logorrheic) [1]. |
| **`-w`** | `integer` (`0`/`1`/`2`) | `2` | Write behavior for filename conflicts (`0` = skip duplicates, `1` = overwrite, `2` = add letter suffix) [1]. |
| **`-x`** | `character` (`y`/`n`/`i`) | `n` | Crop 3D acquisitions (`y` = crop, `n` = no crop, `i` = ignore: neither crop nor rotate 3D acquisitions) [1]. |
| **`-z`** | `character`/`integer` (`y`/`o`/`i`/`n`/`3`) | `n` | GZ compression mode (`y` = pigz, `o` = optimal pigz, `i` = internal miniz, `n` = no compression, `3` = uncompressed 3D) [1]. |

#### Extended / Long Flags

| Flag | Argument Type & Allowed Values | Default | Description |
| :--- | :--- | :--- | :--- |
| **`--big-endian`** | `character` (`y`/`n`/`o`) | `o` | Byte order specification (`y` = big-endian, `n` = little-endian, `o` = optimal/native) [1]. |
| **`--progress`** | `character` (`y`/`n`) | `n` | Format progress information for 3D Slicer [1]. |
| **`--ignore_trigger_times`** | None | — | Disregard DICOM trigger values in tags `0018,1060` and `0020,9153` [1]. |
| **`--terse`** | None | — | Omit filename disambiguation post-fixes (can cause file overwrites if series collide) [1, 5]. |
| **`--version`** | None | — | Report program version number [1]. |
| **`--xml`** | None | — | Output 3D Slicer-formatted feature descriptions [1]. |

---

### Filename Format Tokens (`-f`)

When formatting output filenames via `-f`, the following tokens expand into specific DICOM header values [1, 3]:

* **`%a`**: Antenna / coil name (from Siemens tag `0051,100F`) [1, 3].
* **`%b`**: Basename (file name of the first DICOM) [1, 3].
* **`%c`**: Comments (from DICOM tag `0020,4000`) [1, 3].
* **`%d`**: Protocol description (from DICOM tag `0008,103E`) [1, 3].
* **`%e`**: Echo number (from DICOM tag `0018,0086`) [1, 3].
* **`%f`**: Folder name containing the first DICOM [1, 3].
* **`%g`**: Accession number (from DICOM tag `0008,0050`) [1, 3].
* **`%h`**: Hazardous experimental BIDS file naming scheme (`h` for default, `H` for reproin style) [3].
* **`%i`**: Patient ID (from DICOM tag `0010,0020`) [1, 3].
* **`%j`**: Series Instance UID (from DICOM tag `0020,000E`) [1, 3].
* **`%k`**: Study Instance UID (from DICOM tag `0020,000D`) [1, 3].
* **`%l`**: Local procedure step description (from DICOM tag `0040,0254`) [3].
* **`%m`**: Manufacturer short name (from tag `0008,0070`: GE, Ph, Si, To, UI, NA) [1, 3].
* **`%n`**: Patient name (from DICOM tag `0010,0010`) [1, 3].
* **`%o`**: Media Object Instance UID (from DICOM tag `0002,0003`) [1, 3].
* **`%p`**: Protocol name (from tag `0018,1030`; if empty, uses SequenceName `0018,0024`) [1, 3].
* **`%r`**: Instance number (from DICOM tag `0020,0013`) [1, 3].
* **`%s`**: Series number (from DICOM tag `0020,0011`) [1, 3].
* **`%t`**: Study acquisition date/time (from tags `0008,0020` and `0008,0030`) [1, 3].
* **`%u`**: Acquisition number (from DICOM tag `0020,0012`) [1, 3].
* **`%v`**: Vendor long name (from tag `0008,0070`: GE, Philips, Siemens, Toshiba, UIH, NA) [1, 3].
* **`%x`**: Study ID (from DICOM tag `0020,0010`) [1, 3].
* **`%y`**: GE RawDataRunNumber (`0019,10A2`) or TemporalPosition (`0020,0100`) [3].
* **`%z`**: Sequence name (from DICOM tag `0018,0024`) [1, 3].

---

### Disambiguation Filename Post-Fixes

Unless running in `--terse` mode, `dcm2niix` automatically appends specific post-fixes to disambiguate additional dimensions or sub-types within a series [5, 6]:

* **`_cNx.._cNz`**: Antenna/coil designation (used when multi-channel coil data is saved uncombined) [6].
* **`_e1..eN`**: Echo index for multi-echo acquisitions [6].
* **`_Eq`**: Applied when 2D slice spacing varies across a volume (resliced to equidistant spacing, common in CT) [6].
* **`_i1..N`**: Image number for non-parallel slice stacks [6].
* **`_imaginary`**: Imaginary channel of complex image reconstructions [6].
* **`_MoCo`**: Appended to Protocol Name if DICOM Image Type (`0008,0008`) contains 'MOCO' (motion correction) [6].
* **`_ph`**: Phase map [6].
* **`_phMag`**: Phase and magnitude stored together in the 4th dimension [6].
* **`_r1..rN`**: Repetition index for sequences with multiple repetition times [6].
* **`_real`**: Real channel of complex image reconstructions [6].
* **`_t`**: Cardiac trigger delay time recorded when non-zero (from tags `0020,9153` or `0018,1060`) [6].
* **`_Tilt`**: Slices resampled to remove CT gantry tilt skew [6].
* **`_ROIn`**: Region-of-interest binary overlay planes (`N` ranging from 1 to 16) [5].
