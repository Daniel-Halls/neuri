The `pydeface` package contains functions split between its primary module (`pydeface`) and its utility submodule (`pydeface.utils`) [1, 2]. Below is a complete breakdown of all available Python functions documented in the sources [1-5].

---

### **Core `pydeface` Functions**

#### **1. `deface_image`**
* **Module**: `pydeface` [5]
* **Description**: Performs the primary defacing workflow on a target structural MRI volume [3, 5]. It verifies FSL availability, resolves target paths, registers the face mask to the anatomical scan using FSL FLIRT, and applies the transformed face mask to zero out facial features [3, 5].
* **Arguments**:
  * `infile` (*str, required*): Path to the input NIfTI image (`.nii` or `.nii.gz`) [3, 5].
  * `outfile` (*str, optional*): Output NIfTI image path. If not specified, appends the `_defaced` suffix to the input filename [3-5].
  * `facemask` (*str/path, optional*): Custom face mask NIfTI file to use instead of the default mask (`facemask.nii.gz`) [2, 3, 5].
  * `template` (*str/path, optional*): Custom target template NIfTI image to use as the registration target instead of the default (`mean_reg2mean.nii.gz`) [2, 3, 5].
  * `cost` (*str, optional*): FSL FLIRT registration cost function; defaults to `'mutualinfo'` [3, 5].
  * `force` (*bool, optional*): Forces overwriting of the output file if it already exists; defaults to `False` [3-5].
  * `forcecleanup` (*bool, optional*): Forces cleanup of temporary files; defaults to `False` [3, 5].
  * `verbose` (*bool, optional*): Enables status logging and prints temporary file paths; defaults to `True` [3-5].
  * `**kwargs`: Accepts additional keyword parameters (e.g., `applyto` to apply the generated face mask to secondary co-registered images) [3, 5].
* **Use Case**: Python scripts or automated neuroimaging preprocessing pipelines needing programmatically invoked face stripping to anonymize MRI scans before public sharing [3, 5].

#### **2. `is_interactive`**
* **Module**: `pydeface` [1]
* **Description**: Evaluates whether standard input, output, and error streams (`sys.stdin`, `sys.stdout`, `sys.stderr`) are attached to an interactive terminal session (TTY) [1].
* **Arguments**: None [1].
* **Use Case**: Used internally during exception handling to determine whether the execution context can safely drop into an interactive `pdb` debugger [1, 3].

#### **3. `setup_exceptionhook`**
* **Module**: `pydeface` [1]
* **Description**: Overloads standard Python system exception handling (`sys.excepthook`) with `pydeface`'s custom exception hook handler [1].
* **Arguments**: None [1].
* **Use Case**: Formats unhandled exceptions during command-line execution or redirects errors when debugging flags are enabled [1, 3].

#### **4. `main`**
* **Module**: `pydeface` [2]
* **Description**: Handles CLI argument parsing via `argparse.ArgumentParser` and triggers the defacing pipeline [2, 3].
* **Arguments**: None (parses command-line arguments directly from `sys.argv`) [2].
* **Use Case**: Entry point when calling `pydeface` directly from the terminal or bash scripts [2, 3].

---

### **`pydeface.utils` Submodule Functions**

#### **5. `initial_checks`**
* **Module**: `pydeface.utils` [2]
* **Description**: Runs initial sanity checks and sets default resource file locations for the template image and face mask if they are omitted [2].
* **Arguments**:
  * `template` (*str/path, optional*): Path to the template image. Defaults to `pydeface/data/mean_reg2mean.nii.gz` via `importlib.resources.files` [2].
  * `facemask` (*str/path, optional*): Path to the face mask image. Defaults to `pydeface/data/facemask.nii.gz` via `importlib.resources.files` [2].
* **Use Case**: Pre-execution check ensuring that standard template and facemask resources exist before registration commands are executed [2].

#### **6. `output_checks`**
* **Module**: `pydeface.utils` [4]
* **Description**: Determines and verifies the output destination filename based on input naming and user overwrite options [4].
* **Arguments**:
  * `infile` (*str, required*): Path to input NIfTI image [4].
  * `outfile` (*str, optional*): Desired output path. If `None`, automatically replaces `.nii` in `infile` with `_defaced.nii` [4].
  * `force` (*bool, optional*): Indicates whether existing output files can be overwritten; defaults to `False` [4].
* **Use Case**: Validates output filenames and prevents accidental file overwrites prior to running heavy calculations [4].

#### **7. `generate_tmpfiles`**
* **Module**: `pydeface.utils` [4]
* **Description**: Creates temporary scratch files using `tempfile.mkstemp` required during registration and mask warping [4].
* **Arguments**:
  * `verbose` (*bool, optional*): When `True`, prints paths of created temporary files; defaults to `True` [4].
* **Returns**: A tuple containing four file paths: `(template_reg, template_reg_mat, warped_mask, warped_mask_mat)` [4].
* **Use Case**: Pre-allocates temporary files for storing FSL FLIRT registration outputs (`.nii.gz` volumes and `.mat` transformation matrices) [4].

#### **8. `cleanup_files`**
* **Module**: `pydeface.utils` [4, 5]
* **Description**: Iterates through a provided list of file paths, checks for their existence using `os.path.exists`, and deletes them via `os.remove` [5].
* **Arguments**:
  * `*args`: Variable list of file path strings to be removed [5].
* **Use Case**: Post-processing cleanup to purge temporary registration matrices and intermediate files created during defacing [4, 5].

#### **9. `get_outfile_type`**
* **Module**: `pydeface.utils` [5]
* **Description**: Identifies the FSL output data type identifier based on the file extension suffix of the output path [5].
* **Arguments**:
  * `outpath` (*str, required*): Output file path string [5].
* **Returns**: `'NIFTI_GZ'` if `outpath` ends with `.nii.gz`, or `'NIFTI'` if it ends with `.nii` (raises a `ValueError` if any other suffix is supplied) [5].
* **Use Case**: Formats output string identifiers required when passing parameters to FSL tools like `flirt` [5].

---

Would you like a sample Python script showing how to integrate `deface_image` into a batch processing workflow for a BIDS dataset?
