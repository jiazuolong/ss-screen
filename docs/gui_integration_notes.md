# SS-Screen GUI Integration Notes

## 10 µm 原生 GUI 算例

在主工作台中选择「打开工程文件.ssproject」，打开「10.0 μm演示.ssproject」，选一个空目录作为工程根目录。也可以从主工具栏「新建 / 打开 10 µm 工作区」加载已有算例目录。两种方式都使用原有左侧 01–13 流程树和参数页。

将演示用的 default.db 放进本工程的 01_dataset，在 01 Materials Project 离线页面运行数据获取。预置结果对应数据库 SHA-256 d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8。02、04、06、09、12 使用原页面运行按钮，13 点击右下角「生成候选评价」。03、05 使用预计算结果；07、08、10、11 可直接点击页面的「进入下一步」按钮完成校验和交接。软件核对输入、分组、端元对和缓存文件，保留适用范围：1,407 个结构描述、116 对端元、108 个 SQS、76 项完整凸包。第 11 步的「本步结果」可查看相图。

## 05 从历史结果库匹配

在「收集 / 导入带隙结果」选择「从历史结果库匹配」，选择共享的 results.csv。当前工程需已导出 05 ZIP。可选择历史计算方法或自动匹配唯一记录。相同材料和化学式须通过结构哈希或库内 structure_json 的周期几何核验。多条可用记录、结构无法验证或没有材料记录时不回填带隙。输出目录中保留任务对应、校验报告及结果。存在成功结果时可点击「进入06端元配对」。

## Stage 11: per-target energy convex-hull plots (2026-11-12)

`python -m ssscreen.stability.phase_plot --entries <phase_diagram_entries.csv>
--summary <phase_stability.csv> --output-dir <new-directory>` renders existing
energies in the WSL project environment. Optional `--candidate-structures` and
`--competing-structures` directories connect the selected phase to MatterViz.
The output contains PNG/SVG pairs, a scoped `hull_entries.csv`, and
`phase_plot_index.json`. An existing output directory is never overwritten.

Each target uses its own chemical system and complete phase group. Pymatgen
reconstructs the candidate-inclusive hull from **energy per atom multiplied by
the atom count of the supplied formula**. Every phase's hull distance and the
target's summary composition/energy/hull distance must match before writing.
Duplicate phases, mixed targets, missing elemental references, nonfinite
energies, incomplete results and inconsistent distances are rejected.
Binary/ternary systems are supported; higher dimensions are explicitly rejected.
No model, relaxation, MP query or finite-temperature calculation is run.
The diagrams show 0 K potential-energy hulls for the supplied phase set.

`gui/phase_page.py` supplies a target selector, the complete plot, the current
target's phase table and a linked structure tab. PNG and SVG buttons open the
original files. **加载相图** accepts `phase_plot_index.json`; the selection is
remembered in local QSettings separately for each project. The page also
recognizes `11_phase/phase_plot_index.json` or its imported artifact alias.
It checks scoped entries, source summary and displayed image hashes.
`visualization.py` re-exports the page; Stage 11 **本步结果** opens it, while
**结果清单 / 来源** retains the original summary table.

The supplied 10 μm file has 46,077 entries for 586 targets. All 76 current demo
targets are covered: 2,681 scoped phase rows, including 1,168 unique structures.
Original relaxation records independently confirm every plotted energy and
model/settings signature. Reconstructed hull distances match within
1.1e-14 eV/atom. The 76 PNG/SVG pairs and source hashes are in
`work/stage11_phaseplots/plots`; GUI checks and energy audits are in the same
ignored work directory. External scientific files and demo configuration are
unchanged. The local per-project GUI display preference points to this index.

## Stages 09–11: live upstream inputs (2026-11-12)

`gui/stability_page.py` provides dedicated input/output panels for mixing
enthalpy, phonons and competing phases. Direct entry, stage-parent navigation
and reopening saved projects all use current upstream values:

| Page | Automatic inputs | Editable settings |
|---|---|---|
| 09 | Current 06 pair CSV and 08 relaxation JSONL | Result CSV and summary JSON |
| 10 | Current 08 JSONL, model file/name and dtype | Device, phonon supercell, displacement, mesh, bands, QC, resume and output directory |
| 11 | Current 08 JSONL/model/dtype/relaxation conditions and 01 MP source/database | Device, phase selection thresholds, hull criterion, completeness policy, resume and output directory |

Changing upstream paths immediately updates displayed fields and generated CLI
arguments. A saved downstream path/model does not override its live source.
Stage 11 follows Stage 01's API/offline mode and database; API authentication
still uses the existing connection/environment mechanism. Its fmax, maximum
steps and cell mode follow Stage 08 to preserve the energy reference. CPU/CUDA
remains independently selectable. Missing inputs are shown as pending rather
than replaced with old imported outputs.

