# Activepieces Free Cloud setup

`python scripts/configure_activepieces.py` prints a proposed configuration only. It does not deploy, validate against the live Activepieces API schema, or publish a flow. Treat `flow_configuration.json` as a setup specification, not an importable native flow export. Activepieces connection authorization and final flow publication remain account-owner actions.

The live approval branch must compare `{{step_2['dispatch_route']}}` with the literal text `publish` using **Exactly matches (Text)**. It must then answer the callback, dispatch `Publish approved carousel (.github/workflows/publish.yml)` with the three values from `step_2.workflow_inputs`, and leave the final permalink confirmation to the publishing workflow. A Boolean router is forbidden because it failed through Activepieces coercion in production. See [`FLOW_SPEC.md`](FLOW_SPEC.md) and [`../docs/PRODUCTION_RUNBOOK.md`](../docs/PRODUCTION_RUNBOOK.md).

Use [`approval_code.js`](approval_code.js) as the complete Code step implementation. This keeps parsing, authorization, and the text route deterministic instead of relying on UI coercion.

## Apply the approval repair to the existing flow

1. Replace the Code step with `approval_code.js`; keep the configured authorized user ID and map the whole trigger to `update`.
2. Keep the text router comparison to `publish`.
3. Set Answer Callback Query ID to `{{step_2['callback_query_id']}}`, and enable Continue on failure on that acknowledgement step only. Do not enable it on the GitHub dispatch step.
4. Keep the three dispatch inputs from `step_2.workflow_inputs` and `publish.yml` on `main`.
5. Publish the updated existing flow. A repository commit does not update Activepieces.

Local regression tests: `python -m pytest tests/test_activepieces_runtime.py -q` (requires Node.js). These execute the parser but never contact Telegram, GitHub, or Instagram. They are not proof of live deployment or end-to-end publication. Do not replay old approvals or press a production approval button as a diagnostic without explicit publication authorization.
