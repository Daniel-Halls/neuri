---
name: fmri-postproc
description: Functional MRI postprocessing, confound regression, Nilearn GLM modeling, and Bayesian Simulation-Based Inference (SBI).
triggers:
  - fMRI preprocessing
  - GLM analysis
  - nuisance regression
  - bold connectivity
modalities:
  - bold
  - posterior
---

# Functional MRI & GLM Postprocessing Skill

## 1. Core Responsibilities
- Parse and ingest fMRIPrep BOLD derivatives (`_desc-preproc_bold.nii.gz`, `_desc-confounds_timeseries.tsv`).
- Construct nuisance confound models (6 motion parameters + derivatives, framewise displacement [FD], DVARS, anatomical CompCor).
- Build first-level and second-level General Linear Models (GLM) via Nilearn with canonical Hemodynamic Response Functions (HRF).
- Extract functional connectome correlation/covariance matrices using parcellation schemes (Schaefer-400, Glasser-360).
- Run Bayesian Simulation-Based Inference (SBI) with normalizing flows (NPE) and evaluate MCMC convergence gates.

## 2. Nilearn GLM Specification
```python
from nilearn.glm.first_level import FirstLevelModel
import pandas as pd

# 1. Load confounds and select nuisance regressors
confounds_df = pd.read_csv("sub-01_task-rest_desc-confounds_timeseries.tsv", sep="\t")
selected_confounds = confounds_df[
    ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z", "framewise_displacement"]
].fillna(0.0)

# 2. Fit First Level GLM
glm = FirstLevelModel(
    t_r=2.0,
    slice_time_ref=0.5,
    noise_model="ar1",
    standardize=True,
    signal_scaling=0,
    smoothing_fwhm=6.0,
    mask_strategy="epi",
)
glm.fit("sub-01_task-rest_desc-preproc_bold.nii.gz", confounds=selected_confounds)
```

## 3. Bayesian SBI & Neural Mass Model Convergence Gates
When executing Bayesian SBI or hierarchical models via PyMC / PyTorch SBI:
- **Gelman-Rubin Diagnostic:** $\hat{R} < 1.01$ across all sampled parameters.
- **Effective Sample Size:** Bulk ESS $> 400$ and Tail ESS $> 400$.
- **Divergences:** Zero divergent transitions allowed during sampling.
- **Posterior Predictive Checks (PPC):** Empirical functional connectivity eigenvalues must fall within the 95% posterior credible interval of simulated time-series.
