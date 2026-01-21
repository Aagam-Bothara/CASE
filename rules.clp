;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; CASE Optimizer – Advanced Logic Engine
;; Features: Constraint Analysis, Architectural Pattern Matching, Physical Limits
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

;; ----------------------------
;; 1. DATA MODEL (TEMPLATES)
;; ----------------------------

(deftemplate workload
  (slot workload_type (type SYMBOL))       ; web|api|batch|stream|analytics
  (slot traffic_rps   (type INTEGER) (default 0))
  (slot variability   (type SYMBOL)  (default steady)) ; steady|spiky
  (slot latency       (type INTEGER) (default 150))
  (slot statefulness  (type SYMBOL)  (default stateless))
  (slot persistence_model (type SYMBOL) (default none))
  (slot data_size_gb  (type FLOAT) (default 0.0))
  (slot compliance    (type SYMBOL)  (default none))
  (slot sla_tier      (type SYMBOL)  (default standard))
  (slot multi_region_needed (type SYMBOL) (default no))
  (slot vendor_preference (type SYMBOL) (default none))
  (slot region (type SYMBOL) (default us-east-1))

  ;; Granular Quantitative Inputs
  (slot avg_exec_ms (type FLOAT) (default 100.0))
  (slot mem_gb (type FLOAT) (default 0.5))
  (slot cpu_vcpu (type FLOAT) (default 0.25))
  (slot read_qps (type FLOAT) (default 0.0))
  (slot write_qps (type FLOAT) (default 0.0))
  (slot storage_gb_hot (type FLOAT) (default 0.0))
  (slot storage_gb_cold (type FLOAT) (default 0.0))
  (slot egress_gb_month (type FLOAT) (default 0.0))
)

;; Intermediate facts for reasoning
(deftemplate constraint (slot type) (slot reason))  ; e.g., type=high-memory
(deftemplate pattern (slot type))                   ; e.g., type=event-driven
(deftemplate compute_choice (slot value))           ; serverless-fn, serverless-cont, k8s, vms
(deftemplate storage_choice (slot value))           ; sql, nosql, cache, object...

(deftemplate candidate
  (slot vendor)
  (slot service)
  (slot role)
  (slot notes)
)

(deftemplate candidate_eval
  (slot vendor)
  (slot compute_service)
  (slot storage_service)
  (slot feasible (type SYMBOL))
  (slot p95_ms (type FLOAT))
  (slot availability (type FLOAT))
  (slot monthly_cost (type FLOAT))
  (slot reason)
)

(deftemplate final_recommendation
  (slot vendor)
  (slot compute_service)
  (slot storage_service)
  (slot reason)
)

(deftemplate why (slot msg))

;; ----------------------------
;; 2. CONSTRAINT ANALYSIS PHASE
;; Detects physical limits and workload characteristics
;; ----------------------------

;; Detect High Memory Requirement (>10GB is tricky for standard Lambda/Functions)
(defrule detect-high-memory
  (workload (mem_gb ?m&:(> ?m 10.0)))
  =>
  (assert (constraint (type high-memory) (reason "RAM > 10GB exceeds FaaS limits"))))

;; Detect Long Running Processes (>15 mins is fatal for Lambda)
(defrule detect-long-running
  (workload (avg_exec_ms ?t&:(> ?t 900000))) ;; 15 mins * 60 * 1000
  =>
  (assert (constraint (type long-running) (reason "Execution > 15m exceeds FaaS limits"))))

;; Detect Strict Latency (< 50ms implies avoiding Cold Starts)
(defrule detect-strict-latency
  (workload (latency ?l&:(<= ?l 50)))
  =>
  (assert (constraint (type strict-latency) (reason "Target < 50ms requires warm compute"))))

;; Detect High Throughput (RPS > 1000 usually cheaper on Containers/VMs)
(defrule detect-high-throughput
  (workload (traffic_rps ?r&:(> ?r 1000)) (variability steady))
  =>
  (assert (constraint (type high-throughput) (reason "High steady RPS favors provisioned capacity"))))

;; ----------------------------
;; 3. ARCHITECTURAL PATTERN SELECTION
;; Decides the "Shape" of the solution
;; ----------------------------

