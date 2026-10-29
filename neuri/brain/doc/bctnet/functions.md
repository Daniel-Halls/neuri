The **Brain Connectivity Toolbox (BCT / bctnet)** is a MATLAB toolbox designed for complex graph-theoretical analysis of structural and functional neuroimaging datasets [1, 2]. BCT categorizes network representations into four primary matrix formats:
* **BU**: Binary Undirected
* **WU**: Weighted Undirected
* **BD**: Binary Directed
* **WD**: Weighted Directed

---

### 1. Degree, Strength, and Similarity Measures

* **`degrees_und.m` (BU, WU)** & **`degrees_dir.m` (BD, WD)**
  * **Function**: Computes node degree (total number of links connected to each node) [3]. For directed networks, it calculates in-degree (\\(k_{in}\\)) and out-degree (\\(k_{out}\\)) separately [3].
  * **Parameters**: Binary or weighted adjacency matrix (\\(A\\) or \\(W\\)) [3].
  * **Return Values**: Vector of node degrees \\(k\\) (or two vectors \\(k_{in}\\) and \\(k_{out}\\)) [3].
  * **Use Case**: Basic network density analysis and hub identification based on connection count [3].
* **`strengths_und.m` (WU)** & **`strengths_dir.m` (WD)**
  * **Function**: Computes node strength (sum of link weights connected to a node) [3]. For directed networks, it returns in-strength (\\(s_{in}\\)) and out-strength (\\(s_{out}\\)) [3, 4].
  * **Parameters**: Weighted adjacency matrix (\\(W\\)) [4].
  * **Return Values**: Vector of node strengths \\(s\\) (or \\(s_{in}\\) and \\(s_{out}\\)) [4].
  * **Use Case**: Quantifying nodal connection capacity/intensity in weighted connectomes [4].
* **`strengths_und_sign.m` (WU Signed)**
  * **Function**: Calculates node strength separately for positive and negative weights in signed undirected networks [4].
  * **Parameters**: Signed weighted adjacency matrix (\\(W\\)) [4].
  * **Return Values**: Positive node strength vector \\(s^+\\) and negative node strength vector \\(s^-\\) [4].
  * **Use Case**: Analyzing functional connectivity networks containing both positive correlations and anti-correlations [4].
* **`jdegree.m` (BD, WD)**
  * **Function**: Computes the joint degree distribution matrix [4]. Element \\((u, v)\\) represents the number of nodes in the network that have \\(u\\) outgoing connections and \\(v\\) incoming connections [4].
  * **Parameters**: Directed adjacency matrix [4].
  * **Return Values**: Joint degree matrix \\(J(u, v)\\) [4].
  * **Use Case**: Evaluating asymmetry and joint degree properties between input and output connectivity [4].
* **`gtom.m` (BU)**
  * **Function**: Generalized Topological Overlap Measure (\\(m\\)-th step) [5]. Quantifies the degree to which a pair of nodes share similar \\(m\\)-th step neighbors (nodes reachable within \\(m\\) steps) [4, 5].
  * **Parameters**: Binary undirected matrix \\(A\\), step \\(m\\) [5].
  * **Return Values**: Topological overlap matrix \\(GTOM\\) [5].
  * **Use Case**: Identifying functionally or structurally equivalent node pairs beyond direct connections [5].
* **`edge_nei_overlap_bu.m` (BU)** & **`edge_nei_overlap_bd.m` (BD)**
  * **Function**: Calculates the overlap between the neighborhoods of pairs of nodes linked by edges [5].
  * **Parameters**: Binary adjacency matrix \\(A\\) [5].
  * **Return Values**: Matrix of edge neighborhood overlap values [5].
  * **Use Case**: Evaluating link redundancy and local edge robustness [5].
* **`matching_ind_und.m` (BU)** & **`matching_ind.m` (BD)**
  * **Function**: Computes the matching index, which quantifies the similarity/overlap in connection patterns between any two nodes \\(u\\) and \\(v\\) (ignoring self-connections and direct \\(u\\)-\\(v\\) connections) [5, 6].
  * **Parameters**: Adjacency matrix \\(A\\) [6].
  * **Return Values**: Symmetric matching index matrix \\(M\\) [5, 6].
  * **Use Case**: Assessing functional homophily or structural similarity between brain regions [5, 6].

