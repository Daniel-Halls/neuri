**`hoi` (Higher-Order Interactions)** is an open-source Python package designed to quantify statistical dependencies among 2 or more variables using information-theoretic metrics [1, 2]. Built on top of **JAX**, `hoi` enables vectorization and accelerated execution across CPU, GPU, and TPU hardware backends [1, 3].

---

### 1. Categories of Analysis
`hoi` divides information-theoretic metrics into two primary categories [4, 5]:
* **Network Behavior (Intrinsic)**: Quantifies collective, undirected functional interactions and internal dependencies within a group of variables \\(X^n = \{X_1, X_2, \dots, X_n\}\\) [4-6].
* **Network Encoding (Extrinsic)**: Quantifies the information carried by a group of variables about an external target variable \\(Y\\) [4, 5, 7].

---

### 2. Information-Theoretic Metrics Computed

#### **A. O-information (`hoi.metrics.Oinfo`)**
* **Definition**: Measures whether a subset of variables is dominated by **redundancy** or **synergy** [8-10]. It is defined as the difference between Total Correlation (\\(\text{TC}\\)) and Dual Total Correlation (\\(\text{DTC}\\)) [8, 10-12]:
  \\[\Omega(X^n) = \text{TC}(X^n) - \text{DTC}(X^n) = (n - 2) H(X^n) + \sum_{j=1}^{n} \left[ H(X_j) - H(X_{-j}^n) \right]\\] [8, 10, 12-14]
* **Interpretation & Sign Convention**:
  * \\(\Omega(X^n) > 0 \implies \text{\textbf{Redundancy}}\\) [10, 13-15]
  * \\(\Omega(X^n) < 0 \implies \text{\textbf{Synergy}}\\) [10, 13-15]

#### **B. S-information (`hoi.metrics.Sinfo`)**
* **Definition**: Also known as exogenous information, it represents the sum of Total Correlation (\\(\text{TC}\\)) and Dual Total Correlation (\\(\text{DTC}\\)) [16-20]:
  \\[S(X^n) = \text{TC}(X^n) + \text{DTC}(X^n) = n H(X^n) + \sum_{j=1}^{n} \left[ H(X_j) + H(X_{-j}^n) \right]\\] [16, 18, 20, 21]
* **Interpretation**: Measures the total amount of exogenous constraints ruling the system, capturing both redundancy and synergy concurrently [16, 18, 20].

#### **C. Core Components: Redundancy and Synergy Metrics**
* **Total Correlation (\\(\text{TC}\\), `hoi.metrics.TC`)**:
  \\[\text{TC}(X^n) = \sum_{j=1}^{n} H(X_j) - H(X^n)\\]
  Quantifies collective constraints and shared information (associated with redundancy) [8, 22, 23].
* **Dual Total Correlation (\\(\text{DTC}\\), `hoi.metrics.DTC`)**:
  \\[\text{DTC}(X^n) = H(X^n) - \sum_{j=1}^{n} H(X_j | X_{-j}^n) = (1 - n) H(X^n) + \sum_{j=1}^{n} H(X_{-j}^n)\\]
  Isolates shared randomness and collective interactions (associated with synergy) [8, 24, 25].
* **Topological Information (`hoi.metrics.InfoTopo`)**:
  \\[TI(X^n) = \sum_{i=1}^{n} (-1)^{i - 1} \sum_{S \subset [X^n], \text{card}(S)=i} H(S)\\]
  Conditioned on lower-order multiplets to prevent spatial spreading of interactions across orders [26-30]. \\(TI > 0 \implies \text{Redundancy}\\); \\(TI < 0 \implies \text{Synergy}\\) [27, 30, 31].
* **Gradient O-information (`hoi.metrics.GradientOinfo`)**:
  \\[\partial_{Y} \Omega(X^n) = \Omega(X^n, Y) - \Omega(X^n)\\]
  Measures the variation in O-information when adding an external target \\(Y\\) [16, 32-34]. \\(\partial_{Y} \Omega > 0 \implies \text{Redundant encoding}\\); \\(\partial_{Y} \Omega < 0 \implies \text{Synergistic encoding}\\) [35, 36].
* **Redundancy-Synergy Index (`hoi.metrics.RSI`)**:
  \\[\text{RSI}(S; Y) = I(S; Y) - \sum_{x_i \in S} I(x_i; Y)\\]
  Compares total joint mutual information to the sum of individual mutual informations [37-42]. \\(\text{RSI} > 0 \implies \text{Synergy}\\); \\(\text{RSI} < 0 \implies \text{Redundancy}\\) [37-40, 42].
