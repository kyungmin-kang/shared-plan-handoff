# Current State Snapshot

- Project identifier: `os-pre`
- Rescue stage: `detailed-scan`
- Generated at: `2026-03-31T21:28:21+00:00`
- Detailed scan: `plans/os-pre/detailed-scan.md`

## Project Goal
Produce a submission-ready benchmark paper and maintainable research repo showing when modern solution methods and estimation methods succeed or fail in finite-horizon dynamic choice models, using one explicit evidence pipeline and one approved project plan.

## Current Reality
- The repo already has a real benchmark-and-paper pipeline: `src/main.py` orchestrates runs, `src/paper_config.py` defines frozen paper matrices, `src/paper_artifacts.py` builds stable bundle manifests, and `src/paper_tables.py` feeds manuscript artifacts into `draft/generated`.
- Stable evidence roots already exist in `outputs/paper_latest/tier23-main` and `outputs/paper_latest/tier23-heavy`, so the rescue should preserve and clarify that pipeline rather than replace it.
- The main completion risk is not missing implementation; it is that scope, manuscript claims, prototype methods, reproducibility, and legacy debris are not yet narrowed into one explicit submission plan.
- `OLD_ED/`, duplicate benchmark folders, draft build artifacts, and scattered root-level experiment remnants add maintenance noise and make it harder to tell what is canonical.
- Rescue should preserve the active benchmark entrypoints, paper configs, paper bundles, manuscript sources, and model docs while quarantining legacy and ad hoc artifacts.

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

## Recovery Questions
- What is already built and should be preserved?
- Which in-flight tasks are still valid?
- What should be explicitly superseded or dropped?
- What new milestones are needed after the rethink?
