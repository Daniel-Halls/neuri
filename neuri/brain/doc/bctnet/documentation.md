The **Brain Connectivity Toolbox** (`bctnet`) is a MATLAB library designed for complex network (graph) analysis of structural and functional neuroimaging datasets [1, 2]. It is widely used in network neuroscience and has been ported to or integrated into numerous neuroimaging software suites, including `bctpy`, `bct-cpp`, the Human Connectome Project (HCP), DSI Studio, CONN, and the Virtual Brain Project [3, 4].

---

### 1. Required Matrix Structures & Network Types

`bctnet` categorizes input network structures into four primary network types, alongside signed matrix variants [5]:
* **`BU`**: Binary Undirected
* **`WU`**: Weighted Undirected (including signed variants)
* **`BD`**: Binary Directed
* **`WD`**: Weighted Directed

#### Matrix Properties and Formatting Constraints:
* **Square Matrices**: Matrices must be \\(N \times N\\), where rows and columns denote network nodes (such as parcellated brain regions or cortical vertices), and entries represent connection links/edges [6-8].
* **Network Size**: Designed for networks typically exceeding 20 nodes [6].
* **Symmetry**: Undirected networks require symmetric matrices; directed networks can be asymmetric [5, 8].
* **Weight-to-Distance Mapping**: Distance-based functions require weighted matrices mapped to lengths/distances (commonly via weight inversion) rather than raw correlation/connection strengths [9].
* **Sparsity & Preprocessing Utilities**: Functions like `threshold_absolute.m`, `threshold_proportional.m`, and `weight_conversion.m` are provided to threshold, binarize, normalize, or repair input connection weight matrices [8, 10].

---

### 2. Computed Brain Network Measures

#### **Degree & Density**
* **Node Degree**: Total count of links connected to a node (`degrees_und.m`, `degrees_dir.m` for in-degree and out-degree) [11].
* **Node Strength**: Sum of incoming/outgoing link weights (`strengths_und.m`, `strengths_dir.m`, `strengths_und_sign.m`) [11, 12].
* **Joint Degree**: Matrix quantifying nodes with \\(u\\) outgoing and \\(v\\) incoming connections (`jdegree.m`) [12].
* **Network Density**: Proportion of present connections relative to all possible connections (`density_und.m`, `density_dir.m`) [13].

#### **Clustering & Local Integration**
* **Clustering Coefficient**: Fraction of a node's neighbors that are connected to one another (`clustering_coef_bu.m`, `clustering_coef_bd.m`, `clustering_coef_wu.m`, `clustering_coef_wd.m`, `clustering_coef_wu_sign.m`) [14, 15].
* **Transitivity**: Overall ratio of triangles to triplets in the network (`transitivity_bu.m`, `transitivity_bd.m`, `transitivity_wu.m`, `transitivity_wd.m`) [15, 16].
* **Local Efficiency**: Global efficiency evaluated on a node's immediate neighborhood (`efficiency_bin.m`, `efficiency_wei.m`) [16, 17].

#### **Modularity & Community Structure**
* **Community Detection Algorithms**: Subdivides the network to maximize within-group connections and minimize between-group connections:
  * `community_louvain.m`: Louvain community detection with fine-tuning for binary, weighted, directed, and signed networks [18, 19].
  * `modularity_und.m`, `modularity_dir.m`: Newman's spectral community detection [19].
  * `link_communities.m`: Detects overlapping community structures [18, 19].
  * `clique_communities.m`: Overlapping community detection via clique percolation [19, 20].
* **Consensus Partitioning**: Resolves modularity degeneracy (`agreement.m`, `consensus_und.m`) [21].
* **Partition Distance**: Quantifies similarity between community partitions using variation of information and mutual information (`partition_distance.m`) [22, 23].

#### **Efficiency & Diffusion**
* **Global Efficiency**: Average inverse shortest path length across the entire network (`efficiency_bin.m`, `efficiency_wei.m`, `rout_efficiency.m`) [9, 17, 24].
* **Diffusion Efficiency**: Inverse of the mean first passage time for a random walker (`diffusion_efficiency.m`) [20, 24, 25].
* **Resource Efficiency**: Quantifies particle/message efficiency along shortest paths (`resource_efficiency_bin.m`) [25].