The pages retain numerical and output settings through save/restore and project
switching. An imported phonon run that specifies minimum supercell length but
omits a fixed supercell retains automatic expansion; the GUI's fixed-cell
preset must not override it. Supercell/mesh text survives Click callback
round-trips. Additional calculation and retry controls are expandable.
Old fixed structure-ID lists and command variants are no longer applied to
09–11: these pages process the current 08 batch, with Stage 10's endpoint
inclusion option retained. Historical commands remain in original metadata
for explicit reproduction.

Buttons provide 09 → 10 → 11 → 12 navigation and never execute a task. Stages
10 and 11 both consume Stage 08, so their parameter pages can be prepared
independently of completion of 09/10. Entering 12 fills its real command form
with current 06/05 and 09/10/11 paths, retaining recommendation/output settings.
At execution/export time the existing Stage 08 evidence checker verifies the
current batch. Stage 09 requires compatible alloy/endpoint triples; 10/11 need
usable alloy structures and do not require endpoint energies. External command
export remains enabled for projects configured for external computation.

`work/stage09_11_auto/gui01` records native Windows GUI verification of live
paths/model/settings, rejected missing inputs, navigation, external export,
saved settings, API/offline switching, project switching and 1280/1600 layouts.
The real WSL Stage 09 CLI generated 108 rows identical to the demo in an
isolated work directory; 10/11 were exported only. No MACE, phonon or competing
phase calculation ran, and original demo hashes stayed unchanged.
`work/stage09_11_auto/open_demo.py` opens the actual demo at the new Stage 09
page, with screenshots and preserved settings in `current_demo`.

## Stage 08: automatic SQS inputs and Stage 09 handoff (2026-11-12)

`gui/relax_page.py` replaces the generic relaxation form with separate input
and output panels. Its read-only manifest follows the current Stage 07 output;
Stage 02 structure data is shown as an automatic fallback for old manifests.
Modern SQS manifests already contain endpoint structures, so their commands omit
`--dataset` and avoid an unnecessary pickle load in the MACE environment.
Users retain the model file/name, device, dtype, force threshold, maximum steps,
endpoint relaxation and cell optimization settings. Limit, retry and overwrite
controls are grouped under **续算与运行范围**. The scientific backend remains MACE.

The output panel contains the structure directory, result JSONL, status counts,
run/export action and **进入 09 混合焓**. Project settings, numeric parameters and
output locations survive save/restore and project switching. Old manually saved
Stage 08 manifest/dataset paths no longer override Stage 07/02. Legacy Stage 08
command variants are hidden. External-execution projects retain their export
button; opening this page and entering Stage 09 never launch a calculation.

`gui/relax_results.py` reads existing evidence without loading a model. It checks
the current pair/manifest identities, input/output structure hashes, output
location, model/dtype and relaxation settings. Local model files are checked by
SHA; when an external project's weights are unavailable locally, result model
identities and compatible alloy/endpoint triples are used. CPU/CUDA is not an
energy-reference distinction, matching the existing thermodynamics policy.
Legacy manifests with endpoint files remain supported; if endpoint files were
instead supplied from a dataset, their full input structures must match the
current Stage 02 dataset. New manifests with provenance must also pass Stage 07
checks. The core relaxation and thermodynamics algorithms are unchanged.

At least one usable, compatible alloy plus its two endpoints enables the
handoff. Failed/unconverged entries remain counted and never become usable
energy evidence. The button passes the current Stage 06 CSV and Stage 08 JSONL
to the real Stage 09 form, retaining its output settings for user review.
Changing inputs, model/settings or output files blocks stale-result handoff.

Native Windows GUI verification in `work/stage08_auto/gui02` reads the real
demo's 222 MACE records and invokes only the WSL Stage 09 CLI in an isolated
work project: all 108 mixing-enthalpy rows equal the original results. It also
checks external command export, automatic inputs, save/restore, project switch
and two window sizes. Original demo file hashes remain unchanged; MACE was not
executed. Unit tests use an explicitly fake relaxation backend.
`work/stage08_auto/open_demo.py` opens the actual demo at Stage 08. Its current
Stage 07 regeneration destination has no manifest yet, so Stage 08 waits for
that output; historical imported results remain available in the result view.

## Stage 07: automatic inputs and Stage 08 handoff (2026-11-12)

`gui/sqs_page.py` separates inputs and outputs. It reads the current Stage 06
pair CSV and Stage 02 structure dataset automatically, including direct entry
after restarting. Users edit only the target B-site fractions, supercell,
generator, cutoffs, optimization steps and seed, plus output destinations.
Cutoffs and optimization steps are enabled for icet. Random substitution remains
explicitly labelled as an initial alloy configuration, not optimized SQS.
The original saved numerical parameters and output paths are preserved.

