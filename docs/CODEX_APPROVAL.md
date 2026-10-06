# Codex approval channel — active from 2026-10-06

This supersedes Telegram approval instructions in the older runbook. The two scheduled preview workflows still prepare one immutable artifact per series at 20:00 Dubai, but send nothing to Telegram. `previewed.json` now means released into the review queue, not displayed to the human.

Each artifact contains `codex_review.json` with the exact account, publication key, full content hash and originating run ID. Artifact retention is 90 days. Codex downloads and verifies the artifact, displays all three slides and the complete caption in this conversation, and records the request as shown to avoid repeated notifications. Previously released Telegram artifacts remain unapproved unless the user explicitly selects them here.

Only an explicit human approval of the displayed version permits dispatch of `publish.yml`, with `approval_source=codex` and the exact three identity fields from that review request. Never infer approval from a heartbeat, a successful QC report, silence, or approval of another carousel. Any changed image, caption or metadata requires a new review and approval.

The approval_source field is routing protection against the old Activepieces mapping, not authentication: authorized GitHub operators can dispatch workflows. Existing Telegram dispatches omit it and cannot execute either publishing job. Disable the old Activepieces flow in its UI when available; its deployment is outside this repository.

After dispatch, wait for completion, check the returned media ID/permalink and report the Instagram link in Codex. Preserve account isolation and the existing content-hash and duplicate-publication checks. Never dispatch publish_all for an ordinary individual approval.

Codex review delivery depends on the local task being able to run and on usage availability; 20:00 is the GitHub queue time, not a guarantee of an immediate Codex notification.
