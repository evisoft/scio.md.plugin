---
description: Find and do open Scio tasks the connected agent may take — reported errors to fix, missing or requested articles, corrections to carry into translations. Use when the user asks for Scio work, tasks or what they can contribute.
argument-hint: "[kinds, e.g. small_edit,write_gap,propagation] [--lang <bcp47>]"
---

First load the `scio` skill if it is not loaded in this conversation; the `references/` files named below are in that skill's folder, so read them from there.

Use the `scio` skill. Arguments (if any): $ARGUMENTS

1. `scio_whoami` — stop with a plain explanation if nothing in `permissions` allows contribution. If seats are assigned, mention them first (they have deadlines; `/scio-knowledge:review`).
2. `scio_get_tasks` with `kinds` from the arguments (or all) and, if `--lang` is given, `lang` — the first call of the hour freezes that hour's sample of at most five tasks, so give the kinds and language on that first call (without `lang`, gaps and propagations come in English). It is a sample, not a list; skipping a task costs nothing. Act on each task's `ref_id` (the ticket, gap, panel or propagation it names), never on its `task_id`.
3. Show the person the tasks with what each needs and pays, and do only the ones they choose, at most three this session, highest impact first, following the skill's references: `small_edit` and `propagation` → `references/maintain.md` (a reported error uses `mission_id` = the task's `ref_id`); `write_gap` → the gap section of `references/write.md`; `translate` → `references/translate.md`; `panel_seat` or `audit` → `references/review.md`.
4. Before each proposal, show the draft and its sources and get the person's go-ahead.
5. Report one line per task done: id, kind, outcome, points. A daily `quota_exceeded` ends the session's tasks — say what ran out and when it resets; `quota: points` never resets with time — say so and offer to review instead.
