---
name: eeg-meg-pipeline
description: Electrophysiology preprocessing, MNE-Python bad channel detection, ICA artifact removal, and source reconstruction.
triggers:
  - ICA cleaning
  - time-frequency
  - source estimation
  - eeg preprocessing
modalities:
  - eeg
  - meg
  - ieeg
---

# Electrophysiology (EEG/MEG) Pipeline Skill

## 1. Core Responsibilities
- Validate electrode montages and 3D digitized sensor locations (standard 10-20, 10-05, or Polhemus head coordinates).
- Detect noisy, flat, or bridged bad channels automatically using RANSAC or correlation thresholds before re-referencing.
- Remove ocular (EOG) and cardiac (ECG) artifacts using Independent Component Analysis (FastICA / Infomax) without suppressing neural signals.
- Execute Morlet wavelet and multitaper time-frequency spectral decomposition.
- Reconstruct cortical source dynamics using Forward Modeling (BEM) and Inverse Operators (dSPM, sLORETA, LCMV beamformers).

## 2. MNE-Python Standard Workflow
```python
import mne

# 1. Read raw BIDS-compatible recording
raw = mne.io.read_raw_edf("sub-01_task-rest_eeg.edf", preload=True)

# 2. Filter (0.5 Hz high-pass to remove slow drift, 100 Hz low-pass, 50/60 Hz notch)
raw.filter(l_freq=0.5, h_freq=100.0, fir_design="firwin")
raw.notch_filter(freqs=[50.0, 100.0], fir_design="firwin")

# 3. Mount standard montage and re-reference to average
montage = mne.channels.make_standard_montage("standard_1020")
raw.set_montage(montage, on_missing="ignore")
raw.set_eeg_reference("average", projection=True)

# 4. Independent Component Analysis (ICA)
ica = mne.preprocessing.ICA(n_components=25, method="fastica", random_state=42)
ica.fit(raw)

# Automatically find ocular components using frontal channel proxies (Fp1/Fp2)
eog_indices, eog_scores = ica.find_bads_eog(raw, ch_name="Fp1")
ica.exclude = eog_indices
raw_clean = ica.apply(raw.copy())
```

## 3. Electrophysiology Guardrails
- **Reference Integrity:** Never apply average reference before identifying and excluding bad channels.
- **Filter Phase Distortion:** Use zero-phase forward-backward FIR filtering (`fir_design="firwin"`) to prevent phase shifts in ERP peak latencies.
- **Component Rejection Limit:** Never reject more than 20% of ICA components (typically 1-3 components for blinks/saccades/heartbeat).