Stage 07 now uses the whole current Stage 06 table. Legacy manually selected
pair/dataset inputs are ignored, and the old per-pair variant selector is hidden
for this stage. Historical per-pair commands remain in saved project metadata
for explicit CLI reproduction; their effective seeds must not be interpreted as
the seeds for the corresponding rows of a newly generated batch.

The real SQS CLI also writes `<manifest stem>.provenance.json`, recording input
file hashes, generation settings and the manifest hash. `gui/sqs_results.py`
checks these plus all written alloy/endpoint structure hashes and locations.
**进入 08 MACE弛豫** is enabled for a matching batch with at least one written
structure. Skipped entries remain counted; all-skipped, changed, missing or
legacy unverified results do not enable the handoff. Existing output locations
are protected in the GUI; use new destinations to generate a new batch.

The button opens the real Stage 08 form, filling its manifest and structure
dataset while retaining model, device, dtype, convergence settings and output
locations. It does not execute MACE or change the configured external-execution
mode. Clicking the Stage 07 parent also opens this parameter page.

`work/stage07_auto/gui02` contains a native Windows GUI -> WSL icet smoke test
using a tiny CaS/CaSe fixture (one structure, ten optimization steps). It checks
automatic inputs, generation, 07 -> 08, saved settings/project switching,
changed-input/parameter/structure rejection and two window sizes. MACE was not
executed. `work/stage07_auto/open_demo.py` opens the 116-pair demo read-only at
the new Stage 07 page; its evidence is in `work/stage07_auto/current_demo`.

## Stage 07–13: verified demo subset (2026-11-12)

The authorized `演示` project contains 116 pairs from the partially completed
Stage 03/04 run. Existing external results are bound by endpoint IDs, original
pair indices, effective SQS seeds, structure SHA-256 and method provenance.
The native GUI recomputed 108 mixing enthalpies and all 116 recommendations,
then exported the 116-row Stage 13 assessment. Imports are explicitly labelled;
8 skipped SQS, 4 failed phonons and unavailable geometry remain visible.

Native structure, phonon and recommendation viewers now resolve their standard
artifact names through the project aliases, so results can remain in the user's
Chinese stage folders. Geometry configuration saves to the selected config path;
Stage 13 exports default beside the selected geometry table. No local heavy
calculation is started when opening the saved project.
Saved forms are restored before rebuilding the project tree, so its initial
Stage 01–04 statuses use the actual configured paths.

The external `演示/.gui/open_stage07_13.py` opens Stage 13 by default;
`--run` explicitly performs the lightweight GUI walkthrough and refuses existing
outputs. Archived per-pair Stage 07 commands preserve the original effective seeds
for explicit CLI rebuilding; the current Stage 07 GUI follows the whole Stage 06
table as described above. Evidence, actual GUI command
logs and screenshots are in `演示/.gui/stage07_13_20261112`.

## Stage 06: configured result paths

The dedicated `gui/wavelength_page.py` has separate input and output panels.
Its read-only groups and gap-result fields follow the current Stage 04 output
and the verified Stage 05 collection, including when opening 06 directly after
restarting. Missing/unverified upstream results block execution rather than
falling back to a stale saved path. Wavelength, optional strict gap bounds, CSV
and report destinations retain saved values; a new project requires a wavelength.

The method selector and mixed-method checkbox are removed. The GUI inherits
all successful records from 05 using the existing CLI mixed-source mode:
per-endpoint methods and downstream review flags remain intact, and duplicate
successful records for one material still fail validation. Legacy GUI method
filters are ignored; explicit method filtering remains available in the CLI.

**进入 07 SQS合金** transfers this screen's pair CSV and the current Stage 02
structure dataset to the real SQS form without executing it. Existing fraction,
supercell, backend, seed and output settings remain intact. The button requires
a nonempty result whose input/output SHA-256 and wavelength/bounds match the
current form. New wavelength reports contain these identities. Older reports
remain visible as existing results, but require a fresh screening before this
handoff is enabled. Changing inputs/conditions or altering the CSV disables it.
Generic command restoration now preserves CLI text before callbacks, so saved
SQS supercells such as `2,2,2` survive repeated restoration.

Windows GUI -> WSL verification in `work/stage06_auto/gui03` imported the real
748-record CSV into an isolated project and reproduced all 116 original pairs.
Direct-open autofill, 06 -> 07, saved parameters, project switching, changed
inputs/conditions/output rejection and two window sizes were checked. Original
demo inputs, results and manifest were unchanged; SQS was not executed.

