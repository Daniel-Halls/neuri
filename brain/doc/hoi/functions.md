The **HOI (Higher-Order Interactions)** package is a Python library built on top of JAX (supporting CPU, GPU, and TPU backends) designed to quantify statistical dependencies and functional interactions among two or more units using information-theoretic metrics [1-4]. It exposes a familiar Scikit-learn-style API [2, 5].

Below is a complete reference of all classes, functions, estimators, and metrics across the package's modules as documented in the sources [3, 6-9].

---

### 1. `hoi.metrics` — Higher-Order Interaction Estimators

#### **Base Class: `HOIEstimator`**
All metrics in `hoi.metrics` inherit from `HOIEstimator` [3, 10, 11].
* **Key Attributes**:
  * `entropies`: Array containing computed entropies for feature combinations [12, 13].
  * `multiplets`: Array of feature combination indices of shape `(n_mult, maxsize)` [12-14].
  * `order`: Order (size) associated with each multiplet [12-14].
  * `undersampling`: Theoretical threshold indicating potential sample size under-sampling [12, 13].
* **Core Methods**:
  * `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)`: Fits the estimator across specified multiplet sizes [15-17].
  * `compute_entropies(method='gc', minsize=1, maxsize=None, samples=None, **kwargs)`: Computes entropies for all multiplets [18-20].
  * `get_combinations(minsize, maxsize=None, astype='jax')`: Generates feature index combinations [21, 22].

---

#### **Network Behavior Metrics (Unsupervised Interaction Types)**
These metrics evaluate functional interaction patterns among subsets of variables within a network without an external target [23-25].

* **`Oinfo`**: `class Oinfo(x, y=None, multiplets=None, verbose=None)`
  * **What it does**: Computes the **O-information** (\\(\Omega(X^n) = TC(X^n) - DTC(X^n) = (n-2)H(X^n) + \sum [H(X_j) - H(X_{-j}^n)]\\)). It measures whether a multiplet is dominated by **redundancy** (\\(\Omega > 0\\)) or **synergy** (\\(\Omega < 0\\)) [11, 26-28].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [16, 29].
  * **Usage**: Characterizing higher-order functional dependencies and distinguishing synergistic vs. redundant network dynamics [23, 24, 30].

* **`InfoTopo`**: `class InfoTopo(x, y=None, verbose=None)`
  * **What it does**: Computes **Topological Information** (\\(I_k(X_1; \dots; X_k) = \sum_{i=1}^k (-1)^{i-1} \sum_{card(I)=i} H_i(X_I)\\)). Conditioned on lower orders, it isolates specific interaction orders to prevent spatial spreading of redundancy/synergy to larger orders (\\(I_k > 0 \Rightarrow\\) Redundancy, \\(I_k < 0 \Rightarrow\\) Synergy) [31-35].
  * **Arguments**: `fit(minsize=1, maxsize=None, method='gc', samples=None, **kwargs)` [36, 37]. Ignores `y` [38].
  * **Usage**: Pinpointing the exact size of interacting multiplets without higher-order artifactual spreading [32, 39].

* **`TC`**: `class TC(x, y=None, multiplets=None, verbose=None)`
  * **What it does**: Computes **Total Correlation** (\\(TC(X^n) = \sum_{j=1}^n H(X_j) - H(X^n)\\)), quantifying collective constraints and shared redundancy [26, 40-42].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [43, 44].
  * **Usage**: Measuring total shared redundancy and global dependency constraints across a set of variables [26, 45].

* **`DTC`**: `class DTC(x, y=None, multiplets=None, verbose=None)`
  * **What it does**: Computes **Dual Total Correlation** (\\(DTC(X^n) = H(X^n) - \sum_{j=1}^n H(X_j | X_{-j}^n)\\)), isolating shared randomness intrinsic to the system [26, 46, 47].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [15, 17].
  * **Usage**: Detecting intrinsic shared entropy and synergy structures [26].

