---
name: fsl-atlas
description: Offline MNI152 coordinate-to-anatomy and region-to-coordinate lookup across 20 human FSL atlases without requiring FSL.
triggers:
  - MNI coordinates
  - MNI [
  - atlasquery
  - Harvard-Oxford
  - Juelich
  - Talairach
  - JHU tract
  - XTRACT
  - what brain region
  - ROI coordinates
modalities:
  - coordinates
  - structural
  - diffusion
---

# FSL Anatomical & White-Matter Atlas Skill

## 1. Core Mandate: Zero-Hallucination Brain Anatomy
When working with stereotactic coordinates or neuroimaging parcellations:
1. **NEVER Guess Coordinates or Anatomy**: Human memory and LLM pretraining often conflate adjacent Brodmann areas, hemisphere laterality, or gyral boundaries.
2. **Deterministic Lookup**: You have direct access to Neuri's offline FSL atlas database (`fsl_atlases.db`) containing **20 human MNI152 atlases** (Harvard-Oxford Cortical/Subcortical, Juelich Histological, Cerebellum, Talairach, JHU/XTRACT White-Matter Tracts, SMATT, and Striatal/Thalamic parcellations).
3. **No FSL Required**: Users do not need FSL, Nibabel, or an internet connection installed. The database is pre-compiled into a sub-millisecond sparse lookup table.

---

## 2. Mandatory Coordinate Routing Rules

### When the User Provides MNI Coordinates
*Examples: "What is at MNI [-24, -2, -20]?", "User attached MNI [40, 14, -8] from 3D viewer"*
1. **Query Tool**:
   - Use the `fsl_atlas` MCP tool:
     `query_mni_coordinate(x=<float>, y=<float>, z=<float>, include_neurosynth=True)`
   - Or if MCP is unavailable, execute the direct CLI command:
     `python scripts/query_fsl_atlas.py <X> <Y> <Z>`
2. **Report Concordant Parcellations**:
   - Report macro-anatomical labels and probability percentages from **Harvard-Oxford** (e.g. *Left Amygdala 92%*).
   - Report cytoarchitectonic sub-regions or Brodmann areas from **Juelich** (e.g. *GM Amygdala laterobasal group L 54%*).
   - Report white-matter fibers or tracts from **JHU-tracts** or **XTRACT** if probability $\ge 5\%$.
   - Synthesize the top functional associations from **Neurosynth** (e.g. *emotion, fear, memory*).

### When the User Requests Coordinates for a Brain Region
*Examples: "What are the MNI coordinates for the Left Insula?", "Give me a center coordinate for the Subthalamic Nucleus ROI"*
1. **Search Tool**:
   - Use the `fsl_atlas` MCP tool:
     `search_fsl_brain_region(query="<name>")`
   - Or execute CLI:
     `python scripts/query_fsl_atlas.py --search "<name>"`
2. **Use Exact Centers of Gravity**:
   - Always report the official FSL center-of-gravity `(x, y, z)` in MNI152 space.
   - Use these exact coordinates when writing Nilearn sphere extractors or FSL mask scripts (e.g. `nilearn.maskers.NiftiSpheresMasker(seeds=[(x, y, z)], radius=6)`).

---

## 3. Bundled 20 Human FSL Atlases Reference

- **Cortical & Subcortical**: `HarvardOxford-Cortical`, `HarvardOxford-Subcortical`
- **Cytoarchitectonics**: `Juelich` (121 cytoarchitectonic areas)
- **Hierarchical Gyrus/Brodmann**: `Talairach` (1,106 labels)
- **Gross Lobes**: `MNI` (9 structural tissue/lobe classes)
- **Cerebellum**: `Cerebellum_MNIfnirt`, `Cerebellum_MNIflirt` (28 cerebellar lobules)
- **Basal Ganglia & Thalamus**: `Thalamus`, `STN` (Subthalamic Nucleus), `Striatum-Structural`, `Striatum-Connectivity-3sub`, `Striatum-Connectivity-7sub`
- **White Matter Pathways**: `JHU-tracts`, `JHU-labels`, `XTRACT` (42 major pathways), `SMATT` (sensorimotor tracts)
- **Connectivity-Based**: `MarsParietalParcellation`, `MarsTPJParcellation`, `NeubertVentralFrontalParcellation`, `SalletDorsalFrontalParcellation`