The GUI exposes only **按目标波长筛选端元对** under Stage 06. The older
**生成端元对** and **比较带隙方法** entries are hidden; their CLI commands
remain available for existing scripts. Stage navigation and saved legacy
page links open wavelength pairing. Removed command variants are ignored,
without translating legacy gap thresholds into wavelength parameters.
Stage 05 passes its verified result directly to wavelength pairing.

The native project tree reads the active or saved `pair-wavelength --output` and
`--summary` paths, including custom project-relative directories. When the CSV
has endpoint columns and its row count matches the report, Stage 06 displays
**已筛选 (N)**. This avoids reporting an unstarted stage merely because results
were written outside `06_pair`. Displaying existing results does not run screening.

## Stage 05: collection and validation in one page (2026-11-12, current)

The GUI has one **收集 / 导入带隙结果** entry for returned calculations;
the separate **校验外部带隙结果** entry has been removed. Both VASP-folder and
CSV modes validate identities, schema and values before publishing results.
`results_returned.csv` is the validated table used directly by Stage 06;
there is no second manual validation or required `results_normalized.csv` copy.
The standalone `gap-validate` CLI remains available for existing scripts.

The **收集 / 导入带隙结果** page keeps **输入栏 / Inputs** and
**输出栏 / Outputs**. Its **输入类型** selector shows exactly one active path:
**VASP 原始计算文件** selects the result root folder; **整理好的 CSV 文件**
selects a prepared result CSV such as `results_import.csv` or
`results_normalized.csv`. The output column still selects only an output folder.
Both path values and the selected mode survive project save/restore; inactive
inputs are not sent to the CLI. Existing folder-only projects remain compatible.

CSV mode calls `gap-collect-vasp --results-csv ...` through the real CLI. The GUI
uses the current export and already registered validation task tables internally;
no task-table control is added. CSVs must retain the software's result schema and
task identities. The importer selects a matching registered batch, then invokes
the existing strict validator. Unknown IDs, duplicate rows, invalid gaps or
identity mismatches reject the import before publishing outputs. Original task
IDs, methods and settings hashes remain intact. Missing task rows become explicit
`missing` records; gaps/directness/transitions on unsuccessful calculations are
cleared in the imported output, while the input CSV remains unchanged.

Both modes write `results_returned.csv`, `collection-report.json` and automatic
task/provenance sidecars. CSV reports identify the operation as `project-csv`,
record the input CSV hash and validation summary, and never claim a new XML parse.
Existing outputs cannot be overwritten. After a successful import, the GUI
automatically fills the Stage 06 gap input and current Stage 04 groups while
preserving wavelength, thresholds and other user choices. **进入06端元配对**
opens wavelength pairing without running it. The same verified result is also
carried to the recommendation input.
The button requires at least one successful gap. Before handoff, input/output,
task-table and registered-source hashes are rechecked; modified or unvalidated
results cannot be handed off. Failed and missing calculation records remain
visible and are not counted as successful gaps. Saved legacy task registration
is retained internally; old validation-page navigation opens the unified page.

The isolated Windows GUI/WSL verification in
`work/stage05_merge/gui_run_02` imported 748 records (544 successful), passed
them directly to the real Stage 06 CLI, and reproduced all 116 original pairs
row for row. It also checked saved settings, output tampering and an all-failed/
missing XML fixture. Original demonstration inputs and results were unchanged.
Older `.gui/open_stage05_dual.py --verify` scripts target the superseded button.

### VASP input mode

In VASP mode, the user selects **VASP结果文件夹** in the input column and an output
folder in the output column. The task-table, metadata and subset editors have
been removed. Accept exactly `VASP结果/gap-任务ID/vasprun.xml` (or `.xml.gz`), with
no intervening mBJ subdirectory. The source task IDs should stay as originally
exported in the current project's ZIP; the GUI does not ask for another CSV.

`gap_collect_page.py` passes the configured project export as an internal
`--task-source` argument to the real `gap-collect-vasp` CLI. The core
`pair/gap_collect_folder.py` verifies ZIP task hashes and formal task identities,
then matches returned directory names to one complete source batch. Locally
registered legacy task tables and adjacent `prepared/tasks.csv` are supported
when their IDs match. It never guesses material identity from a formula or
reverses the task-ID hash. Unknown IDs, nested folders and ambiguous XML/gz files
are rejected; expected tasks lacking files remain explicitly missing.

