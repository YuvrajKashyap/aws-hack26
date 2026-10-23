# Deadline integration review

Reviewed October 23 against Viswa PR5 head `e4deb74` and Pranav PR6 head `3901460`. Neither branch was overwritten or force-pushed.

## Viswa

Kept the useful opt-in random simulator scenario support from `bdf23da`, while retaining seed 7 as the stable default for existing demonstrations and tests. `Simulator(seed=None)` requests a fresh scenario; `SIM_SEED` can make that opt-in path reproducible. The simulator stays an isolated fictional CRAC experiment, never input to the AI4I classifier.

Deferred the full merge. The branch's notifier would replace the persistent, explicit-opt-in shared outbox with an environment-triggered SNS publish and in-memory deduplication. Its expected-cost card derives probabilities from an unvalidated RUL range; those outputs must not become decision-grade financial or failure estimates. The newer agent crew also needs bounded-tool and offline-path verification. Generated diagnosis caches, work orders, and purchase logs were not imported. These remain on the original PR for follow-up; nothing was deleted.

## Pranav

Reviewed the action reducer/context, action panel, filtering interface, and Vite deployment configuration. Useful patterns include per-component action state, duplicate-kind replacement, explicit scheduling choices, and accessible status announcements. The current contribution is a separate data-center React prototype with static data and in-memory actions, not the validated manufacturing pipeline. It also hardcodes a workshop proxy hostname. A wholesale merge would add a second application without connecting it to the real assessment or persistent ledger.

Kept PR6 open rather than claim backend integration. The primary console now adopts the explicit review-disposition workflow with durable SQLite storage and concurrent-update protection. Pranav's implementation remains available unchanged for a future dedicated frontend migration. No untested dispatch/order buttons were added to the active demo.

The six remediation choices are carried into the active console as proposed follow-ups: technician inspection, inventory verification after diagnosis, work-scope drafting, maintenance-window review, specialist support, and a parts-request review. Selected follow-ups persist with the inspection note. They never claim execution or invent inventory availability. PR8 was also checked: its direction is `main` into `vishwaa`, so it is a branch-sync request, not a new contribution into `main`.

## Primary demo

The coherent demonstration is a manufacturing technician inspecting a synthetic machining-cell observation, evidence, and a simulated review order. The new review-disposition screen records a local simulated acknowledgment, pending inspection, or completed review with an inspection note. It does not certify safety or trigger operational actions. Read the 3D console guide for the presentation sequence.
