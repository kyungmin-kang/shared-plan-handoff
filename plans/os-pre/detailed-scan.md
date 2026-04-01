# Detailed Rescue Scan

- Project identifier: `os-pre`
- Generated at: `2026-03-31T21:28:21+00:00`
- Quick scan reference: `plans/os-pre/current-state.md`

## Project Goal
Produce a submission-ready benchmark paper and maintainable research repo showing when modern solution methods and estimation methods succeed or fail in finite-horizon dynamic choice models, using one explicit evidence pipeline and one approved project plan.

## What Completion Requires
- Freeze one approved paper scope and empirical claim set for the final submission.
- Keep `src/main.py` and `run_benchmark.sh` as the canonical rerun entrypoints, with `src/paper_config.py` defining the frozen paper matrices.
- Treat `outputs/paper_latest/tier23-main` and `outputs/paper_latest/tier23-heavy` plus their bundle manifests as the canonical evidence roots unless a new approved rerun supersedes them.
- Regenerate manuscript-ready tables and figures into `draft/generated` from stable bundles.
- Rewrite the results, practical guidance, and conclusion sections so every claim maps to saved evidence.
- Lock a reproducible environment for the optional solver stack and document the exact commands a collaborator should run.

## What Maintenance Requires
- Separate active assets from archived or noisy material so a future contributor can tell what is canonical.
- Preserve one durable status summary, one approved plan, and one rescue notebook rather than spreading planning across many files.
- Keep canonical commands, outputs, and paper bundles documented in one place.
- Reduce ambiguity around prototype methods, especially Diff-MPC and optional heavy SAC passes, so maintenance work does not accidentally treat exploratory results as frozen paper evidence.
- Move or quarantine legacy and ad hoc artifacts that are useful historically but should not drive current execution decisions.

## Detailed Findings
### Clear Goal
- The repo’s real goal is not to become a general-purpose solver platform first; it is to finish a journal-submission-ready benchmark paper with a reproducible evidence pipeline.
- The codebase should support that paper by making the benchmark matrix, saved evidence, manuscript tables, and manuscript claims line up cleanly.

### Essential Active Files And Paths
- `README.md`: project-level workflow and canonical commands.
- `src/main.py`: top-level orchestrator for benchmark runs.
- `run_benchmark.sh`: wrapper that selects `.venv/bin/python3` when present and routes through `src.main`.
- `src/paper_config.py`: defines the named paper matrices such as `tier23-core`, `tier23-heavy`, `tier23`, and `tier23-uncertainty`.
- `src/paper_artifacts.py`: bundles model run outputs into stable `paper_latest` manifests and symlink bundles.
- `src/paper_tables.py`: generates manuscript-ready tables and figures into `draft/generated`.
- `draft/master.tex` and section files in `draft/`: the manuscript source of truth.
- `docs/model1/*`, `docs/model2_labor/*`, `docs/model2_retirement/*`, `docs/model3/*`: model-specific explanation and result interpretation.
- `outputs/paper_latest/tier23-main` and `outputs/paper_latest/tier23-heavy`: current canonical evidence bundles with `paper_bundle_manifest.json`.
- `tests/test_main_entrypoint.py`, `tests/test_paper_artifacts.py`, `tests/test_paper_tables.py`, `tests/test_paper_config.py`: lightweight regression coverage around the execution and paper-artifact pipeline.

### Evidence That The Core Pipeline Already Exists
- `README.md` names `src/main.py` as the canonical entrypoint and documents dry-run and paper-config flows.
- `src/main.py` centralizes model registry, alias resolution, paper-config selection, and output routing.
- `src/paper_config.py` already encodes a paper-ready matrix across four arenas with distinct core, heavy, and uncertainty passes.
- `outputs/paper_latest/` already contains stable bundled evidence roots for `tier23-main` and `tier23-heavy`.
- `PROJECT_STATUS_SUMMARY.md` says the strongest current asset is breadth of real benchmark infrastructure and saved evidence, not speculative future work.

### Work In Progress And Ambiguity
- The manuscript scope and final empirical claims are still not frozen tightly enough for submission.
- Prototype methods, especially Diff-MPC in some arenas, appear partially implemented but not consistently evidenced across the saved paper artifacts.
- The environment for the full optional stack is not locked, so collaborator reproducibility is weaker than it should be.
- Planning is fragmented across `README.md`, `notes.md`, `outline.md`, `PROJECT_STATUS_SUMMARY.md`, manuscript sections, and historical outputs.
- The repo root is not a git working tree, which makes durable maintenance and audited plan evolution harder.

### Likely Preserve Set
- Active `src/` benchmark entrypoints and shared utilities.
- `src/paper_config.py`, `src/paper_artifacts.py`, and `src/paper_tables.py`.
- `draft/` manuscript source and `draft/generated` output path.
- `docs/` model notes that explain methods and interpretation.
- `outputs/paper_latest/*` and the best `outputs/paper_runs/*` manifests that underpin the stable bundles.
- The recent `PROJECT_STATUS_SUMMARY.md` because it already captures much of the current state accurately.

### Likely Noisy Or Historical Material To Quarantine
- `OLD_ED/` and nested legacy copies.
- Root-level ad hoc benchmark directories outside the canonical `outputs/paper_runs` and `outputs/paper_latest` structure, such as older debug or duplicate benchmark folders.
- Draft build artifacts and conflict copies inside `draft/` that are useful locally but should not drive rescue decisions.
- Standalone root-level PNGs and one-off experiment remnants unless they are explicitly referenced by the current manuscript.

### What The Rescue Should Solve
- Pick one approved paper scope and define which saved bundles count as the evidence base.
- Decide whether Diff-MPC is a main result, a secondary result, or appendix/future work in each arena.
- Reduce the active surface area of the repo so execution decisions are driven by canonical commands and bundles only.
- Convert the existing status knowledge into one approved repo plan that can be decomposed into PM tasks cleanly.

### What Will Make Future Maintenance Easier
- One approved plan file that points to canonical commands, active files, and approved evidence roots.
- One rescue notebook in Notion for durable context snapshots before the execution workspace is built.
- One environment lock or reproducibility note covering optional solver dependencies.
- A clearer distinction between active benchmark artifacts and historical exploration.
- A lightweight maintenance rhythm where new reruns update stable bundle manifests and then refresh manuscript tables from those bundles instead of ad hoc output paths.