For readable XML, actual functional/spin parameters determine an XML-derived
method identifier. Full INCAR/parameters, k-points, POTCAR titles, VASP version,
input/final structures and XML SHA are recorded; POTCAR binary hashes are not
available from this input. Actual input geometry defines the derived result-task
hash. The original folder ID, method and structure hash remain in the matching
table, so changed calculation geometry is not falsely represented as identical.
Composition mismatches are failed records, with no accepted gap or material
reassignment. Unreadable/missing calculations retain source identities and
failed/missing status, without invented methods or gaps.

The output folder contains `results_returned.csv`, `collection-report.json` and
automatically managed `results_returned.tasks.csv` / `.provenance.json` sidecars.
The folder collector runs the shared strict validator in memory against its
generated matching task table before writing any result. The collection report
contains the validation summary, using per-task settings hashes without a
single uploaded method file. Existing files are protected. Legacy explicit CLI
`--tasks` / metadata / task-subset use still behaves as before.

The previous folder-only GUI verification entry was `.gui/open_stage05_folder.py`; evidence is under
`.gui/folder_collect_verification`. Only its explicit `--verify` mode runs an
isolated invalid-XML fixture. The actual demonstration result directory stays
blank until the user selects external VASP files. Older exported ZIPs remain
unchanged; this folder-return instruction supersedes their mandatory-prepared
CSV instructions for the current GUI. Future ZIP README files include both paths.

## Previous Stage 05 design: compact VASP collection (superseded)

The following records the earlier three-field version; the current dual-mode
design above removes the task-table input and its advanced metadata controls.

`gap_collect_page.py` replaces the generic `gap-collect-vasp` form with three
main fields: **计算任务清单** and **VASP结果文件夹** under **输入栏 / Inputs**,
and **输出文件夹** under **输出栏 / Outputs**. The result CSV and JSON collection
report are named automatically (`results_returned.csv`, `collection-report.json`).
The default folder follows the configured Stage 05 export location. Collection
reads completed `task_id/vasprun.xml[.gz]` files; it does not start VASP.

| Previous option | Purpose | New presentation |
|---|---|---|
| `--tasks` | Associate task IDs with materials, structures and actual methods | Main input |
| `--results-dir` | Find VASP XML under task-ID directories | Main input |
| `--method-metadata` | Record actual calculation settings and their hash | Automatically read `method_metadata.json` beside tasks; manual/none in Advanced |
| `--task-id` | Select only particular tasks | Advanced; blank means all; subset scope stays visible |
| `--output` | Write the collected band-gap CSV | Derived from output folder, shown read-only |
| `--report` | Write status counts and per-task failure/missing details | Derived from output folder, shown read-only |

Use the task table actually used for external calculations. With the new ZIP
flow this is `prepared/tasks.csv`; the GUI rejects pending-method export
templates. Existing CSVs with actual task identities are still accepted. Old
saved output/report names, optional metadata and task subsets are preserved;
changing the output folder resets the legacy report path into the new folder.
`command_forms` retains the automatic/manual/none metadata preference through
project save/restore without adding GUI-only flags to the scientific CLI.

The collector retains a task's settings hash when no single metadata file is
supplied. A supplied metadata file must agree with any existing task settings
hashes before collection writes outputs. Missing and unconverged/failed records
remain visible and are not converted into zero gaps. Existing GUI output files
are protected: choose a new folder for another collection.

After matching collection outputs exist, **进入结果校验** fills the existing
validation form with the collected CSV, corresponding tasks and actual metadata;
it does not run validation automatically. Already normalized/returned CSV data,
including the prepared historical mBJ records, can go directly to the separate
validation page without inventing VASP XML files.

The demonstration launcher is `.gui/open_stage05_collect.py`; normal startup
runs no collection. Its explicit `--verify` mode uses only an isolated malformed
XML/missing-file fixture under `.gui/collect_verification`, executes the real
GUI-to-WSL collector, checks the validation handoff, then clears fixture inputs.
The demonstration's actual VASP input fields remain empty until external files
are available. Existing Stage 05 scientific files are hashed before/after.

## Stage 05: two inputs and one ZIP (2026-11-12)

`gap_bundle_page.py` supplies the native **导出带隙计算压缩包** page. Its
**输入栏 / Inputs** contains only the Stage 04 groups JSON and the candidate
structure DataFrame; **输出栏 / Outputs** contains one ZIP destination. The
**读取上一步输出** button reads the current Stage 04/02 paths. There is no method,
format, template-path or command-preview control. **导出计算压缩包** invokes the
real `gap-export --bundle` CLI through the selected runtime backend.

Old saved export commands restore their input paths and migrate CSV output to
`带隙计算输入.zip` in the same folder. Their atom-count limit and structure column
are retained internally; the page states the atom-count scope (default 30).
New commands and project snapshots preserve all three fields. The tree reads
the ZIP manifest and the output column displays its task and skip counts.

