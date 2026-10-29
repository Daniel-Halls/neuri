**`pydeface`** is a Python-based utility designed to remove facial structures from structural MRI volumes to facilitate subject anonymization [1, 2].

---

### **1. What `pydeface` Does**
* **Anonymization / Defacing:** Automatically strips facial features and ears from anatomical MRI scans by zeroing out those regions [1, 2].
* **Multi-Image Application:** Generates a subject-specific face mask and allows applying that same mask across multiple auxiliary images at once using the `--applyto` flag [1].

---

### **2. Defacing Process & Workflow**
* **FSL Dependency:** Requires **FSL** (specifically `FLIRT`) to be installed and accessible on the system executable path [3].
* **Image Registration:** Uses FSL’s `FLIRT` linear registration to align the input MRI to a target template [1, 3]. 
* **Registration Cost Function:** Defaults to **Mutual Information** (`--cost mutualinfo`), though alternative FSL-FLIRT cost functions can be specified [1, 3].
* **Temporary Transformation Workflows:** Automatically creates intermediate registration matrices and warped files (`template_reg_mat`, `warped_mask`, `template_reg`, `warped_mask_mat`) to warp the standard face mask into the subject's native image space [4].
* **Mask Application & Cleanup:** Applies the warped mask to mask out facial regions [1, 3, 4]. Unless `--nocleanup` is explicitly set, all temporary intermediate files are deleted upon completion [1, 3, 4].

---

### **3. Template and Facemask Usage**
* **Default Template:** If no custom target template is provided, `pydeface` uses its internal packaged template located at `data/mean_reg2mean.nii.gz` [5].
* **Default Facemask:** If no custom face mask is supplied, it defaults to its packaged mask located at `data/facemask.nii.gz` [5].
* **Custom Template (`--template <path>`):** Allows specifying an alternative registration target image [1, 3].
* **Custom Facemask (`--facemask <path>`):** Allows passing a custom binary face mask to replace the default mask [1, 3].

---

### **4. Outputs Generated**
* **Primary Output:** A defaced NIfTI image volume [1, 4].
* **Default Naming:** If `--outfile` is not specified, `pydeface` automatically appends the `_defaced` suffix to the input filename (e.g., `input_defaced.nii.gz`) [1, 4].
* **Overwriting Control:** Existing output files will not be overwritten unless the `--force` flag is provided [1, 4].

---

### **5. Required Input File Formats**
* **NIfTI Format:** Input files must be valid NIfTI images [1, 4].
* **Supported Extensions:** Accepts either uncompressed (`.nii`) or gzipped (`.nii.gz`) NIfTI files [3, 4]. Input files missing a `.nii` or `.nii.gz` extension will trigger a `ValueError` [3].