#### **Path Length & Distances**
* **Shortest Path & Distance Matrices**:
  * `distance_bin.m` & `reachdist.m`: Algebraic distance and reachability matrices [26].
  * `breadthdist.m`: Memory-efficient breadth-first search distance calculation [26].
  * `distance_wei.m` & `distance_wei_floyd.m`: Shortest path calculations using Dijkstra's or Floyd-Warshall algorithms [9, 20].
  * `retrieve_shortest_path.m`: Returns the specific node sequence along a shortest path [26].
* **Global Topological Metrics**:
  * `charpath.m`: Computes characteristic path length (mean shortest path length), node eccentricity, network radius (minimum eccentricity), and network diameter (maximum eccentricity) [9, 17].

#### **Centrality**
* **Betweenness Centrality**: Fraction of all shortest paths passing through a node (`betweenness_bin.m`, `betweenness_wei.m`) or an edge (`edge_betweenness_bin.m`, `edge_betweenness_wei.m`) [27, 28].
* **Within-Module Degree Z-Score**: Node degree centrality evaluated strictly within its assigned community module (`module_degree_zscore.m`) [28].
* **Participation, Gateway, & Diversity Coefficients**: Quantifies the diversity of a node's intermodular connections (`participation_coef.m`, `participation_coef_sign.m`, `gateway_coef_sign.m`, `diversity_coef_sign.m`) [28-30].
* **Eigenvector & PageRank Centrality**: Self-referential centrality based on connections to other highly central nodes (`eigenvector_centrality_und.m`, `pagerank_centrality.m`) [30, 31].
* **Subgraph Centrality & K-Coreness Centrality**: `subgraph_centrality.m`, `kcoreness_centrality_bu.m`, `kcoreness_centrality_bd.m`, and `flow_coef_bd.m` [31, 32].

#### **Motifs & Self-Similarity**
* **Structural Motifs**: Counts 3-node and 4-node connectivity patterns occurring at statistically significant frequencies, along with weighted motif intensity and coherence (`motif3struct_bin.m`, `motif4struct_bin.m`, `motif3struct_wei.m`, `motif4struct_wei.m`; requires `motif34lib.mat` generated via `make_motif34lib.m`; motif legend mapped via `find_motif34.m`) [33, 34].
* **Functional Motifs**: Subsets of functional connection patterns embedded within structural motifs (`motif3funct_bin.m`, `motif4funct_bin.m`, `motif3funct_wei.m`, `motif4funct_wei.m`) [34, 35].
* **Quasi-idempotence**: Quantifies how close a weighted connection matrix is to being idempotent (`quasi_idempotence.m`) [35, 36].

---

### 3. Inputs & Outputs Summary

| Component | Description |
| :--- | :--- |
| **Inputs** | • Primary: Square \\(N \times N\\) connectivity matrices (correlation, coherence, or streamline counts) [6, 8, 37].<br>• Secondary: Weight-to-distance transformation matrices [9]; community partition vectors [21, 28]; spatial coordinates (for Rentian scaling) [14]; motif library definitions (`motif34lib.mat`) [33, 35]. |
| **Outputs** | • **Nodal Vectors (\\(N \times 1\\))**: Degree, strength, clustering coefficient, local efficiency, betweenness centrality, participation coefficient, within-module z-score.<br>• **Pairwise Matrices (\\(N \times N\\))**: Distance matrix, reachability matrix, edge betweenness, topological overlap.<br>• **Global Scalars**: Characteristic path length, global efficiency, transitivity, density, modularity statistic \\(Q\\), assortativity, radius, diameter.<br>• **Community Vectors (\\(N \times 1\\))**: Module affiliation indexes.<br>• **Motif Profiles**: Frequency, intensity, and coherence arrays across motif ID classes [33, 34]. |
