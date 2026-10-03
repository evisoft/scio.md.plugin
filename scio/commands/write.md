---
description: Research and propose a sourced Scio article, edit or correction on a topic, one claim per sentence with verified quotes. Use when the user asks to write, create, extend or correct a Scio article.
argument-hint: "<topic or article slug>"
---

First load the `scio` skill if it is not loaded in this conversation; the `references/` files named below are in that skill's folder, so read them from there.

Use the `scio` skill and follow `references/write.md` for the topic given here (if any; otherwise ask): $ARGUMENTS

1. `scio_whoami`: stop with a plain explanation if `propose` is not permitted or no proposal quota is left.
2. `scio_search` the topic. If an article exists, propose an edit to it instead of a duplicate (read it, keep its `base_revision`). If the search returns a gap, follow the gap section: check notability before anything is reserved, reserve the gap only when the work is real, and reserve it again right before proposing.
3. Run the work as the team in `references/team.md` when the host can delegate (Cowork, Claude Code): `scio-researcher` (stop and report if notability fails), then `scio-writer` (draft + claims, no proposing), then `scio-refuter` with lenses precision and weight in parallel (add harm in sensitive domains), then the writer fixes every `unsupported` claim; at most three refute/fix rounds. Without delegation, do the same roles yourself one after another, each in its own round.
4. Verify every source with `scio_verify_source` and the exact quote you cite, and run the hand pre-flight (step 8 of `references/write.md`).
5. Show the person the title, summary, claims with sources, expected quota use and kind. Propose with `scio_propose_edit` only once they agree, with one `idempotency_key` you keep for retries and status checks.
6. Report the proposal id, state, gate results and expected panel time — and what the refuters changed — not how many agents ran. Never call a proposal published before the history shows the merge.
