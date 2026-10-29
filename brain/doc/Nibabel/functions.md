A reference manual of the primary functions, classes, methods, spatial affine utilities, and header manipulation APIs in **NiBabel** is provided below.

---

### 1. Global Input/Output Functions and Serialization API

NiBabel provides top-level I/O functions and instance methods to handle reading, writing, and byte-stream serialization across neuroimaging file formats [1-3].

#### `nibabel.load(filename)`
* **Parameters**: 
  * `filename` (*str* or *Path*) — The file path to the image dataset (e.g., `.nii`, `.nii.gz`, `.hdr`, `.gii`, `.dscalar.nii`) [4-7].
* **Return Value**: An instance of a format-specific image class (e.g., `Nifti1Image`, `Nifti2Image`, `Nifti1Pair`, `Cifti2Image`, or `GiftiImage`) [4-7].
* **Raises**: 
  * `ImageFileError`: Raised if the file format or magic header bytes are not recognized [6, 7].
  * `OSError` / `FileNotFoundError`: Raised if the target path does not exist [6, 7].
* **Usage**: Universal entry point for loading neuroimaging datasets into Python [4, 5]. NiBabel inspects file headers and magic bytes to construct the appropriate image object dynamically [4, 5].

#### `nibabel.save(img, filename)`
* **Parameters**:
  * `img` (*SpatialImage* or *DataobjImage*) — The NiBabel image instance to write [5, 7, 8].
  * `filename` (*str* or *Path*) — Output destination file path [5, 7, 8].
* **Return Value**: `None` [5, 8].
* **Usage**: Saves an image object to disk [5, 8, 9]. If the destination filename extension differs from the original class, `save()` attempts automatic format conversion [2].

#### `img.to_filename(filename)`
* **Parameters**:
  * `filename` (*str* or *Path*) — Target file path [2, 10].
* **Return Value**: `None` [2, 10].
* **Usage**: Instance method called directly on an image object to save its data and header to disk while updating its internal `file_map` filename references [2, 10, 11].

#### `img.to_bytes()`
* **Parameters**: None [2].
* **Return Value**: `bytes` — Serialized byte string representation of the image stream [2].
* **Usage**: Serializes single-file image datasets (supported for NIfTI-1, NIfTI-2, GIFTI, and MGH formats) into byte strings for stream-based I/O or network transfers [2, 12].

#### Related Serialization and Path Methods
* **`img.get_filename()`**: Returns the primary file path string associated with the image's `file_map`, or `None` if created purely in memory [10].
* **`img.set_filename(filename)`**: Updates path references inside the image's internal `file_map` mapping without immediately performing disk I/O [10, 11].
* **`img.from_bytes(bytestring)`**: Class/instance method that deserializes an image directly from an in-memory byte string [2, 12].

---

### 2. Primary Spatial Image Classes

NiBabel encapsulates volumetric arrays, surface geometry, and metadata into specialized object classes [1, 13].

#### `Nifti1Image`
`nibabel.nifti1.Nifti1Image(dataobj, affine, header=None, extra=None, file_map=None, dtype=None)` [14]

* **Parameters**:
  * `dataobj`: \\(N\\)-dimensional numerical array or `ArrayProxy` object [14, 15].
  * `affine`: \\((4 \times 4)\\) homogeneous transformation matrix mapping voxel array indices to RAS+ world coordinates [13, 14].
  * `header` (*optional*): `Nifti1Header` instance or mapping structure [14, 16].
  * `extra` (*optional*): Dictionary for storing extra non-standard metadata attributes [14, 16].
  * `file_map` (*optional*): Mapping of file keys (e.g., `'image'`) to `FileHolder` objects [10, 14, 16].
* **Return Value**: A instantiated single-file NIfTI-1 image object [5, 14].
* **Key Attributes & Methods**:
  * `header_class`: Alias pointing to `Nifti1Header` [17].
  * `valid_exts`: Tuple of valid file extensions (`('.nii',)` or compressed `.nii.gz`) [2, 17].
  * `update_header()`: Synchronizes header metadata fields (`dim`, `datatype`, `pixdim`) with the shape, dtype, and affine of `dataobj` [17, 18].
* **Usage**: Primary container for standard 3D/4D volumetric structural, functional, and diffusion MRI data [1, 2].

#### `Nifti2Image`
`nibabel.nifti2.Nifti2Image(dataobj, affine, header=None, extra=None, file_map=None, dtype=None)` [15, 19]