The ZIP includes all exported structures, task/result tables, method template,
input groups, skipped-material list, provenance, per-file hashes, instructions
and `prepare_calculation.py`. Paths are relative to the extracted root. The
external operator supplies actual method/settings and uses the helper to create
formal task/result identities while retaining pending-task mappings. The package
does not invent DFT settings or contain calculated gaps. Existing output files
are refused, and missing candidate structures fail before publication.

CLI/scientific checks run in the WSL project environment. Windows GUI checks use
the native controls, saved-command round trips and a real QProcess-to-WSL ZIP
export. The demonstration entry is `.gui/open_stage05_zip.py`; it starts no task
unless explicitly invoked with `--verify-export`. Evidence is recorded in
`.gui/stage05_zip_status.json`, `.gui/stage05_zip_export.log` and `05_zip_ready.png`.
The demonstration export passed with 748 tasks and 64 atom-limit skips from 812
unique members of the current 398 partial groups. All 2,252 file hashes and ZIP
CRC checks passed; task IDs match the earlier CSV export. The single deliverable
is `演示/05带隙交接/带隙计算输入.zip` (1,407,804 bytes); existing inputs/results remain
unchanged and no gap calculation or Stage 06 task was started.

## Stage 05/06 parent navigation (2026-11-12)

In ordinary projects, clicking Stage 05 now expands its command children and opens
**导出带隙计算压缩包**. Stage 06 likewise opens **按目标波长筛选端元对**.
Previously both parent items fell through to the project overview; their command
forms existed but were hidden behind collapsed tree nodes. Saved `stage_commands`
take precedence, and imported `workflow_stages` continue using their own controller.
The children still expose all three commands per stage; navigation never runs them.

The demonstration launcher `.gui/open_stage05_06.py` opens the native window and
verifies actual mouse clicks on both parents and all six command children, form
retention, configured entry points and imported-workflow compatibility. Screenshots
and `stage05_06_navigation_status.json` are stored beside the launcher. Its project
settings now contain the previously documented Stage 05 export paths and Stage 06
10 μm / strict 0–0.4 eV parameters, without replacing existing command settings.
At that navigation-fix checkpoint the Stage 05/06 output directories were empty.
Stage 06 still requires the normalized band-gap results from Stage 05.

## Stage 03 stop/resume and partial Stage 04 (2026-11-11)

Stage 03 now has fixed controls above its tabs: **停止计算（保留结果）** and
**使用已完成结果进入 04**. Stop requests are shared files, with a unique path
per GUI run, passed to `condense --stop-file`. Windows and WSL see the same
request. The worker finishes its current structure, then exits with code 130;
the GUI reports a stopped run instead of full completion. The toolbar Stop
uses this mechanism for `condense`. Closing during condensation requests the
same stop and waits for the worker before closing the window.

Each attempted structure is journaled to the manifest. The index and manifest
are finalized on normal completion, cooperative stop or a handled interrupt.
Completed JSONs remain intact. Running again uses a new stop file and the
existing skip behavior, so completed structures are not recomputed by default.
The stop can take as long as the current structure; it is not an immediate
process kill. These changes do not add cooperative cancellation to other CLI
commands.

The Stage 03 handoff button requests a stop first when condensation is active,
then opens Stage 04. Stage 04 defaults to the configured Stage 02 candidate CSV
and Stage 03 output directory. Uncheck its follow-input option for manual
archive selection; saved legacy manual inputs retain that mode. The handoff
fills the form; the user starts matching with Stage 04's run button.

Matching freezes available file membership when it starts, catches malformed
JSONs as invalid, and preserves missing candidates in its summary. Reports now
include unique candidate/available/missing/invalid material counts, available
IDs, coverage and `partial_run`. GUI summaries distinguish unique material
counts from repeated template rows and label partial results explicitly.
The structure matching algorithm and minimum X-element requirement remain unchanged.

For the current demonstration, the old worker was interrupted at 1,407 outputs.
All 1,407 passed validation. Its old code had no incremental manifest; the
recovered manifest records existing files as `present`, while 3,541 missing
descriptions remain `unavailable` without inventing a failure count. The recovery
record is `03结构描述归档/独立复现/interruption_recovery.json`.
Actual GUI-to-WSL matching produced 398 groups under
`04结构匹配与材料分组/部分结果/`, with 28.4% description coverage. This is not a
complete 4,948-material screening result. `.gui/open_stage03_04.py` opens the
updated native GUI without starting another calculation. Stop/resume and
matching evidence is under `.gui/stop_verification/`.

## Stage 02 binary/ternary selection and Stage 03 input (2026-11-11)