* **`Sinfo`**: `class Sinfo(x, y=None, multiplets=None, verbose=None)`
  * **What it does**: Computes **S-information** (\\(S(X^n) = TC(X^n) + DTC(X^n) = n H(X^n) + \sum [H(X_j) + H(X_{-j}^n)]\\)), also called exogenous information [48-51].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [52, 53].
  * **Usage**: Measuring the total constraints in a system by combining redundant and synergistic contributions [30, 48].

---

#### **Network Encoding Metrics (Target-Directed Interactions)**
These metrics quantify how feature multiplets jointly encode information about an external target variable \\(Y\\) [25, 48, 54].

* **`GradientOinfo`**: `class GradientOinfo(x, y, multiplets=None, base_model=Oinfo, verbose=None)`
  * **What it does**: Computes **First-Order Gradient O-information** (\\(\partial_i \Omega(X^n) = \Omega(X^n, Y) - \Omega(X^n)\\)). Positive values indicate **redundant encoding** about target \\(Y\\), while negative values indicate **synergistic encoding** [48, 55-58].
  * **Arguments**: `x`, `y` (target feature array), `base_model` (default `Oinfo`), `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [56, 59-61].
  * **Usage**: Identifying feature multiplets that redundantly or synergistically encode an external target or behavior \\(Y\\) [24, 48, 54, 58].

* **`RSI`**: `class RSI(x, y, multiplets=None, verbose=None)`
  * **What it does**: Computes the **Redundancy-Synergy Index** (\\(RSI(S; Y) = I(S; Y) - \sum_{x_i \in S} I(x_i; Y)\\)). Positive values indicate synergy, negative values indicate redundancy regarding target \\(Y\\) [62-65].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [66, 67].
  * **Usage**: Disentangling target-specific synergistic vs. redundant information encoding [62, 65, 68].

* **`RedundancyMMI`**: `class RedundancyMMI(x, y, multiplets=None, verbose=None)`
  * **What it does**: Estimates **Redundancy via Minimum Mutual Information** (\\(Red(S; Y) = \min_{x_i \in S} I(X_i; Y)\\)) [69-71].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [72, 73].
  * **Usage**: Finding the baseline minimum redundant information shared between individual features and target \\(Y\\) [69].

* **`SynergyMMI`**: `class SynergyMMI(x, y, multiplets=None, verbose=None)`
  * **What it does**: Estimates **Synergy via Minimum Mutual Information** (\\(Syn(S; Y) = I(S; Y) - \max_{x_i \in S} I(S_{-i}; Y)\\)) [69, 74-76].
  * **Arguments**: `fit(minsize=2, maxsize=None, method='gc', samples=None, **kwargs)` [77, 78].
  * **Usage**: Quantifying additional information provided by the full multiplet \\(S\\) about \\(Y\\) compared to any \\(n-1\\) subset [69, 76].

* **`InfoTot`**: `class InfoTot(x, y, multiplets=None, verbose=None)`
  * **What it does**: Computes **Total Information** (\\(InfoTot(S; Y) = I(x_1, \dots, x_n; Y)\\)) between multiplet set \\(S\\) and target \\(Y\\) [79, 80].
  * **Arguments**: `fit(minsize=1, maxsize=None, method='gc', samples=None, **kwargs)` [81, 82].
  * **Usage**: Measuring full joint mutual information between feature multiplets and a target \\(Y\\) [79].

---

#### **Dynamic & Time-Series / Integrated Information (phiID) Metrics**
These metrics analyze temporal dependency and information flow across time points [83-86].

* **`MI`**: `class MI(x, multiplets=None, verbose=None)`
  * **What it does**: Computes **Pairwise Mutual Information** in dynamical systems (\\(I((X_i, X_j)_{t-\tau}; (X_i, X_j)_t)\\)) between past and future states [84, 87].
  * **Arguments**: `fit(minsize=2, tau=1, direction_axis=0, maxsize=2, method='gc', samples=None, matrix=False, **kwargs)` [88-90].
  * **Usage**: Evaluating temporal auto- and cross-mutual information across pairs of variables over delay \\(\tau\\) [84, 89].

* **`TransferEntropy`**: `class TransferEntropy(x, multiplets=None, verbose=None)`
  * **What it does**: Computes **Pairwise Transfer Entropy** (\\(T_{X_i \to X_j} = I(X_i(t-\tau); X_j(t) | X_j(t-\tau))\\)) [85, 91].
  * **Arguments**: `fit(minsize=2, tau=1, direction_axis=0, maxsize=2, method='gc', samples=None, matrix=False, **kwargs)` [92-94].
  * **Usage**: Measuring directed, delayed information flow from \\(X_i\\) to \\(X_j\\) in dynamic systems [85].

* **`RedundancyphiID`**: `class RedundancyphiID(x, multiplets=None, verbose=None)`
  * **What it does**: Computes the **redundancy-to-redundancy atom (\\(rtr\\))** of Integrated Information Decomposition (phiID) via MMI (\\(\min \{I(X_{t-\tau}; X_t), I(X_{t-\tau}; Y_t), I(Y_{t-\tau}; X_t), I(Y_{t-\tau}; Y_t)\}\\))[95-97].
  * **Arguments**: `fit(minsize=2, tau=1, direction_axis=0, maxsize=None, method='gc', samples=None, **kwargs)` [98-101].
  * **Usage**: Quantifying preserved double redundancy and information robustness across time [86, 95, 97].

* **`AtomsPhiID`**: `class AtomsPhiID(x, multiplets=None, verbose=None)`
  * **What it does**: Computes **Integrated Information Decomposition (phiID)** atoms for pairs of variables (\\(maxsize=2\\)) [102-105].
  * **Arguments**: `fit(minsize=2, tau=1, direction_axis=0, maxsize=2, method='gc', samples=None, atoms=['sts'], matrix=False, **kwargs)` [106-109]. Supported `atoms`: `'rtr'`, `'rtu1'`, `'rtu2'`, `'rts'`, `'u1tr'`, `'u2tr'`, `'str'`, `'u1tu1'`, `'u1tu2'`, `'u2tu1'`, `'u2tu2'`, `'stu1'`, `'stu2'`, `'u1ts'`, `'u2ts'`, `'sts'` [107, 109].
  * **Usage**: Decomposing temporal information dynamics into fine-grained phiID atoms (such as synergy-to-synergy `sts`) [83, 86, 102].

---

### 2. `hoi.core` — Core Information-Theoretic Functions & Combinatorics

#### **Entropy Estimation Factory & Functions**
* **`get_entropy(method='gc', **kwargs)`**: Factory function returning a JIT-compiled callable `fcn(x)` expecting shape `(n_features, n_samples)` [6, 110-112].
  * **Supported `method` options**:
    * `'gc'`: Gaussian Copula entropy (`entropy_gc`) [112-114].
    * `'gauss'`: Parametric Gaussian entropy (`entropy_gauss`) [112, 113, 115].
    * `'binning'`: Pre-discretized discrete Shannon entropy (`entropy_bin`) [112, 113, 116].
    * `'histogram'`: Histogram-based differential entropy (`entropy_hist`) [112, 113, 117].
    * `'knn'`: Kraskov \\(k\\)-nearest neighbor non-parametric estimator (`entropy_knn`) [112, 113, 118].
    * `'kernel'`: Gaussian kernel density estimation (`entropy_kernel`) [112, 113, 119].
    * `callable`: Custom JAX-written callable taking `(n_features, n_samples)` and returning a scalar float [111, 120, 121].
* **`entropy_gc(x, biascorrect=True, copnorm=True)`**: Computes Gaussian Copula entropy with optional bias correction and copula normalization [114, 122].
* **`entropy_gauss(x)`**: Computes parametric Gaussian entropy [114, 115].
* **`entropy_bin(x, base=2)`**: Computes discrete entropy on pre-binned data `x` [115, 116].
* **`entropy_hist(x, base=2, n_bins=8)`**: Computes differential entropy via histogram binning [117].
* **`entropy_knn(x, k=3)`**: Computes non-parametric entropy using the \\(k\\)-nearest neighbor distance [118].
* **`entropy_kernel(x, bw_method=None)`**: Computes entropy using Gaussian kernel density estimation [119].
* **`prepare_for_it(data, method, samples=None, **kwargs)`**: Preprocesses data arrays and handles sample indexing prior to information-theoretic calculations [6, 123].

#### **Mutual Information Factory Functions**
* **`get_mi(method='gc', **kwargs)`**: Factory function returning a callable `fcn(x, y)` for Mutual Information calculation between inputs `(n_features_x, n_samples)` and `(n_features_y, n_samples)` [3, 124-127].
* **`get_cond_mi(method='gc', **kwargs)`**: Factory function returning a callable `fcn(x, y, z)` for Conditional Mutual Information calculation \\(I(X; Y | Z)\\) [128].

#### **Combinatorics**
* **`combinations(n, minsize, maxsize=None, astype='iterator', order=False, fill_value=-1, target=None, directed=False)`**:
  * **What it does**: Generates all candidate feature index combinations (multiplets) [3, 129].
  * **Arguments**: `n` (total features), `minsize`, `maxsize`, `astype` (`'jax'`, `'numpy'`, `'iterator'`), `order`, `fill_value`, `target`, `directed` [116, 129].

---

### 3. `hoi.simulation` — Data Simulation

* **`simulate_hoi_gauss(n_samples=1000, target=False, triplet_character='synergy')`**:
  * **What it does**: Simulates multivariate Gaussian data containing 3-variable higher-order interactions with specified interaction character [130-133].
  * **Arguments**: `n_samples` (number of samples, default 1000), `target` (bool; if `True`, includes a 4th target variable \\(Y\\)), `triplet_character` (`'synergy'` or `'redundancy'`) [130, 131, 133].
  * **Returns**: Array `x` of shape `(n_samples, 3)` (or tuple `(x, y)` if `target=True`) [130, 132-134].
  * **Usage**: Creating benchmark datasets for validating HOI metrics [23, 130, 134].

---

### 4. `hoi.plot` — Visualizations

* **`plot_landscape(hoi, model=None, orders=None, minsize=None, maxsize=None, kind='hist', undersampling=True, cbar=True, hist_kwargs={}, plt_kwargs={})`**:
  * **What it does**: Generates a 2D landscape visualization showing how HOI estimates are distributed across multiplet orders [7, 135-137].
  * **Arguments**: `hoi` (HOI result array), `model` (HOIEstimator instance), `orders`, `minsize`/`maxsize`, `kind` (`'hist'` for 2D histogram or `'scatter'` for scatter plot), `undersampling` (bool, draws undersampling threshold line), `cbar`, `hist_kwargs`, `plt_kwargs` [136-138].
  * **Returns**: Matplotlib `Axes` instance [138, 139].

---

### 5. `hoi.utils` — Preprocessing & Postprocessing Utilities

#### **Preprocessing**
* **`digitize(x, n_bins, axis=0, use_sklearn=False, **kwargs)`**: Discretizes continuous variables into \\(n\\) discrete bins [8, 140]. `kwargs` are passed to `sklearn.preprocessing.KBinsDiscretizer` (e.g. `strategy='quantile'`) [140].
* **`normalize(x, to_min=0.0, to_max=1.0)`**: Rescales array values linearly between `to_min` and `to_max` [8, 9, 141].

#### **Postprocessing & Results Analysis**
* **`get_nbest_mult(hoi, model=None, orders=None, multiplets=None, n_best=5, minsize=None, maxsize=None, names=None)`**:
  * **What it does**: Extracts a pandas DataFrame containing the top \\(n\\) highest and lowest multiplets from an HOI result array [129, 141-143].
  * **Arguments**: `hoi` (HOI result array), `model` (optional HOIEstimator), `orders`, `multiplets`, `n_best` (default 5), `minsize`/`maxsize`, `names` (list of feature variable names) [141, 143].
  * **Returns**: `pandas.DataFrame` with columns for rank, order, HOI value, multiplet indices, and optional variable names [6, 142, 144].
* **`landscape(x, mult_size, n_bins=100, centered=False, stat='probability', output='numpy')`**: Computes the 2D histogram/density distribution array of HOI values across orders for custom landscape plotting [129, 145-147].

---