---

### 2. Density and Physical Spatial Scaling

* **`density_und.m` (BU, WU)** & **`density_dir.m` (BD, WD)**
  * **Function**: Calculates network density (the fraction of present connections relative to all possible connections) [6].
  * **Parameters**: Adjacency matrix \\(A\\) or \\(W\\) [6].
  * **Return Values**: Scalar density \\(k_{density}\\), total number of nodes \\(N\\), and total number of links \\(K\\) [6].
  * **Use Case**: Global sparseness assessment and wiring cost evaluation [6].
* **`rentian_scaling_2d.m`** & **`rentian_scaling_3d.m` (BU)**
  * **Function**: Calculates physical Rentian scaling, a topo-physical metric combining topological network organization with 2D or 3D physical spatial coordinates [7, 8].
  * **Parameters**: Binary undirected matrix \\(A\\), matrix of 2D/3D nodal physical coordinates [7].
  * **Return Values**: Rentian scaling exponent \\(t\\), block sizes, and internal/external connection counts [7].
  * **Use Case**: Analyzing physical wiring cost optimization versus topological efficiency in brain networks [6, 7].

---

### 3. Segregation, Clustering, and Community Structure (Modularity)

* **`clustering_coef_bu.m` (BU)**, **`clustering_coef_bd.m` (BD)**, **`clustering_coef_wu.m` (WU)**, **`clustering_coef_wd.m` (WD)**
  * **Function**: Computes the node clustering coefficient (fraction of triangles around a node, or fraction of neighbors that are neighbors of each other) [7].
  * **Parameters**: Adjacency/weight matrix \\(A\\) or \\(W\\) [7].
  * **Return Values**: Nodal clustering coefficient vector \\(C\\) [7].
  * **Use Case**: Measuring local segregation, local cliquishness, and local fault tolerance [7].
* **`clustering_coef_wu_sign.m` (WU Signed)**
  * **Function**: Generalizes the weighted clustering coefficient for networks containing both positive and negative weights (e.g., Costantini & Perugini variants) [7, 9-11].
  * **Parameters**: Signed weighted adjacency matrix \\(W\\) [7].
  * **Return Values**: Vector of signed clustering coefficients [7].
  * **Use Case**: Evaluating local segregation in functional correlation networks with anti-correlations [7, 9, 11].
* **`transitivity_bu.m` (BU)**, **`transitivity_bd.m` (BD)**, **`transitivity_wu.m` (WU)**, **`transitivity_wd.m` (WD)**
  * **Function**: Computes network transitivity (ratio of triangles to triplets across the entire network) [11, 12].
  * **Parameters**: Adjacency or weight matrix [11].
  * **Return Values**: Scalar transitivity value \\(T\\) [11].
  * **Use Case**: Global measure of segregation without nodal degree bias [11].
* **`efficiency_bin.m` (BU, BD)** & **`efficiency_wei.m` (WU, WD)**
  * **Function**: Computes global efficiency (average inverse shortest path length) and/or local efficiency (global efficiency computed on node neighborhoods) [10, 13-16].
  * **Parameters**: Adjacency/weight matrix, local efficiency flag [14, 16].
  * **Return Values**: Scalar global efficiency \\(E_{glob}\\) or vector of local efficiencies \\(E_{loc}\\) [14, 16].
  * **Use Case**: Measuring parallel information transfer capacity globally and locally [14, 16].
* **`get_components.m` (BU)**
  * **Function**: Identifies connected components (subnetworks where all pairs of nodes are mutually connected by paths) [14].
  * **Parameters**: Binary undirected matrix \\(A\\) [14].
  * **Return Values**: Component assignment vector \\(comp\\) and size of each component [14].
  * **Use Case**: Detecting isolated sub-graphs and verifying network connectedness [14].
