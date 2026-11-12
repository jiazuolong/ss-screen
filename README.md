# ss-screen

Screen **materials pairs that form solid-solutions (alloys) with tunable band gaps**.

`ss-screen` packages the screening pipeline developed in the `HC/` research
workspace into a tested, documented command-line tool. It identifies
isostructural prototype groups in large materials databases (Materials Project,
WBM) where one endmember is near-zero-gap and another is a small direct-gap
semiconductor — candidates for gap tuning via alloying.

## 10.0 μm GUI 演示

[下载演示工程与数据库](https://github.com/jiazuolong/ss-screen/releases/tag/demo-10um-20261112) · [安装与逐步验收说明](docs/reproducibility/demo_v1_delivery.md)

## Scientific core

Materials are grouped by a **robocrystallographer local-environment fingerprint**
in which the variable (alloyed) element is relabeled to a placeholder `X`, so
chemically distinct but structurally identical prototypes collapse together.
A group is *promising* when it contains both a near-zero-gap member and a
small direct-gap member.

## Install

The core package supports Python 3.10+. Use Python 3.11 or newer for the
`condense` extra: its required `matminer>=0.10.1` dependency requires Python 3.11+.

```bash
pip install -e .
# CLI plus structure descriptions, MP access and development tools:
python -m pip install -e ".[condense,mp]" --group dev
# To query Materials Project directly with --backend api:
pip install -e ".[mp]"
# To use a local Materials Project SQLite snapshot (separate package):
python -m pip install /path/to/mp-offline
# To load WBM extxyz files:
pip install -e ".[wbm]"
# To also run the robocrys condensation step:
pip install -e ".[condense]"
# To generate optimized SQS candidates with icet:
pip install -e ".[sqs]"
# To launch the optional PySide6 desktop GUI:
pip install -e ".[gui]"
ss-screen-gui
# To run MACE-MPA-0 relaxation (install the cluster CUDA build first):
pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[mlp,phonon]"
```

To start with the original **MP ZIP** and recompute candidates/groups before
producing the 318 mBJ pairs, use `ss-screen mp-reproduce --mp-zip ... --mbj-bundle ... --output-dir ...`.
Follow [MP ZIP → 318 pairs](docs/reproducibility/MP_ZIP_TO_318_ZH.md): this route
needs the original database, offline reader, and existing mBJ results. It calculates
robocrys descriptors afresh by default; a separately verified cache is opt-in.
The [historical protocol notes](docs/reproducibility/mp_2944_20261104.md) explain provenance.
To replay only the 318 pairs from a separately supplied data ZIP, follow the
[Chinese quickstart](docs/reproducibility/REPLAY_318_ZH.md) and use
`scripts/replay_mbj_results.py`; the original MP database and MACE are not needed.
The [observed environment constraints](requirements/reproduction-20261104/README.md)
separate screening, CPU MACE/Phonopy, and Windows GUI environments. Database
snapshots, computed band gaps, and model weights are separate assets; cloning
this repository does not download them or run electronic-structure calculations.

## CLI

```bash
ss-screen --help

# Stage 1: build a normalized Materials Project DataFrame from mp_offline.
# A reproducibility sidecar is written to mp.df.provenance.json by default.
ss-screen dataset mp \
  --offline-db /path/to/mp-offline/data/default.db \
  --output mp.df \
  --provenance mp.df.provenance.json

# Optional live Materials Project query. Credentials may come from MP_API_KEY or
# ~/.pmgrc.yaml; page size, retries, timeout, and stable sort are recorded in provenance.
ss-screen dataset mp --backend api --output mp.df

# Stage 1: build a normalized WBM DataFrame from extxyz
ss-screen dataset wbm --xyz wbm-dataset.xyz --output wbm.df

# Stage 1: build a normalized DataFrame from local POSCAR/CIF structure folders
ss-screen dataset structures \
  --input-dir data/CaS_CaSe_CaTe_POSCAR \
  --band-gap-default 0.0 \
  --e-hull-default 0.0 \
  --output local_structures.df \
  --provenance local_structures.provenance.json

# Stage 1a: screen composition-template candidates before structure matching
ss-screen composition-screen \
  --df mp.df --df local_structures.df --nelems 2 \
  --output composition_candidates.csv \
  --summary composition_summary.json

# Optional: pre-filter metallic / mixed-valence structures
ss-screen valence-filter --df-mp mp.df --df-wbm wbm.df --output valid_ids.json

# Stage 2: build robocrys condensed JSON inputs for grouping
ss-screen condense \
  --df mp.df \
  --output-dir condensed/ \
  --manifest condensed_manifest.jsonl \
  --index condensed_index.csv

# Optional: index or validate an existing condensed JSON archive
ss-screen condense-index --condensed-dir condensed/ --output condensed_index.csv
ss-screen condense-validate --condensed-dir condensed/ --output condensed_validation.csv

# Stage 3: match composition candidates by structure/environment fingerprint
ss-screen structure-match \
  --candidates composition_candidates.csv \
  --condensed-dir condensed/ \
  --output group_df.json \
  --summary structure_match_summary.json

# Stage 3a: export structures/metadata for external high-level band-gap calculations
ss-screen gap-export \
  --groups group_df.json \
  --dataset mp.df \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --structure-dir gap_structures/ \
  --structure-format json \
  --structure-format cif \
  --structure-format poscar \
  --results-template gap_results_template.csv \
  --method-metadata-template method_metadata.json \
  --output gap_tasks.csv

# Stage 4: collect a batch of task_id/vasprun.xml calculations
ss-screen gap-collect-vasp \
  --tasks gap_tasks.csv \
  --results-dir vasp-results/ \
  --method-metadata method_metadata.json \
  --output user_gap_results.csv \
  --report vasp_collection_report.json

# Then validate identities, settings and numerical results
ss-screen gap-validate \
  --tasks gap_tasks.csv \
  --gaps user_gap_results.csv \
  --method-metadata method_metadata.json \
  --output gap_results.normalized.csv \
  --rejected gap_results.rejected.csv \
  --report gap_validation.json

# Stage 5: enumerate promising alloying pairs from computed gaps
ss-screen pair \
  --groups group_df.json \
  --gap-results gap_results.normalized.csv \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --summary gap_feedback_summary.json \
  --output final_pairs.csv

# Stage 5a: compare final pair lists from multiple theory levels
ss-screen gap-compare \
  --groups group_df.json \
  --gap-results gap_results.normalized.csv \
  --output-dir gap_method_comparison/ \
  --summary gap_method_comparison.json

# Stage 6: generate preliminary alloy/SQS input artifacts for stability screening
ss-screen stability sqs-generate \
  --pairs final_pairs.csv \
  --dataset mp.df \
  --backend icet \
  --target-fraction 0.5 \
  --cutoff 4.0 \
  --sqs-steps 10000 \
  --supercell 2,2,2 \
  --output-dir sqs_structures/ \
  --manifest sqs_manifest.jsonl

# Stage 7: relax SQS and endmembers with MACE and collect E/F/stress
ss-screen stability relax \
  --manifest sqs_manifest.jsonl \
  --include-endmembers \
  --backend mace \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --fmax 0.03 \
  --max-steps 500 \
  --output-dir relaxation/ \
  --results relaxation/relaxation_results.jsonl

# Stage 8: estimate SQS mixing enthalpies from compatible relaxed energies
ss-screen stability mixing-enthalpy \
  --pairs final_pairs.csv \
  --relax-results relaxation/relaxation_results.jsonl \
  --output thermodynamics/mixing_enthalpy.csv \
  --summary thermodynamics/mixing_summary.json

# Stage 9: finite-displacement phonon bands and DOS using MACE energies/forces
ss-screen stability phonon-run \
  --relax-results relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float64 \
  --displacement 0.01 \
  --mesh 20,20,20 \
  --output-dir phonons/

# Stage 10: discover MP competing structures, relax them with the same MACE
# checkpoint, and build strict same-energy-reference convex hulls. The default
# API backend securely prompts for the Materials Project API key.
ss-screen stability phase-diagram \
  --relax-results relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --mp-max-e-hull 0.1 \
  --output-dir phase_diagram/

# Network-isolated alternative. Install the local mp_offline package first;
# the SQLite snapshot remains external and is never copied into the project.
ss-screen stability phase-diagram \
  --relax-results relaxation/relaxation_results.jsonl \
  --mp-backend offline \
  --offline-db /path/to/mp-offline/data/default.db \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 \
  --dtype float32 \
  --mp-max-e-hull 0.1 \
  --output-dir phase_diagram_offline/

# Stage 11: join pair, gap, mixing, phonon, and phase evidence into an
# auditable decision-support table and Markdown report
ss-screen recommend \
  --pairs final_pairs.csv \
  --gap-results gap_results.normalized.csv \
  --mixing-enthalpy thermodynamics/mixing_enthalpy.csv \
  --phonons phonons/phonon_summary.csv \
  --phase-stability phase_diagram/phase_stability.csv \
  --output recommendations.csv \
  --report recommendation_report.md \
  --summary recommendation_summary.json

# Stage 13: compare endmember lattices and search local substrate matches
ss-screen geometry-evaluate \
  --input 13_geometry/input \
  --config 13_geometry/config.json \
  --output 13_geometry

# Legacy notebook-style gap CSVs are still accepted:
ss-screen pair --groups group_df.json --gaps mbj_gaps.csv --output mbj_result.csv
```

All numerical thresholds (band-gap windows, atom-count caps, excluded elements)
are exposed as CLI options with research-default values; pass `--help` on any
command to see them. The `condense` command requires the optional `condense`
extra because it uses robocrys at runtime. Condensed structures are stored as
one JSON file per material (`condensed/{material_id}.json`) so multiple workers
can read, skip, and write independent files concurrently; manifest/index CSV
sidecars provide searchable metadata without replacing the per-material files.
High-level band-gap calculations are deliberately external to `ss-screen`.
The Stage 05 GUI offers two input paths (Stage 04 groups and the structure
DataFrame) and one ZIP output. The equivalent portable export is:

```bash
ss-screen gap-export --bundle --groups 04_groups/groups.json \
  --dataset 02_composition/candidates.df --output 05_gap/gap_inputs.zip
```

The ZIP contains task tables, JSON/CIF/POSCAR structures with relative paths,
result and method templates, the input groups, a skip list, source/file hashes,
and handoff instructions. It retains the existing 30-atom default export limit;
the GUI states this scope and a saved limit is preserved. No method needs to be
chosen in this export form. For VASP returns, keep the original exported task IDs
as directory names: `VASP-results/gap-TASK-ID/vasprun.xml[.gz]`. The collection GUI
offers **VASP原始计算文件** or **整理好的CSV文件**, with one active input path
and one output folder. In VASP mode it automatically uses the
project export, records actual method/settings and geometry from XML, and saves
the linked task table for validation. Unknown task IDs and extra directory levels
are rejected. The equivalent CLI is:

```bash
ss-screen gap-collect-vasp --task-source 05_gap/gap_inputs.zip \
  --results-dir VASP-results --output 05_gap/results_returned.csv
```

For a prepared CSV, the GUI automatically associates the project's registered
calculation records and validates task/material/method/structure identities and
gap values before import. Select a CSV in the software's result format; no task
table needs to be selected in the GUI. The equivalent CLI with an already
registered task table is:

```bash
ss-screen gap-collect-vasp --task-source prepared/tasks.csv \
  --results-csv prepared/results.csv --output 05_gap/results_returned.csv
```

Choose one of `--results-dir` and `--results-csv`. CSV import preserves calculation
statuses, marks absent tasks as missing, and does not reparse XML. Both modes save
the result table, report and automatic task/provenance sidecars, protecting
existing output files. In the GUI, **收集 / 导入带隙结果** now includes validation
for both input modes. Its validated `results_returned.csv` goes directly to
Stage 06 through **进入06端元配对**; the separate GUI validation entry is removed.
Successful collection fills the pairing input automatically without starting
pairing. Records without successful gaps remain visible, and the handoff is
disabled when no successful gap is available. The standalone `gap-validate`
CLI remains available for independent checks and existing scripts.

`prepare_calculation.py` remains available for explicit task/CSV handoffs from
other external workflows. This exports material inputs, not a configured DFT job
or calculated gaps. Existing ZIPs are never
overwritten; choose a new output name for another export.

`gap-export` assigns deterministic task IDs and structure hashes and writes
JSON/CIF/POSCAR structures plus result/method templates. `gap-collect-vasp`
batch-parses `task_id/vasprun.xml[.gz]` directories, and `gap-validate`
cross-checks returned task, material, method, structure, and settings identities.
Malformed or duplicate rows are rejected explicitly; valid failed/skipped rows
remain in the normalized result table for coverage accounting. Legacy seven-column
gap CSV/JSON records remain readable when no task table is supplied.
An AiiDA-based external runner only needs to propagate the exported task fields
and may add columns such as `aiida_process_uuid`; `ss-screen` never needs the
AiiDA profile, database/broker credentials, SSH settings, Computer/Code labels,
or pseudopotential paths.
The Stage 6 `stability sqs-generate` command supports a dependency-light
`--backend random` mode and an optimized `--backend icet` mode. The manifest
records which generator was used, together with backend limitations and
provenance needed by later MLP relaxation stages. Stage 7 uses an optional MACE
backend, preserves every input, and writes relaxed pymatgen structures plus
JSONL/per-task JSON records containing total/per-atom energy, the complete
force array, Cartesian stress in eV/Angstrom^3 and GPa, convergence, actual
steps, model/input hashes, and quality-control warnings. Matching task
fingerprints resume automatically; changed settings require `--overwrite`.
Stage 8 joins every SQS to its two relaxed endmembers, verifies a common energy
reference (model/version/hash, dtype, and complete settings), and computes
per-atom mixing enthalpy using the realized SQS composition when available.
Missing, unusable, ambiguous, or incompatible records remain visible as failed
output rows instead of being silently omitted.
Stage 9 uses Phonopy finite displacements and the same MACE checkpoint for fixed-
geometry energy/force/stress evaluation. It supports automatic or explicit
supercells, reference-force subtraction, per-task fingerprints and resume,
force-constant symmetrization, gamma-centered mesh screening, automatic
high-symmetry bands, DOS, CSV/JSON summaries, and PNG/PDF plots. The staged
`phonon-export`, `phonon-forces`, and `phonon-collect` commands expose the same
workflow for large or externally scheduled runs.
Stage 10 uses either the Materials Project API or an explicit `mp_offline`
SQLite snapshot only to discover competing entries and obtain structures.
`competing-export`, `competing-relax`, and `convex-hull` expose a resumable
workflow; `phase-diagram` runs all three steps. Every online run prompts for the
API key with hidden input and never stores it; offline runs store the database
SHA-256 and warn that completeness is scoped to that snapshot. Candidate and
competing energies must share the MLP model hash, dtype, optimizer, cell mode,
convergence settings, and structural QC policy. Missing, skipped, unconverged,
or incompatible competing phases make the hull incomplete by default; MP DFT
energies are never used as a fallback.
Stage 11 joins evidence by pair and SQS structure without silently dropping
missing stages. It reports `promising`, `uncertain`, or `low-priority` together
with L2--L6 evidence levels, explicit positive evidence, risks, missing data,
source warnings, and next steps. Ranking is deterministic and does not use an
opaque aggregate scientific score. Defect evidence can be supplied when
available and is optional unless `--require-defects` is selected. The default
mixing-enthalpy and same-MLIP hull thresholds are configurable triage values,
not universal stability criteria.
Stage 13 compares endmember lattice correspondence and evaluates one explicitly
selected relaxed alloy SQS (default seed101) against a user-supplied local
substrate library. It reports ZSL supercell matches and in-plane principal
engineering strain, while reusing existing property evidence without launching
DFT/MLP/phonon calculations. Its finite search is geometric screening evidence,
not proof of epitaxy, synthesizability, or device performance; see
`docs/lattice_substrate_matching_development.md`.

## Documentation

- `docs/PROJECT_PLAN.md` — full design and milestone roadmap
- `docs/PROJECT_LOG.md` — cross-session progress log
- `docs/algorithm_gap_backfill_pairing.md` — external gap contract and pair algorithm
- `docs/algorithm_competing_phase_hull.md` — Stage 10 MP/MLIP hull contract
- `docs/algorithm_recommendation.md` — Stage 11 recommendation and evidence contract
- `docs/lattice_substrate_matching_development.md` — Stage 13 lattice, substrate matching, strain, and file contract
- `AGENTS.md` — operating rules for AI assistants (read-only boundaries)
- `references/README.md` — curated historical notebooks/source with executed results
- `references/manifest.json` — machine-readable provenance, hashes, aliases, redactions, and exclusions

The `references/` archive is historical evidence, not canonical runtime code.
Large datasets, calculation directories, archives, `.aiida` data, generated
scheduler artifacts, and secrets remain external.

## Status

The staged CLI currently covers dataset normalization, composition screening,
condensed-structure archive generation, structure matching, external band-gap
handoff/feedback, method comparison, and preliminary SQS input generation. MLP
relaxation with energy/force/stress collection is also available through MACE,
followed by preliminary mixing-enthalpy estimation, MACE finite-displacement
phonon screening, and same-MACE Materials Project competing-phase convex hulls.
An auditable Stage 11 recommendation report is also available. Target-gap
queries, defect execution/ranking, and workflow-level orchestration remain
planned — see `docs/PROJECT_PLAN.md`. A CPU-only Stage 1--11 artifact-chain
fixture runs in default pytest/CI using tiny synthetic inputs and deterministic
substitutes for external or expensive engines; see `tests/data/e2e/README.md`.

## License

MIT