* **Parameters**: Identical argument signature to `Nifti1Image` [14, 15].
* **Return Value**: A single-file 64-bit NIfTI-2 image instance [15, 19].
* **Key Attributes & Methods**:
  * `header_class`: Alias pointing to `Nifti2Header` [20].
  * Uses 64-bit integers (`int64_t`) and double-precision floats (`double`) in its header structure to support high-resolution matrices and large spatial dimensions exceeding 32,767 voxels along an axis [21, 22].
* **Usage**: Used for large-scale volumetric datasets where NIfTI-1 16-bit dimension fields hit overflow limits [21, 22].

#### `Cifti2Image`
`nibabel.cifti2.Cifti2Image(dataobj=None, header=None, nifti_header=None, extra=None, file_map=None, dtype=None)` [23, 24]

* **Parameters**:
  * `dataobj`: Array-like matrix containing grayordinate scalar, time-series, or parcellated data [1, 23].
  * `header`: `Cifti2Header` instance or a sequence of `cifti2_axes.Axis` instances (such as `BrainModelAxis`, `ParcelsAxis`, `SeriesAxis`, `ScalarAxis`, or `LabelAxis`) describing matrix dimensions [23].
  * `nifti_header` (*optional*): `Nifti2Header` instance used as the outer container wrapper [23].
* **Return Value**: A CIFTI-2 composite volume/surface image object [1, 23].
* **Key Methods**:
  * `update_headers()`: Harmonizes outer NIfTI-2 container dimensions with internal CIFTI-2 matrix shape specifications [23].
* **Usage**: Standard container for combined cortical surface mesh vertices and subcortical volume voxels used in Human Connectome Project (HCP) pipelines [1, 23].

#### `GiftiImage`
`nibabel.gifti.GiftiImage(darrays=None, meta=None, labeltable=None)` [24, 25]

* **Parameters**:
  * `darrays` (*optional*): Sequence of `GiftiDataArray` instances representing coordinate vertices, triangle faces, or per-vertex scalar data [25].
  * `meta` (*optional*): `GiftiMetaData` instance containing key-value metadata [25].
  * `labeltable` (*optional*): `GiftiLabelTable` instance mapping integer keys to region names and RGBA colors [25].
* **Return Value**: A GIFTI surface image object [1, 25].
* **Key Methods**:
  * `add_data_array(data_array)`: Appends a new `GiftiDataArray` object to the surface dataset [25].
  * `to_xml()`: Converts the surface mesh and metric data into GIFTI XML text format [25].
* **Usage**: Representation of cortical surface geometries, mesh topology, and surface-mapped metrics [1, 25].

---

### 3. Spatial Geometry, Affines, and Coordinate Systems

NiBabel maps spatial arrays into physical world space using homogeneous affine transformations, enforcing a Right-Anterior-Superior (RAS+) coordinate space [13, 26, 27].

#### Mathematical Affine Mapping
A \\((4 \times 4)\\) affine matrix \\(A\\) relates array indices \\((i, j, k)\\) to world RAS+ coordinates \\((x, y, z)\\) [13, 27]:

\\[\begin{bmatrix} x \\ y \\ z \\ 1 \end{bmatrix} = A \begin{bmatrix} i \\ j \\ k \\ 1 \end{bmatrix}\\]

#### Affine Utility Functions

##### `apply_affine(aff, pts)`
* **Parameters**:
  * `aff`: \\((4 \times 4)\\) affine transformation matrix [28].
  * `pts`: Coordinate point array of shape \\((N, 3)\\) or \\((3,)\\) [28].
* **Return Value**: Transformed physical RAS+ coordinate array [28].
* **Usage**: Applies matrix coordinate transformation to points without explicit matrix multiplication overhead [28].

##### `nibabel.aff2axcodes(affine)`
* **Parameters**:
  * `affine`: \\((4 \times 4)\\) spatial transformation matrix [28, 29].
* **Return Value**: Tuple of axis orientation code strings (e.g., `('R', 'A', 'S')` or `('L', 'P', 'I')`) [28, 29].
* **Usage**: Determines anatomical direction encoded along each array axis [28, 29].

##### `nibabel.affines.voxel_sizes(affine)` / `header.get_zooms()`
* **Parameters**:
  * `affine` / `header`: Spatial affine matrix or header object [28-31].