Stage 02 has separate input/output columns. Binary and ternary checkboxes are
both enabled by default; either may be unchecked, but at least one is required.
Only 2 and 3 elements are supported. The existing per-count scientific rules
are unchanged. One run writes three configured files:

- `composition_candidates.csv`: combined template membership rows; a material
  may occur in several templates. Multi-count runs include a `nelems` column.
- `composition_summary.json`: total counts, `by_nelems` branch statistics and
  `unique_candidate_materials`, plus input and structure-output paths.
- `candidates.df`: each candidate ID once, preserving the input material index,
  original structure and all other input columns. No old condensed archive is
  used to create this table.

The CLI accepts repeated `--nelems 2 --nelems 3` and the new
`--structures-output <candidates.df>`. Single-count CLI calls remain supported;
structure export is optional for existing CLI consumers, always supplied by
the dedicated GUI. Ambiguous duplicate input IDs, missing structure columns,
and colliding input/output paths are rejected before outputs are written.

Stage 03's DataFrame tab defaults to **默认使用 02 输出的候选结构 candidates.df**.
While checked, its input follows the Stage 02 structure output path. Uncheck it
to browse or enter another DataFrame. Both the choice and paths survive project
saves. Legacy `nelems_edit` settings migrate to the corresponding checkbox;
legacy explicit Stage 03 inputs retain manual mode.

In the current demonstration project, all three outputs are under
`演示/02组成模板筛选/`; `.gui/open_stage02.py` opens the updated native window.
At gap < 1 eV and hull <= 0, GUI-to-WSL verification produced 10,232 CSV rows
(3,356 binary + 6,876 ternary) and 4,948 unique original structures. Both CSV
branches exactly match the existing separate runs. Stage 03's actual input
reader accepts all 4,948 structures; descriptor generation was not started.

## Stage 01 MP input/output columns (2026-11-11)

The Materials Project tab separates its form into two equal-width columns:
**输入栏 / Inputs** contains the source mode, existing database and hull filter;
**输出栏 / Outputs** contains the generated DataFrame path, provenance path and
file status. These files are created by the run and need not exist beforehand.
For offline MP imports, **输出位置跟随输入数据库目录** is enabled by default:
selecting `01数据源/default.db` fills `01数据源/mp.df` and
`01数据源/mp.df.provenance.json`. The output files sit beside the selected
database, including when it is in a nested `输入` folder. Paths inside the
project are displayed relative to the project; external paths stay absolute.
API mode or an empty database field retains the `01_dataset/` fallback.

Typing or browsing a custom output disables automatic following; checking the
box again restores source-based defaults. This choice survives project saves
and switches. Older saved projects with explicit output paths retain those paths.
The command preview and acquisition action use the displayed paths; the project
tree reads the configured MP outputs, and a successful MP import adds its actual
DataFrame to stage 02. No scientific filter or CLI calculation is changed.

The current user-operated demonstration root is
`C:/Users/19756/Desktop/重要文件/ss-screen-local-results/演示`, with numbered
Chinese stage folders 01–13. Its stage 01 database is currently
`01数据源/default.db`, and the GUI is opened by `.gui/open_demo.py` inside that
root. This is a local demonstration configuration, not a hardcoded application
path. Import execution remains a user action.

## Native imported workflow projects (2026-11-11)

The original `MainWindow` now reads `gui_settings` from `.ssscreen-project.json`.
`workflow_project.py` restores the existing dataset, composition, archive,
structure-match and assessment controls, and real Click command forms for the
remaining stages. `pair-wavelength` is registered in stage 06. The workflow
toolbar switches parameters, completed results and batch presets; parameter
pages are never replaced by JSON text. Stage 13 has an editable geometry
configuration form. Settings survive project snapshots and project switching.

Imported sources remain outside the repository. Small tables are staged in the
new project; dataset aliases and structure/phonon indexes reference originals.
A new local output takes precedence over a read-only imported alias. Imported
tables retain failed/skipped/unresolved records and calculation batch identity.
The original full batch did not return per-phase hull entries, so stage 11 shows
the complete hull summary rather than inventing a hull diagram.

Projects can mark commands as external. Their buttons export argv JSON and copy
the command; they never start a local QProcess. Exported command records are not
portable computation packages: input/model/output paths must be mapped on the
external machine; existing package locations are included. No upload or job
submission is implied. Standard projects without this setting still run normally.

For the completed local MP 10 μm run, use
`scripts/prepare_native_mp_workflow.py --results-root <run> --output <new-project>`
in WSL `.venv`, then open the resulting project using the standard
`ss-screen-gui <new-project>` entry point in Windows `.venv-gui`.
`scripts/verify_native_workflow_gui.py <project> --replay-pairs` visits all 13
native parameter/results pages and executes only the lightweight pairing step
through the GUI's WSL QProcess. Heavy calculations remain external.