* **`community_louvain.m` (BU, BD, WU, WD, Signed)**
  * **Function**: Louvain community detection algorithm with fine-tuning for modularity maximization [17-19]. Replaces older `modularity_louvain.m` and `modularity_finetune.m` scripts [17].
  * **Parameters**: Adjacency/weight matrix \\(W\\), resolution parameter \\(\gamma\\), signed treatment options [17-19].
  * **Return Values**: Community affiliation vector \\(M\\) and modularity statistic \\(Q\\) [19].
  * **Use Case**: Unsupervised partitioning of brain networks into non-overlapping functional or structural modules [14, 19].
* **`modularity_und.m` (BU, WU)** & **`modularity_dir.m` (BD, WD)**
  * **Function**: Newman's deterministic spectral community detection algorithm [10, 12, 19].
  * **Parameters**: Connectivity matrix \\(A\\) or \\(W\\) [19].
  * **Return Values**: Module affiliation vector \\(Ci\\) and modularity \\(Q\\) [19].
  * **Use Case**: Deterministic modularity decomposition [10, 19].
* **`link_communities.m` (BU, BD, WU, WD)**
  * **Function**: Link-based community detection algorithm that identifies overlapping communities (where nodes can belong to multiple modules) [17, 19].
  * **Parameters**: Connectivity matrix \\(A\\) or \\(W\\) [19].
  * **Return Values**: Link community affiliation matrix and node membership matrix [19].
  * **Use Case**: Mapping overlapping brain modules and multi-functional gateway regions [19].
* **`clique_communities.m` (BU)**
  * **Function**: Clique-percolation community detection algorithm for detecting overlapping modules [8, 19].
  * **Parameters**: Binary matrix \\(A\\), clique size \\(k\\) [8, 19].
  * **Return Values**: Overlapping community assignment matrix [19].
  * **Use Case**: Identifying dense overlapping subgraphs and shared module boundaries [19].
* **`agreement.m`** & **`agreement_weighted.m` (BU, BD, WU, WD Partitions)**
  * **Function**: Computes an agreement (co-assignment) matrix across an ensemble of module partitions [20].
  * **Parameters**: Partition matrix (nodes \\(\times\\) runs) [20].
  * **Return Values**: Agreement matrix \\(D\\) (entry \\(D_{ij}\\) = proportion of partitions in which nodes \\(i\\) and \\(j\\) were placed in the same module) [20].
  * **Use Case**: Quantifying partition consistency and preparing input for consensus clustering [20].
* **`consensus_und.m` (BU, BD, WU, WD Partitions)**
  * **Function**: Generates a single consensus partition from an agreement matrix [18, 20].
  * **Parameters**: Agreement matrix \\(D\\), threshold parameter, sweep repetitions [20].
  * **Return Values**: Consensus module vector \\(Consensus\\) and consensus modularity [20].
  * **Use Case**: Resolving modularity degeneracy (multiple high-modularity partitions) to obtain a reproducible module assignment [20].

---

### 4. Assortativity, Rich-Club, and Core-Periphery Structure

* **`assortativity_bin.m` (BU, BD)** & **`assortativity_wei.m` (WU, WD)**
  * **Function**: Calculates the assortativity coefficient (correlation coefficient between degrees/strengths of nodes on opposite ends of a link) [21].
  * **Parameters**: Adjacency/weight matrix [21].
  * **Return Values**: Scalar assortativity coefficient \\(r\\) [21].
  * **Use Case**: Testing whether high-degree hubs preferentially link to other hubs (assortative) or non-hubs (disassortative) [21].
* **`local_assortativity_wu_sign.m` (WU Signed)**
  * **Function**: Calculates local (nodal) assortativity for signed weighted networks [9, 21].
  * **Parameters**: Signed weight matrix \\(W\\) [21].
  * **Return Values**: Vector of local assortativity scores for each node [21].
  * **Use Case**: Identifying specific brain regions driving overall network assortativity or disassortativity [9, 21].
* **`rich_club_bu.m` (BU)**, **`rich_club_bd.m` (BD)**, **`rich_club_wu.m` (WU)**, **`rich_club_wd.m` (WD)**
  * **Function**: Calculates the rich-club coefficient at degree level \\(k\\) (fraction of edges connecting nodes of degree \\(\ge k\\) relative to the maximum possible edges between them) [21, 22].
  * **Parameters**: Adjacency/weight matrix, maximum degree \\(k_{max}\\) [22].
  * **Return Values**: Vector of rich-club coefficients \\(\Phi(k)\\) [22].
  * **Use Case**: Detecting a central "rich-club" core of densely interconnected hubs [21, 22].