;; Pattern: True Serverless (Functions)
;; Use if: Web/API, Stateless, Spiky traffic, fits memory/time constraints
(defrule pattern-serverless-functions
  (workload (workload_type ?t&:(or (eq ?t web) (eq ?t api))) (statefulness stateless) (variability spiky))
  (not (constraint (type high-memory)))
  (not (constraint (type long-running)))
  (not (constraint (type strict-latency)))
  =>
  (assert (compute_choice (value serverless-fn)))
  (assert (why (msg "Spiky + Stateless + Small footprint → Serverless Functions"))))

;; Pattern: Serverless Containers (The sweet spot)
;; Use if: Stateless, but maybe long running or strict latency (via min instances)
(defrule pattern-serverless-containers
  (workload (workload_type ?t&:(or (eq ?t web) (eq ?t api) (eq ?t batch))) (statefulness stateless))
  (not (constraint (type high-memory))) ;; Some CaaS have limits too, but higher (32GB+)
  =>
  (assert (compute_choice (value serverless-cont)))
  (assert (why (msg "Stateless workload → Serverless Containers (Flexible)"))))

;; Pattern: Kubernetes / Orchestration
;; Use if: High throughput steady, or complex microservices (implied), or VERY high memory
(defrule pattern-k8s
  (or (constraint (type high-throughput))
      (constraint (type high-memory)))
  (workload (statefulness stateless))
  =>
  (assert (compute_choice (value k8s)))
  (assert (why (msg "High Load or High RAM → Kubernetes/Managed Clusters"))))

;; Pattern: Virtual Machines (Legacy/Stateful)
;; Use if: Stateful, or Long Running Batch with huge RAM
(defrule pattern-vms
  (or (workload (statefulness stateful))
      (and (workload (workload_type batch)) (constraint (type long-running))))
  =>
  (assert (compute_choice (value vms)))
  (assert (why (msg "Stateful or Long-Running Batch → Virtual Machines"))))

;; ----------------------------
;; 4. STORAGE SELECTION
;; ----------------------------

(defrule storage-direct
  (workload (persistence_model ?m&:(neq ?m none)))
  =>
  (assert (storage_choice (value ?m))))

;; Intelligent Caching: Add Redis if Read Heavy
(defrule storage-smart-cache
  (workload (read_qps ?r) (write_qps ?w))
  (test (> ?r 500))         ;; High reads
  (test (> ?r (* ?w 5)))    ;; Read/Write ratio > 5:1
  =>
  (assert (storage_choice (value cache)))
  (assert (why (msg "High Read/Write ratio → Suggest Caching Layer"))))

;; Intelligent Archival: Add Object Storage if Cold Data exists
(defrule storage-smart-archive
  (workload (storage_gb_cold ?c&:(> ?c 10.0)))
  =>
  (assert (storage_choice (value object)))
  (assert (why (msg "Cold data present → Suggest Object Storage for Archival"))))

;; ----------------------------
;; 5. SERVICE MAPPING & GUARDRAILS
;; Expands choices to candidates, but respects constraints
;; ----------------------------

;; AWS Mappings
(defrule map-aws-fn
  (compute_choice (value serverless-fn))
  (not (constraint (type high-memory))) ;; Double check constraint
  => (assert (candidate (vendor aws) (service lambda) (role compute) (notes "AWS Lambda"))))

(defrule map-aws-cont
  (compute_choice (value serverless-cont))
  => (assert (candidate (vendor aws) (service fargate) (role compute) (notes "AWS Fargate"))))

(defrule map-aws-k8s
  (compute_choice (value k8s))
  => (assert (candidate (vendor aws) (service eks) (role compute) (notes "Amazon EKS"))))

(defrule map-aws-vm
  (compute_choice (value vms))
  => (assert (candidate (vendor aws) (service ec2) (role compute) (notes "Amazon EC2"))))

;; Azure Mappings
(defrule map-azure-fn
  (compute_choice (value serverless-fn))
  (not (constraint (type high-memory)))
  => (assert (candidate (vendor azure) (service functions) (role compute) (notes "Azure Functions"))))