Related tests: `tests/test_gui_workflow_project.py`, `test_gui_project_file.py`,
`test_gui_wsl.py`, `test_gui_appearance.py`, `test_wavelength.py`.

## Goal

The desktop GUI should preserve the workflow thinking from the standalone review
build while keeping the existing CLI as the authoritative scientific runtime.
The two public entry points should coexist:

```text
ss-screen      # real Click CLI and scientific pipeline
ss-screen-gui  # optional PySide6 desktop workbench
```

## Design Kept From The Review Build

- A project-oriented workbench with a left project tree, central parameter pages,
  right-side properties, and a bottom log/file/message area.
- The workflow is organized by the same staged material-screening flow as the
  CLI: data sources, composition screening, structure condensation, structure
  matching, gap handoff, pairing, SQS, relaxation, thermodynamics, phonons,
  phase diagram, and recommendation.
- GUI pages collect user-facing inputs and convert them back into CLI arguments.
- Long-running work is executed through `python -m ssscreen.cli.app ...` so the
  CLI and GUI share validation, defaults, output schemas, and exit codes.
- API keys, when entered in the GUI, should be injected only into the child
  process environment and not written to commands, project files, or logs.

## Integration Boundary

For WSL execution, the connection's WSL path locates the code environment.
The GUI first enters that directory and activates `.venv` or `.venv-mlp`, then
changes to the active data project's directory before invoking the CLI. Relative
inputs and outputs therefore belong to the active GUI project, even when it is
outside the code checkout. The displayed execution command follows the same
construction as the launched command; its preview excludes the API key.

The GUI must not replace or simplify `src/ssscreen/cli/app.py`. Any preview-only
or mock command surface should remain outside the production package. The CLI is
the contract used by tests, documentation, automation, and future Web workers.

The formal package exposes the GUI as an optional extra:

```text
pip install -e ".[gui]"
ss-screen-gui
```

For a fuller Ubuntu development environment, use the repository
`requirements.txt`.

## Desktop Result And Project Integration

- Stage 08's result view opens the relaxed/SQS structure browser and renders the selected
  structure with the bundled MatterViz 0.7.0 WebGL frontend.
- Stage 10 presents phonon status, minimum frequency, band/DOS figures, and the
  linked structure in one page.
- Stage 11 presents the competing-phase table, a ternary composition/hull map,
  and the selected competing structure.
- CPU is the default MACE device in the desktop presets. Users may still enter
  an explicit CUDA device when the target machine benefits from GPU execution.
- CLI option rows display a Chinese label together with the authoritative
  command-line flag so domain users can understand the parameter without losing
  reproducibility.
- `.ssproject` is a ZIP64 project container with a versioned `project.json`, an
  SHA-256 manifest, and artifacts from Stage 01 through Stage 12. API keys are
  explicitly excluded. Opening a project validates paths and checksums before
  extracting it to the application project cache.
- The SSH panel is intentionally a read-only validation probe in this iteration.
  It checks authentication, remote Python/`ss-screen`, and an optional remote
  project directory; it does not submit, stop, poll, or download remote jobs.

The MatterViz control sidebar is disabled because MatterViz 0.7.0 currently
triggers a `svelte-widgets` multi-select initialization error in that optional
panel. Core WebGL rendering, atom visibility, replication, mouse rotation,
zoom, and pan remain available.

## Near-Term Follow-Up

The desktop toolbar places a View / 视图 dropdown beside the project actions.
It provides 界面字号, with exclusive 9--18 pt
choices (default 10 pt) and a restore-default action. Changes apply immediately and persist through Qt application
settings, independently of `.ssproject` scientific parameters. Native text,
table rows/columns, command previews, and embedded MatterViz zoom follow the
chosen size. Qt 6 uses native high-DPI rendering with fractional scale factors
preserved at startup. This addresses small text; actual monitor sharpness still
depends on the system's display scaling and native resolution.

Toolbar actions use Qt's overflow menu on narrow windows. The central work area
and inspector scroll when content exceeds the available size; inspector fields
are arranged vertically and long form rows wrap. Wide scientific tables remain
horizontally scrollable at large font sizes.

- Add a small import/launcher smoke test once a GUI-capable CI environment is
  available, or keep it guarded so headless Linux does not need a display server.
- Review each specialized GUI page against the restored real Click command
  options and remove any parameter that is only valid in the standalone demo.
- Promote the SSH probe into an explicit remote-job protocol only after a server
  test account is available. That protocol still needs upload/download rules,
  remote process identity, durable status files, reconnect behavior, and safe
  cancellation semantics.