* **`core_periphery_dir.m` (BU, BD, WU, WD)**
  * **Function**: Partitions the network into core and periphery node groups to maximize core-core connectivity and minimize periphery-periphery connectivity [9, 22].
  * **Parameters**: Adjacency/weight matrix [22].
  * **Return Values**: Binary core-periphery vector \\(C\\) (\\(1\\) = core, \\(0\\) = periphery) and coreness statistic \\(q\\) [9, 22].
  * **Use Case**: Dissecting hierarchical core-periphery architecture in brain networks [9, 22].
* **`kcore_bu.m` (BU)** & **`kcore_bd.m` (BD)**
  * **Function**: Extracts the \\(k\\)-core subnetwork (largest subnetwork containing nodes of degree \\(\ge k\\), derived by recursive peeling) [23].
  * **Parameters**: Binary matrix \\(A\\), degree threshold \\(k\\) [23].
  * **Return Values**: \\(k\\)-core adjacency matrix and node coreness indices [23].
  * **Use Case**: Stripping peripheral nodes to isolate dense structural cores [23].
* **`score_wu.m` (WU)**
  * **Function**: Extracts the \\(s\\)-core subnetwork (largest subnetwork containing nodes of strength \\(\ge s\\)) [24].
  * **Parameters**: Weighted matrix \\(W\\), strength threshold \\(s\\) [24].
  * **Return Values**: \\(s\\)-core matrix and node strength indices [24].
  * **Use Case**: Extracting weighted structural cores based on connection strength thresholding [24].

---

### 5. Paths, Distances, Efficiency, and Navigation

* **`findpaths.m` (BU, BD)** & **`findwalks.m` (BU, BD)**
  * **Function**: Identifies paths (node sequences without node repetition) and walks (node sequences allowing node repetition) up to path length \\(k\\) [24].
  * **Parameters**: Binary matrix \\(A\\), max path length \\(k\\) [24].
  * **Return Values**: Path matrix \\(P_k\\) or walk matrix \\(W_k\\) [24].
  * **Use Case**: Analyzing structural communication routes and multi-step signaling [24].
* **`distance_bin.m` (BU, BD)**
  * **Function**: Computes the shortest path distance matrix using an algebraic algorithm [25].
  * **Parameters**: Binary matrix \\(A\\) [25].
  * **Return Values**: Shortest path distance matrix \\(D\\) [25].
  * **Use Case**: Topological distance and path length calculation in unweighted networks [25].
* **`reachdist.m` (BU, BD)**
  * **Function**: Computes reachability and distance matrices using matrix powers (returns nonzeros on main diagonal) [25].
  * **Parameters**: Binary matrix \\(A\\) [25].
  * **Return Values**: Reachability matrix \\(R\\) and distance matrix \\(D\\) [25].
  * **Use Case**: Evaluating topological reachability between all brain regions [25].
* **`breadthdist.m` (BU, BD)**
  * **Function**: Computes reachability and distance matrices via breadth-first search (requires auxiliary `breadth.m`) [25]. Slower but less memory-intensive than `distance_bin.m` [25].
  * **Parameters**: Binary matrix \\(A\\) [25].
  * **Return Values**: Distance matrix \\(D\\) [25].
  * **Use Case**: Memory-efficient path distance calculation on large sparse connectomes [25].
* **`retrieve_shortest_path.m` (BU, BD, WU, WD)**
  * **Function**: Retrieves the exact node sequence comprising the shortest path between a source node and a target node [25].
  * **Parameters**: Source node \\(s\\), target node \\(t\\), distance/transform matrix [25].
  * **Return Values**: Ordered vector of node indices along the path [25].
  * **Use Case**: Explicitly tracing communication pathways in structural connectomes [25].