* **Minimum Mutual Information Framework (`RedundancyMMI`, `SynergyMMI`)**:
  \\[\text{Red}_{\text{MMI}}(S; Y) = \min_{x_i \in S} I(x_i; Y)\\] [43-45]
  \\[\text{Syn}_{\text{MMI}}(S; Y) = I(S; Y) - \max_{x_i \in S} I(S_{-i}; Y)\\] [43, 45, 46]
* **Integrated Information Decomposition (\\(\phi\text{ID}\\), `AtomsPhiID`, `RedundancyphiID`)**:
  Decomposes dynamic information into atoms like \\(rtr\\) (redundancy-to-redundancy) and \\(sts\\) (synergy-to-synergy) across past and future states [47-54].

---

### 3. Inputs & Parameters

#### **Primary Data Inputs**
1. **Source Data (`x`)**: Standard array-like object representing the network variables [13, 21, 35, 55].
   * **2D Shape**: `(n_samples, n_features)` [13, 21, 35, 55].
   * **3D Shape**: `(n_samples, n_features, n_variables)` (used for time-varying/dynamic time series) [13, 21, 35, 55].
2. **Target Data (`y`)**: Required for network encoding metrics (`GradientOinfo`, `RSI`, `RedundancyMMI`, `SynergyMMI`, `InfoTot`) [35, 39, 56-60].
   * **Univariate Shape**: `(n_samples,)` [35, 39, 56, 58, 59].
   * **Multivariate Shape**: `(n_samples, n_target_features)` or `(n_samples, n_target_features, n_variables)` [56, 57, 61, 62].

#### **Model & Execution Parameters (`fit` method)**
* **`minsize`, `maxsize`** (`int`): Defines the minimum and maximum order (multiplet size) to analyze (e.g., `minsize=3, maxsize=3` for triplets) [63-70].
* **`method`** (`str` or `callable`): The entropy/mutual information estimation backend [63, 70-72]. Options include:
  * `'gc'`: Gaussian Copula entropy (default and recommended for continuous multivariate data) [63, 70, 72, 73].
  * `'gauss'`: Gaussian distribution assumption [63, 70-72].
  * `'binning'` / `'histogram'`: Discretization-based entropy [63, 70-72, 74, 75].
  * `'knn'`: \\(k\\)-Nearest Neighbor estimator [63, 70-72, 76].
  * `'kernel'`: Gaussian kernel density estimation [63, 70-72, 77].
  * Custom JAX-compatible callable function [63, 70, 78].
* **`samples`** (`ndarray`): Optional list of sample indices for bootstrapping or trial sub-selection [79-84].
* **`multiplets`** (`list` of `tuples`): Optional explicit list of node indices to evaluate (e.g., `[(0, 1, 2), (2, 7, 8)]`) rather than computing all \\(\binom{n}{k}\\) combinations [13, 21, 35, 55, 85].
* **`tau` & `direction_axis`**: Time delay and axis orientation parameters for dynamical metrics (`MI`, `TransferEntropy`, `RedundancyphiID`, `AtomsPhiID`) [86-89].

---

### 4. Outputs

1. **Interaction Values Array (`hoi`)**:
   * Returned by `.fit()` as a NumPy array of shape `(n_multiplets, n_variables)` storing computed metric values in bits [80-84, 90-93].
2. **Summary Table (`get_nbest_mult`)**:
   * Returns a Pandas DataFrame summarizing top \\(n\\) synergistic or redundant multiplets [94-97]. Includes columns: `index`, `order`, `hoi` (value), `multiplet` (tuple of indices), and optional variable `names` [94, 95, 97-99].
3. **Landscape Visualizations (`plot_landscape`)**:
   * Generates a 2D scatter or histogram plot depicting HOI values distributed across multiplet orders [100-102].

---

### 5. Data Structures

* **Input Arrays**: NumPy `ndarray` or JAX `jnp.ndarray` float arrays for variables \\(X\\) and target \\(Y\\) [1, 35, 80, 103].
* **Multiplets Representation**: JAX integer arrays or lists of tuples representing feature index combinations (with `-1` padding used internally for unused feature slots) [103-105].
* **JAX internal structures**: Uses JAX primitives (`vmap`, `lax.scan`, `jit`) for rapid memory layout transformation and parallel execution [106-111].
* **Pandas DataFrames**: Used for metric parameter tables, component metrics, and structured result summaries (`get_nbest_mult`) [94, 97, 112].
* **Hypergraph Structures**: Compatible with the `xgi.Hypergraph` class for network visualization of higher-order interactions [113, 114].

