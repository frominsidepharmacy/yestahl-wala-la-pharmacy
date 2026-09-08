# Telegram control flow

Use one Activepieces Free Cloud flow. Import/reference `flow_configuration.json`, connect the Telegram Bot **New Update** trigger and GitHub **Trigger Workflow Dispatch** action, then set the repository and `main` ref.

The first router condition must compare the sender ID from either `callback_query.from.id` or `message.from.id` to `TELEGRAM_ALLOWED_USER_ID`. The unauthorized branch records the attempt in run logs and terminates without any GitHub action.

Callback payloads are colon-separated and remain under Telegram's 64-byte limit. `APPROVE` sends the approval hash prefix and artifact run ID to `publish.yml`; that workflow resolves the immutable artifact and recomputes the complete SHA-256 over every slide, caption, and metadata before publishing. `EDIT` uses the `yestahl_edit_state` table for the next natural-language message. `REGENERATE` and `REJECT` are independent routes. `APPROVE ALL` dispatches `publish_all.yml` for the same artifact run.

The flow must be explicitly published in Activepieces after both OAuth connections are authorized.

