# Recovery Plan Draft

## Objective
Stabilize `OS_pre` and convert the repo into one explicit, approved execution plan that can re-enter the normal handoff pipeline.

## Goal
Produce a submission-ready benchmark paper and maintainable research repo showing when modern solution methods and estimation methods succeed or fail in finite-horizon dynamic choice models, using one explicit evidence pipeline and one approved project plan.

## Inputs
- Current state snapshot: `plans/os-pre/current-state.md`
- Detailed rescue scan: `plans/os-pre/detailed-scan.md`

## Definition Of Completion
- Freeze one approved paper scope and empirical claim set for the final submission.
- Keep `src/main.py` and `run_benchmark.sh` as the canonical rerun entrypoints, with `src/paper_config.py` defining the frozen paper matrices.
- Treat `outputs/paper_latest/tier23-main` and `outputs/paper_latest/tier23-heavy` plus their bundle manifests as the canonical evidence roots unless a new approved rerun supersedes them.
- Regenerate manuscript-ready tables and figures into `draft/generated` from stable bundles.
- Rewrite the results, practical guidance, and conclusion sections so every claim maps to saved evidence.
- Lock a reproducible environment for the optional solver stack and document the exact commands a collaborator should run.

## Maintenance Baseline
- Separate active assets from archived or noisy material so a future contributor can tell what is canonical.
- Preserve one durable status summary, one approved plan, and one rescue notebook rather than spreading planning across many files.
- Keep canonical commands, outputs, and paper bundles documented in one place.
- Reduce ambiguity around prototype methods, especially Diff-MPC and optional heavy SAC passes, so maintenance work does not accidentally treat exploratory results as frozen paper evidence.
- Move or quarantine legacy and ad hoc artifacts that are useful historically but should not drive current execution decisions.

## Recovery Milestones
1. Lock the true project goal and narrow the scope to the finishable core.
2. Separate essential active assets from archived, noisy, or superseded material.
3. Freeze one explicit approved plan revision with canonical commands, artifacts, and evidence sources.
4. Re-run decomposition and reviewer checks on that approved plan.
5. Publish or refresh the shared rescue notebook in Notion when durable context would help.
6. Build or reconcile the execution workspace only after the reviewed handoff is ready.

## Immediate Actions
- Review the current-state snapshot with the human and confirm the real end goal.
- Identify the essential files, canonical commands, and saved evidence that must survive the rescue.
- Turn the recovery draft into the next approved plan revision when the scope is stable.

## Additional Rescue Context
Use the detailed rescue scan as the basis for the next approved plan revision.