* **`distance_wei.m` (WU, WD)**
  * **Function**: Computes shortest path distance matrix using Dijkstra's algorithm [26]. Requires a mapping from weight to distance (e.g., weight inversion) [26].
  * **Parameters**: Distance/length matrix \\(L\\) [26].
  * **Return Values**: Shortest weighted path distance matrix \\(D\\) [26].
  * **Use Case**: Calculating weighted path lengths and communication latencies [26].
* **`distance_wei_floyd.m` (BU, BD, WU, WD)**
  * **Function**: All-pairs shortest path distance matrix using the Floyd-Warshall algorithm [8, 26]. Accepts either distance-mapped inputs or native weight matrices with a specified transform [8, 26].
  * **Parameters**: Weight or distance matrix, weight transform specifier [8, 26].
  * **Return Values**: Distance matrix $D$ and number-of-edges matrix $B$ [26].
  * **Use Case**: Robust all-pairs shortest path calculation on dense or weighted graphs [8, 26].
* **`charpath.m` (BU, BD, WU, WD)**
  * **Function**: Computes characteristic path length $\lambda$, global efficiency $E_{glob}$, node eccentricity, network radius, and network diameter [15, 18, 26].
  * **Parameters**: Distance matrix $D$, path exclusion options [15, 18].
  * **Return Values**: Characteristic path length $\lambda$, efficiency $E$, eccentricity vector, radius $r$, and diameter $d$ [15].
  * **Use Case**: Global summary metrics of network integration and spatial compactness [15, 26].
* **`cycprob.m` (BU, BD)**
  * **Function**: Calculates cycle probability for path length $d$ (fraction of paths of length $d-1$ extending to cycles of length $d$) [15].
  * **Parameters**: Binary matrix $A$, length $d$ [15].
  * **Return Values**: Cycle probability statistic [15].
  * **Use Case**: Quantifying feedback loop propensity in directed/undirected graphs [15].
* **`rout_efficiency.m` (BU, BD, WU, WD)**
  * **Function**: Computes routing efficiency across network nodes [16].
  * **Parameters**: Connectivity matrix [16].
  * **Return Values**: Routing efficiency matrix/vector [16].
  * **Use Case**: Quantifying information routing efficiency along dedicated communication pathways [16].
* **`mean_first_passage_time.m` (BU, BD, WU, WD)**
  * **Function**: Computes the mean first passage time (expected number of steps a random walker takes to reach node $j$ from node $i$) [8, 16].
  * **Parameters**: Transition probability matrix or weight matrix [16].
  * **Return Values**: Mean first passage time matrix $MFPT$ [16].
  * **Use Case**: Modeling stochastic diffusion and random-walk dynamics in connectomes [8, 16].
* **`diffusion_efficiency.m` (BU, BD, WU, WD)**
  * **Function**: Calculates diffusion efficiency (the inverse of the mean first passage time) globally and pair-wise [8, 16, 27].
  * **Parameters**: Weight or adjacency matrix [16, 27].
  * **Return Values**: Global diffusion efficiency $E_{diff}$ and pairwise diffusion efficiency matrix [16, 27].
  * **Use Case**: Evaluating communication efficiency under unbiased random-walk diffusion processes [8, 16, 27].
* **`resource_efficiency_bin.m` (BU)**
  * **Function**: Computes resource efficiency (inversely proportional to the amount of resources/particles required to ensure at least one message arrives in exactly $SPL$ steps) [27].
  * **Parameters**: Binary matrix $A$ [27].
  * **Return Values**: Resource efficiency metric [27].
  * **Use Case**: Modeling message spreading efficiency under particle capacity constraints [27].
* **`path_transitivity.m` (BU)**
  * **Function**: Computes path transitivity (the density of local detours/triangles available along shortest paths between node pairs) [8, 27, 28].
  * **Parameters**: Binary matrix $A$ [28].
  * **Return Values**: Path transitivity matrix [28].
  * **Use Case**: Measuring structural fault tolerance and alternative routing routes along shortest paths [8, 27, 28].
* **`search_information.m` (BU)**
  * **Function**: Calculates search information (amount of information in bits required for a random walker to follow the shortest path between two nodes) [28].
  * **Parameters**: Binary matrix $A$ [28].
  * **Return Values**: Search information matrix $S$ [28].
  * **Use Case**: Quantifying the accessibility and navigation difficulty of shortest paths [28].
