---
name: scientific-writing-neuro
description: Scientific methodology drafting, PRISMA literature review, zero-hallucination BibTeX verification, and COBIDAS reporting standards.
triggers:
  - generate Methods
  - verify BibTeX
  - literature synthesis
  - cobidas report
modalities:
  - table
  - report_qa
---

# Scientific Writer & Neuro-Reporting Skill

## 1. Core Responsibilities
- Compile end-to-end execution provenance from `execution_history.json` into publication-grade Markdown and LaTeX Methods sections.
- Enforce the COBIDAS guidelines (Committee on Best Practices in Data Analysis and Sharing) for MRI, fMRI, dMRI, and EEG/MEG.
- Enforce the Anti-Hallucination Citation Gate: every citation key in the generated manuscript must map to a verified DOI or PMID in `.neuri/references.bib`. Unverified references are strictly blocked.
- Synthesize literature searches and PRISMA flowcharts from PubMed, EuropePMC, and bioRxiv queries.

## 2. COBIDAS Reporting Checklist
Every generated Methods section must document:
1. **Sample & Demographics:** Total subject count, exclusions with explicit rationale, age (mean, SD, range), sex/gender distribution.
2. **Acquisition Parameters:** Scanner make/model, field strength (T), coil configuration, pulse sequence type, TR, TE, flip angle, FOV, matrix size, voxel dimensions, slice timing/order.
3. **Diffusion Imaging Specifics:** Number of gradient directions, b-values ($s/\text{mm}^2$), phase encoding directions (AP/PA for susceptibility correction), b0 count.
4. **Preprocessing Software & Versions:** Exact software versions (e.g., FSL v6.0.7, FreeSurfer v7.4.1, MNE-Python v1.6.0, ANTs v2.5.0), container SHA-256 hashes, and non-default CLI parameters.
5. **Statistical Modeling:** GLM design matrix rank, temporal filtering cutoff, autocorrelation corrections (e.g., AR(1)), and multiple comparisons corrections (FWE cluster-level or FDR $q < 0.05$).

## 3. Anti-Hallucination Citation Protocol
- Never fabricate a BibTeX key, author list, or publication year.
- When an agent generates a citation `\cite{Smith2023}`, the Writer Agent checks `citations_ledger` in the Blackboard.
- If the DOI is unverified, the Writer Agent queries `mcp-scholar` (`api.crossref.org`) to confirm existence and retrieve the official BibTeX entry before permitting it in the final document.
