# Maintaining the docs

The docs in this repo are the project's memory between agent sessions. A session that changes the
project and leaves the docs stale has not finished its task. These rules say what goes where and when
to update it.

## Where things live

| File | Holds | Does not hold |
|---|---|---|
| `README.md` | User-facing: what it does, install, usage, how it works in brief | Internals, plans, agent instructions |
| `AGENTS.md` | Entry point for agents: commands, doc index, hard rules | Explanations; keep it short and link out |
| `docs/architecture.md` | Module map, algorithms, data flow, invariants the code relies on | Line numbers, function bodies |
| `docs/development.md` | Setup, testing, platform quirks, gotchas found the hard way | Design rationale |
| `docs/decisions.md` | Settled decisions with the reason, so they are not reopened | Open questions (those go in the roadmap) |
| `docs/roadmap.md` | Open and recently finished tasks, with status | History older than the last release |
| `HANDOFF.md` (local only) | Machine-specific or private context: local paths, the user's other repos, credentials setup | Anything that belongs in a tracked doc |

When unsure: if a stranger cloning the repo would benefit, it goes in a tracked doc. If it only makes
sense on this user's machine or mentions something private, it goes in `HANDOFF.md`.

## When to update

Before ending a task, check each trigger against what you did:

- **Changed code structure** (new module, moved responsibility, changed algorithm) →
  `docs/architecture.md`.
- **Changed CLI flags or output format** → `README.md` (usage table and examples) and, if the change
  reverses a settled choice, `docs/decisions.md`.
- **Lost time to something surprising** (flaky test cause, platform quirk, git behavior) → add it to
  Gotchas in `docs/development.md`, phrased as the rule to follow plus why.
- **Made or confirmed a decision with the user** → `docs/decisions.md`, one entry with the reason.
- **Finished, started or discovered a task** → `docs/roadmap.md`: tick it, add it, or note the blocker.
- **Changed a command or a hard rule** → `AGENTS.md`.

If nothing applies, say so in your final message ("docs: no update needed") so the user can see the
check happened.

## How to write

- English, plain and short. Present tense, describing the current state, not the story of how it got
  there. The git log has the story.
- Do not record facts that drift and are cheap to recompute: test counts, line numbers, file sizes,
  exact timings. Point to the command instead (`uv run pytest`).
- Do not duplicate. If two docs need the same fact, one states it and the other links to it.
- Edit in place. Fix a wrong statement where it is; delete what is no longer true instead of adding a
  correction below it.
- When the code and a doc disagree, the working code wins: update the doc, unless the user says
  the code is wrong.
- Keep `AGENTS.md` under about 50 lines. Move detail into `docs/`.
- New doc file only when a topic outgrows its section; add it to the tables in `AGENTS.md` and here.

## Privacy check

Before committing a doc change, scan the diff for: absolute paths under a user's home, hostnames,
non-noreply emails, branch names or output from other repositories. Move any of these to `HANDOFF.md`.