(defrule map-azure-cont
  (compute_choice (value serverless-cont))
  => (assert (candidate (vendor azure) (service container-apps) (role compute) (notes "Azure Container Apps"))))

(defrule map-azure-k8s
  (compute_choice (value k8s))
  => (assert (candidate (vendor azure) (service aks) (role compute) (notes "Azure AKS"))))

(defrule map-azure-vm
  (compute_choice (value vms))
  => (assert (candidate (vendor azure) (service vm) (role compute) (notes "Azure VMs"))))

;; GCP Mappings
(defrule map-gcp-fn
  (compute_choice (value serverless-fn))
  (not (constraint (type high-memory)))
  => (assert (candidate (vendor gcp) (service cloud-functions) (role compute) (notes "Google Cloud Functions"))))

(defrule map-gcp-cont
  (compute_choice (value serverless-cont))
  => (assert (candidate (vendor gcp) (service cloud-run) (role compute) (notes "Google Cloud Run"))))

(defrule map-gcp-k8s
  (compute_choice (value k8s))
  => (assert (candidate (vendor gcp) (service gke) (role compute) (notes "Google GKE"))))

(defrule map-gcp-vm
  (compute_choice (value vms))
  => (assert (candidate (vendor gcp) (service gce) (role compute) (notes "Google Compute Engine"))))

;; Storage Mapping (Simplified for brevity, expands to all vendors)
(defrule map-storage-all
  (storage_choice (value ?type))
  =>
  (if (eq ?type sql) then
      (assert (candidate (vendor aws) (service rds-aurora) (role storage) (notes "Aurora")))
      (assert (candidate (vendor azure) (service azure-sql) (role storage) (notes "SQL Database")))
      (assert (candidate (vendor gcp) (service cloud-sql) (role storage) (notes "Cloud SQL"))))
  (if (eq ?type nosql) then
      (assert (candidate (vendor aws) (service dynamodb) (role storage) (notes "DynamoDB")))
      (assert (candidate (vendor azure) (service cosmosdb) (role storage) (notes "CosmosDB")))
      (assert (candidate (vendor gcp) (service bigtable) (role storage) (notes "BigTable"))))
  (if (eq ?type object) then
      (assert (candidate (vendor aws) (service s3) (role storage) (notes "S3")))
      (assert (candidate (vendor azure) (service blob) (role storage) (notes "Blob Storage")))
      (assert (candidate (vendor gcp) (service gcs) (role storage) (notes "GCS"))))
  (if (eq ?type cache) then
      (assert (candidate (vendor aws) (service elasticache-redis) (role storage) (notes "ElastiCache")))
      (assert (candidate (vendor azure) (service azure-redis) (role storage) (notes "Azure Redis")))
      (assert (candidate (vendor gcp) (service memorystore-redis) (role storage) (notes "Memorystore"))))
  (if (eq ?type none) then
      (assert (candidate (vendor aws) (service none) (role storage) (notes "None")))
      (assert (candidate (vendor azure) (service none) (role storage) (notes "None")))
      (assert (candidate (vendor gcp) (service none) (role storage) (notes "None"))))
)


;; ----------------------------
;; 6. FINAL RECOMMENDATION ENGINE
;; Picks the "Winner" from the Evaluated Candidates
;; ----------------------------

(deffunction score-eval (?e ?pref ?maxCost ?maxP95)
  "Calculate normalized scores for an evaluation (0-100 scale)"
  (bind ?cost (fact-slot-value ?e monthly_cost))
  (bind ?p95  (fact-slot-value ?e p95_ms))
  (bind ?vend (fact-slot-value ?e vendor))

  ;; Cost score: inverse normalized (lower is better, scaled 0-100)
  (bind ?costScore (if (> ?maxCost 0)
                      then (* 100 (- 1 (/ ?cost ?maxCost)))
                      else 100))

  ;; Performance score: inverse normalized (lower latency is better, scaled 0-100)
  (bind ?perfScore (if (> ?maxP95 0)
                      then (* 100 (- 1 (/ ?p95 ?maxP95)))
                      else 100))

  ;; Preference score: binary 100 or 0
  (bind ?prefScore (if (and (neq ?pref none) (eq ?vend ?pref)) then 100 else 0))

  ;; Composite score: weighted average (Cost: 50%, Perf: 30%, Pref: 20%)
  (bind ?composite (+ (* ?costScore 0.5) (* ?perfScore 0.3) (* ?prefScore 0.2)))

  (create$ ?composite ?costScore ?perfScore ?prefScore))

