# Dogfood Retrospective And Next-Cut Backlog

This note captures what worked, what still felt rough, and what should land
after the first public share of `Shared Plan Handoff`.

## What Worked

- The repo-first handoff model held up: approved docs, task graph, review gate,
  and Notion workspace all stayed legible as separate artifacts.
- Rescue mode was useful once it became goal-first and separated `Rescue
  Understanding` from `Bring-It-Home Workstreams`.
- MCP-first Notion mutation was a much better default than relying on the stale
  REST token path for normal interactive use.
- The live `Shared Plan Handoff` Notion workspace is now good enough to
  drive real work without constantly reopening the repo.
- The product successfully dogfooded itself through planning, workspace build,
  execution, and plugin packaging.

## What Felt Rough

- Notion linked-database limitations still force a hybrid human-agent setup for
  the best inline PM views.
- View ergonomics are still a compromise: the `Tasks -> All tasks` surface is
  strong, but richer Team-Projects-style visual composition remains partly
  manual.
- Docs library sync is still mostly explicit rather than automatic; new repo docs
  should eventually be easier to publish into Notion.
- Transport handling is conceptually clear now, but the code still centers the
  Python bridge while the everyday mutation path is MCP-first. That split is
  correct, but not yet elegantly packaged.

## What We Learned

- Treating failures as systematic errors is the right operating rule for this
  product. The branch-creation issue and the phase-label drift both looked
  incidental at first, but each reflected a real workflow assumption that needed
  to be fixed at the system level.
- Humans need the Notion PM surface to be understandable without repo context,
  but the repo still needs to remain the upstream source of truth. The product
  is strongest when it respects both halves of that design.
- A repo-local plugin is useful primarily because it makes the intended workflow
  discoverable, not because it replaces the local skills or the coordinator.

## Next-Cut Backlog

### High priority

- Auto-publish new release-confidence and retrospective docs into the Notion
  Docs library as part of the normal Phase 5 flow.
- Add a dedicated QA report artifact and link it from the project page after a
  verification pass.
- Improve docs-library metadata handling so `Repo Path` values remain readable
  in Notion despite underscore-heavy filenames.

### Medium priority

- Make inline-view setup guidance more structured and reusable across projects.
- Add a cleaner MCP-first abstraction layer so the bridge can express transport
  policy more directly in code.
- Expand tests around plugin packaging and docs-library publishing beyond the
  current scaffold and presence checks.

### Lower priority

- Explore a richer phases/tasks visual model that gets closer to the best parts
  of the Notion `Team Projects` template without depending on unsupported
  connector features.
- Revisit whether repo artifacts should optionally live in the target project
  instead of this PM repo for multi-repo use.