* **`navigation_wu.m` (WU)**
  * **Function**: Simulates decentralized greedy navigation driven by physical geometric closeness between target nodes [28].
  * **Parameters**: Weight matrix $W$, physical coordinate matrix [28].
  * **Return Values**: Navigation success rate and navigation path lengths [28].
  * **Use Case**: Assessing greedy physical spatial routing efficiency in embedded brain networks [28].

---

### 6. Centrality Measures

* **`betweenness_bin.m` (BU, BD)** & **`betweenness_wei.m` (WU, WD)**
  * **Function**: Computes node betweenness centrality (fraction of all shortest paths passing through a given node) [29]. `betweenness_bin` uses Kintali's algorithm; `betweenness_wei` uses Brandes's algorithm [29].
  * **Parameters**: Adjacency/distance matrix [29].
  * **Return Values**: Node betweenness centrality vector $BC$ [29].
  * **Use Case**: Identifying crucial bottleneck regions and communication hubs [29].
* **`edge_betweenness_bin.m` (BU, BD)** & **`edge_betweenness_wei.m` (WU, WD)**
  * **Function**: Computes edge betweenness centrality (fraction of shortest paths passing through a specific link) [29, 30].
  * **Parameters**: Adjacency/distance matrix [30].
  * **Return Values**: Matrix $EBC$ of edge betweenness centrality values [30].
  * **Use Case**: Identifying critical connector tracts whose disruption disconnects subnetworks [29, 30].
* **`module_degree_zscore.m` (BU, BD, WU, WD)**
  * **Function**: Calculates within-module degree z-score ($z_i$), measuring how well connected a node is to other nodes in its own module relative to the module average [30].
  * **Parameters**: Adjacency/weight matrix, community affiliation vector $Ci$ [30].
  * **Return Values**: Vector $Z$ of within-module z-scores [30].
  * **Use Case**: Categorizing node roles into intra-modular hubs vs. non-hubs [30].
* **`participation_coef.m` (BU, BD, WU, WD)**
  * **Function**: Calculates participation coefficient ($P_i$), measuring the diversity of inter-modular connections of individual nodes [30, 31].
  * **Parameters**: Adjacency/weight matrix, community affiliation vector $Ci$ [30, 31].
  * **Return Values**: Vector $P$ of participation coefficients [31].
  * **Use Case**: Classifying connector hubs ($P_i \to 1$) vs. provincial hubs ($P_i \approx 0$) [30, 31].
* **`participation_coef_sign.m`**, **`gateway_coef_sign.m`**, **`diversity_coef_sign.m` (WU Signed)**
  * **Function**:
    * `participation_coef_sign.m`: Participation coefficient generalized for signed networks [31].
    * `gateway_coef_sign.m`: Gateway coefficient (variant of participation coefficient weighted by connection importance) for signed networks [9, 31].
    * `diversity_coef_sign.m`: Diversity coefficient based on Shannon entropy for signed networks [31].
  * **Parameters**: Signed weight matrix $W$, community affiliation vector $Ci$ [31].
  * **Return Values**: Positive and negative nodal coefficient vectors [31].
  * **Use Case**: Nodal role classification in signed functional connectomes [9, 31].
* **`eigenvector_centrality_und.m` (BU, WU)**
  * **Function**: Computes eigenvector centrality (self-referential measure: nodes have high centrality if connected to other highly central nodes; uses leading eigenvector) [12, 31].
  * **Parameters**: Adjacency/weight matrix $A$ or $W$ [31].
  * **Return Values**: Vector $V$ of eigenvector centrality scores [31].
  * **Use Case**: Identifying globally dominant node clusters [31].
* **`pagerank_centrality.m` (BU, WU)**
  * **Function**: Calculates PageRank centrality (variant of eigenvector centrality with a damping factor) [32].
  * **Parameters**: Adjacency/weight matrix, damping factor $d$ [32].
  * **Return Values**: Vector $R$ of PageRank centrality scores [32].
  * **Use Case**: Ranking node influence in complex directed or weighted graphs [32].
