`pydeface` (v2.1.0) is a command-line utility designed to remove facial structures from structural MRI NIfTI images [1].

---

### **Usage Syntax**

```bash
pydeface [-h] [--outfile path] [--force] [--applyto [ ...]] [--cost mutualinfo] [--template path] [--facemask path] [--nocleanup] [--verbose] [--debug] path
``` [1]

---

### **Positional Arguments**

* **`path`** (or `infile`): Path to the input NIfTI image to be defaced [1, 2]. Must be a valid NIfTI file with a `.nii` or `.nii.gz` extension [3].

---

### **Optional Flags and Options**

* **`-h, --help`**: Displays the program help message and command syntax, then exits [1].
* **`--outfile path`**: Specifies the custom output file path [1]. If omitted, `pydeface` automatically appends the suffix `_defaced` to the input filename [1]. Output paths must have a `.nii` or `.nii.gz` extension [3].
* **`--force`**: Forces the tool to overwrite the output file if a file with the target output name already exists [1, 3].
* **`--applyto [ ...]`**: Applies the face mask computed from the primary image to one or more additional target NIfTI images [1]. Accepts multiple space-separated file paths as arguments [1].
* **`--cost mutualinfo`**: Specifies the cost function used by FSL's `FLIRT` tool during spatial registration [1, 3]. Default is `'mutualinfo'` [1, 3].
* **`--template path`**: Optional path to a custom registration target template image [1, 3]. If not specified, `pydeface` defaults to its internal template (`data/mean_reg2mean.nii.gz`) [2].
* **`--facemask path`**: Optional path to a custom face mask image to apply instead of the default [1, 3]. If not provided, it defaults to the internal face mask (`data/facemask.nii.gz`) [2].
* **`--nocleanup`**: Disables the automatic deletion of intermediate temporary files created during registration and masking [1]. Off by default [1].
* **`--verbose`**: Enables detailed status output and progress printing during execution [1, 3]. Off by default [1].
* **`--debug`**: Enables debug mode. Disables exception catching so that full tracebacks are displayed, automatically dropping the process into the Python debugger (`pdb`) upon error [1].

---

### **System Requirements & Constraints**

* **FSL Dependency**: `pydeface` requires FSL to be installed and accessible in the system execution PATH [3].
* **File Formats**: All input and output file paths must use `.nii` or `.nii.gz` suffixes [3].
