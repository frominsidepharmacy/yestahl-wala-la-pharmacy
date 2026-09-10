# Activepieces Free Cloud setup

Run `python scripts/configure_activepieces.py` after setting `ACTIVEPIECES_API_KEY`, `ACTIVEPIECES_PROJECT_ID`, `GITHUB_REPOSITORY`, and both connection IDs. The script validates the machine-readable flow specification and prints the exact API request body without secrets. Activepieces connection authorization and final flow publication remain account-owner actions.

The live approval branch must compare `{{step_2['dispatch']}}` with the text `true` using **Exactly matches (Text)**. It must then answer the callback, dispatch `Publish approved carousel (.github/workflows/publish.yml)` with the three values from `step_2.workflow_inputs`, and leave the final permalink confirmation to the publishing workflow. See [`FLOW_SPEC.md`](FLOW_SPEC.md) and [`../docs/PRODUCTION_RUNBOOK.md`](../docs/PRODUCTION_RUNBOOK.md).