* **Return Value**: Tuple of voxel dimensions in millimeters (plus Repetition Time TR in seconds for temporal 4D series) [28, 30, 31].
* **Usage**: Extracts spatial voxel spacing along array axes [28, 30, 31].

#### Three-Tier Affine Selection Algorithm (`get_best_affine()`)
When reading NIfTI files, NiBabel selects the primary image affine using a three-tier hierarchy [27, 32]:
1. **sform affine**: Selected if `sform_code != 0`, reading transformation values from header fields `srow_x`, `srow_y`, `srow_z` [27, 32].
2. **qform affine**: Selected if `sform_code == 0` and `qform_code != 0`, reconstructed from quaternion parameters (`quatern_b`, `quatern_c`, `quatern_d`), offsets (`qoffset_x`, `qoffset_y`, `qoffset_z`), and sign flip `qfac` [27, 33].
3. **Fall-back header affine**: Fallback matrix constructed from `pixdim` voxel dimensions when both codes are zero, placing origin coordinates at the central voxel [27, 34].

---

### 4. Header Manipulation and Data Scaling API

NiBabel exposes format-specific headers via both raw dictionary-like item access and validated accessor methods [27, 30].

#### Access Patterns
* **Dict-Like Item Access** (`hdr['pixdim']`, `hdr['descrip']`): Directly queries or modifies raw C-structure header fields without applying safety range checks [27, 30].
* **Validated Getter/Setter Methods**: Methods that enforce format constraints, validate value combinations, and synchronize dependent header attributes safely [27].

#### Key Header Methods

##### `get_data_shape()` / `set_data_shape(shape)`
* **Parameters**: `shape` — Tuple of integers defining \\(N\\)-dimensional array dimensions [31, 35].
* **Return Value**: Tuple representing array shape (`dim` header field) [30, 31, 35].

##### `get_data_dtype()` / `set_data_dtype(dtype)`
* **Parameters**: `dtype` — Target NumPy data type or string alias (e.g., `np.int16`, `np.float32`, `'uint8'`) [30, 36].
* **Return Value**: On-disk binary NumPy data type [30, 37, 38].

##### `get_zooms()` / `set_zooms(zooms)`
* **Parameters**: `zooms` — Tuple of floating-point voxel dimensions and temporal TR [30, 31].
* **Return Value**: Tuple containing physical voxel dimensions in mm and TR in seconds [30, 31].

##### `get_sform(coded=False)` / `set_sform(affine, code=None)`
* **Parameters**:
  * `affine`: \\((4 \times 4)\\) array or `None` [39, 40].
  * `code`: Integer or string alignment label (e.g., `0` for unknown, `1` for scanner RAS+, `3` for Talairach, `4` for MNI) [32, 39, 40].
  * `coded` (*optional, bool*): If `True`, returns both affine matrix and integer sform code [39, 41].
* **Return Value**: \\((4 \times 4)\\) sform affine matrix (or `None` if `sform_code == 0` when `coded=True`) [32, 36, 39].

##### `get_qform(coded=False)` / `set_qform(affine, code=None, strip_shears=True)`
* **Parameters**:
  * `affine`: \\((4 \times 4)\\) array or `None` [40, 42].
  * `code`: Integer or string qform code [40, 42].
  * `strip_shears` (*bool*): If `True`, silently removes non-orthogonal shear factors to allow valid quaternion encoding [40].
  * `coded` (*optional, bool*): If `True`, returns both reconstructed affine and qform code [37, 42].
* **Return Value**: \\((4 \times 4)\\) qform affine matrix reconstructed from quaternions [33, 41, 42].

##### `get_slope_inter()` / `set_slope_inter(slope, inter)`
* **Parameters**: `slope` (*float*), `inter` (*float*) — Scaling slope and intercept values [43].
* **Return Value**: Tuple `(scl_slope, scl_inter)` [43].
* **Data Scaling Formula**: Binary data on disk \\(D_{\text{raw}}\\) is converted to floating-point physical values \\(Y\\) during `get_fdata()` access via [43]:

\\[Y = D_{\text{raw}} \cdot \text{scl\_slope} + \text{scl\_inter}\\]

##### `get_intent()` / `set_intent(code, params=(), name='')`
* **Parameters**:
  * `code`: Integer or string NIfTI intent code (e.g., t-statistic, Z-score, vector, label) [25, 42].
  * `params`: Tuple of floating-point parameters for the intent distribution [42].
  * `name`: Text description string [42].
* **Return Value**: Tuple `(code, parameters, name)` [42].

---