* **`subgraph_centrality.m` (BU)**
  * **Function**: Calculates subgraph centrality (weighted sum of closed walks of different lengths starting and ending at a given node) [32].
  * **Parameters**: Binary matrix $A$ [32].
  * **Return Values**: Subgraph centrality vector $C_{sub}$ [32].
  * **Use Case**: Characterizing participation in closed subgraphs [32].
* **`kcoreness_centrality_bu.m` (BU)** & **`kcoreness_centrality_bd.m` (BD)**
  * **Function**: Computes $k$-coreness centrality (the coreness integer $k$ indicating the highest $k$-core level to which a node belongs) [32, 33].
  * **Parameters**: Binary matrix $A$ [32, 33].
  * **Return Values**: Vector $K$ of node coreness values [32, 33].
  * **Use Case**: Hierarchical core scoring in structural networks [32, 33].
* **`flow_coef_bd.m` (BU, BD)**
  * **Function**: Calculates flow coefficient (computes centrality based on local neighborhoods; inversely related to clustering coefficient) [33].
  * **Parameters**: Adjacency matrix $A$ [33].
  * **Return Values**: Flow coefficient vector and total flow [33].
  * **Use Case**: Measuring local flow and message forwarding capacity [33].
* **`erange.m` (BD)**
  * **Function**: Identifies shortcuts (central edges whose removal significantly increases characteristic path length) [33].
  * **Parameters**: Binary directed matrix $A$ [33].
  * **Return Values**: Edge range matrix [33].
  * **Use Case**: Locating central shortcut edges [33].

---

### 7. Motifs and Self-Similarity

* **`motif3struct_bin.m`**, **`motif4struct_bin.m` (BD)** & **`motif3struct_wei.m`**, **`motif4struct_wei.m` (WD)**
  * **Function**: Computes structural motif frequency, intensity, and coherence for 3-node and 4-node directed motifs (requires library `motif34lib.mat` generated by `make_motif34lib.m`) [34].
  * **Parameters**: Adjacency/weight matrix, `motif34lib.mat` library [34].
  * **Return Values**: Nodal and total motif frequency, intensity, and coherence vectors/matrices [34].
  * **Use Case**: Uncovering basic local connectivity building blocks in directed anatomical circuits [34].
* **`motif3funct_bin.m`**, **`motif4funct_bin.m` (BD)** & **`motif3funct_wei.m`**, **`motif4funct_wei.m` (WD)**
  * **Function**: Computes functional motif frequency, intensity, and coherence (subsets of connection patterns embedded within structural motifs) [35].
  * **Parameters**: Adjacency/weight matrix, `motif34lib.mat` library [35].
  * **Return Values**: Nodal and total functional motif matrices [35].
  * **Use Case**: Dissecting functional interaction patterns constrained by structural motifs [35, 36].
* **`find_motif34.m` (BD)**
  * **Function**: Motif legend helper function. Returns all motif isomorphs for a given motif ID/size or returns motif ID for a given $3 \times 3$ or $4 \times 4$ matrix [35, 36].
  * **Parameters**: Motif size, motif ID, or connectivity matrix [35, 36].
  * **Return Values**: Motif connection matrices or motif ID [35, 36].
  * **Use Case**: Structural lookup and visual mapping of 3-node and 4-node motif topologies [35, 36].
* **`quasi_idempotence.m` (WU)**
  * **Function**: Computes quasi-idempotence (correlation between a matrix and its squared versions to quantify how close it is to being idempotent) [35, 37].
  * **Parameters**: Weighted matrix $W$ [37].
  * **Return Values**: Quasi-idempotence statistic [37].
  * **Use Case**: Evaluating whether edge strengths are primarily determined by nodal strengths and triangular patterns [35, 37].

---

### 8. Network Comparison and Matrix Utilities

* **`partition_distance.m` (BU, BD, WU, WD Partitions)**
  * **Function**: Quantifies distance/similarity between two community structure partitions using Variation of Information ($VI$) and Mutual Information ($MI$) [10, 38].
  * **Parameters**: Community affiliation vectors $M_1$ and $M_2$ [38].
  * **Return Values**: Variation of Information ($VI$) and Normalized Mutual Information ($NMI$) [38].
  * **Use Case**: Comparing community partitions across subjects, sessions, or algorithms [10, 38].