(deffunction top3-feasible-evals-with-pref (?pref)
  "Returns a multifield of top 3 feasible evaluations based on composite scoring"
  (bind ?allFeasible (create$))
  (bind ?maxCost 0.0)
  (bind ?maxP95 0.0)

  ;; First pass: find max values for normalization
  (do-for-all-facts ((?e candidate_eval)) (eq (fact-slot-value ?e feasible) yes)
    (bind ?cost (fact-slot-value ?e monthly_cost))
    (bind ?p95  (fact-slot-value ?e p95_ms))
    (if (> ?cost ?maxCost) then (bind ?maxCost ?cost))
    (if (> ?p95 ?maxP95) then (bind ?maxP95 ?p95)))

  ;; Second pass: collect all feasible with scores
  (do-for-all-facts ((?e candidate_eval)) (eq (fact-slot-value ?e feasible) yes)
    (bind ?scores (score-eval ?e ?pref ?maxCost ?maxP95))
    (bind ?composite (nth$ 1 ?scores))
    (bind ?allFeasible (create$ ?allFeasible ?e ?composite)))

  ;; Sort by composite score (descending) and return top 3 facts
  (bind ?top3 (create$))
  (bind ?count 0)

  (while (and (< ?count 3) (> (length$ ?allFeasible) 0))
    (bind ?bestIdx 1)
    (bind ?bestScore (nth$ 2 ?allFeasible))

    ;; Find best remaining
    (bind ?i 1)
    (while (<= ?i (length$ ?allFeasible))
      (if (= (mod ?i 2) 0) then
        (if (> (nth$ ?i ?allFeasible) ?bestScore) then
          (bind ?bestScore (nth$ ?i ?allFeasible))
          (bind ?bestIdx (- ?i 1))))
      (bind ?i (+ ?i 1)))

    ;; Add to top3
    (bind ?top3 (create$ ?top3 (nth$ ?bestIdx ?allFeasible)))

    ;; Remove from allFeasible
    (bind ?newList (create$))
    (bind ?i 1)
    (while (<= ?i (length$ ?allFeasible))
      (if (neq ?i ?bestIdx) then
        (bind ?newList (create$ ?newList (nth$ ?i ?allFeasible) (nth$ (+ ?i 1) ?allFeasible))))
      (bind ?i (+ ?i 2)))
    (bind ?allFeasible ?newList)
    (bind ?count (+ ?count 1)))

  ?top3)

(deffunction best-feasible-eval-with-pref (?pref)
  "Returns single best evaluation (for backwards compatibility)"
  (bind ?top3 (top3-feasible-evals-with-pref ?pref))
  (if (> (length$ ?top3) 0)
    then (nth$ 1 ?top3)
    else FALSE))

(defrule choose-optimal
  (declare (salience 100))
  (not (final_recommendation (vendor ?)))
  (candidate_eval (feasible yes))
  (workload (vendor_preference ?vp))
  =>
  (bind ?best (best-feasible-eval-with-pref ?vp))
  (if ?best then
    (assert (final_recommendation
      (vendor (fact-slot-value ?best vendor))
      (compute_service (fact-slot-value ?best compute_service))
      (storage_service (fact-slot-value ?best storage_service))
      (reason (str-cat "Optimal choice. Cost: $" (fact-slot-value ?best monthly_cost) 
                       " | Latency: " (fact-slot-value ?best p95_ms) "ms"))))))

(defrule no-solution
  (declare (salience 90))
  (not (final_recommendation (vendor ?)))
  (not (candidate_eval (feasible yes)))
  =>
  (assert (final_recommendation
      (vendor "none")
      (compute_service "none")
      (storage_service "none")
      (reason "No feasible options found given the constraints (Performance/Budget)."))))