* **`threshold_absolute.m`** & **`threshold_proportional.m` (BU, BD, WU, WD)**
  * **Function**: Thresholds connectivity matrices by absolute weight cutoffs or by retaining a specified proportion of the strongest weights [39].
  * **Parameters**: Matrix $W$, threshold value or proportion $p$ [39].
  * **Return Values**: Thresholded connectivity matrix $W_{thresh}$ [39].
  * **Use Case**: Network sparsification and weight filtering prior to graph theoretical analysis [39].
* **`weight_conversion.m`**
  * **Function**: Utility script for weight conversions, normalizations, and fixing weight anomalies (includes `autofix` flag) [10, 17].
  * **Parameters**: Weight matrix, transform specifier (e.g., `'binarize'`, `'lengths'`, `'autofix'`) [10, 17].
  * **Return Values**: Transformed weight matrix [10, 17].
  * **Use Case**: Preprocessing connectome matrices before graph calculations [10, 17].
* **`null_model_und_sign.m`**, **`null_model_dir_sign.m`**, **`randmio_und_signed.m`**, **`randmio_dir_signed.m`**
  * **Function**: Generates randomized reference null model networks preserving signed in/out-degree distributions and positive/negative weights [9, 12].
  * **Parameters**: Signed connectivity matrix, iteration count [9, 12].
  * **Return Values**: Randomized null model adjacency matrix $W_{rand}$ [9, 12].
  * **Use Case**: Non-parametric statistical significance testing against random graph null models [9, 12].
* **`latmio_und.m`**, **`latmio_und_connected.m`**, **`latmio_dir.m`**, **`latmio_dir_connected.m` (BU, BD, WU, WD)**
  * **Function**: Generates latticized benchmark networks preserving degree distributions (and connectivity in `connected` variants) [40].
  * **Parameters**: Connectivity matrix, iteration count [40].
  * **Return Values**: Latticized matrix $W_{lat}$ [40].
  * **Use Case**: Benchmark lattice null models for evaluating physical spatial embedding [40].
* **`makerandCIJ_und.m`**, **`makerandCIJ_dir.m`**, **`makerandCIJdegreesfixed.m`**, **`makelatticeCIJ.m`**, **`makeringlatticeCIJ.m`**, **`makeevenCIJ.m`**, **`makefractalCIJ.m`**, **`maketoeplitzCIJ.m`**
  * **Function**: Synthetic network generators creating random, fixed-degree, non-ring lattice, ring lattice, modular small-world, hierarchical modular fractal, and Toeplitz distance-decay matrices [41-43].
  * **Parameters**: Node count $N$, link count $K$, module counts, or distance decay exponents [41-43].
  * **Return Values**: Synthetic adjacency matrix $CIJ$ [41-43].
  * **Use Case**: Simulating canonical graph topologies for theoretical graph analysis [41-43].
* **`backbone_wu.m` (BU, WU)**
  * **Function**: Extracts the structural backbone of a weighted matrix [44].
  * **Parameters**: Weighted matrix $W$, backbone threshold/degree constraints [44].
  * **Return Values**: Backbone graph matrix [44].
  * **Use Case**: Retaining primary topological pathways in dense weighted connectomes [44].
* **`align_matrices.m`**, **`reorder_matrix.m`**, **`reorder_mod.m`**, **`reorderMAT.m` (BU, BD, WU, WD)**
  * **Function**: Reorders matrix nodes using simulated annealing or modular structure to align matrices or maximize edge density along the main diagonal [44, 45].
  * **Parameters**: Connectivity matrix, target alignment matrix or module vector [44, 45].
  * **Return Values**: Reordered matrix and node permutation vector [44, 45].
  * **Use Case**: Matrix visualization, modular block-diagonal inspection, and cross-subject matrix alignment [44, 45].
* **`demo_efficiency_measures.m`**
  * **Function**: Demonstration script for computing efficiency functions on synthetic datasets (requires `demo_efficiency_measures_data.mat`) [13].
  * **Use Case**: Benchmark testing and validation of BCT efficiency calculations [13].

---
