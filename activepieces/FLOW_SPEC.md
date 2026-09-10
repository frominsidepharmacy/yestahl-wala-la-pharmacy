# Telegram control flow

Use one Activepieces Free Cloud flow. Import/reference `flow_configuration.json`, connect the Telegram Bot **New Update** trigger and GitHub **Trigger Workflow Dispatch** action, then set the repository and `main` ref.

The Code step must compare the sender ID from either `callback_query.from.id` or `message.from.id` to `TELEGRAM_ALLOWED_USER_ID`. The unauthorized branch records the attempt in run logs and terminates without any GitHub action.

Callback payloads are colon-separated and remain under Telegram's 64-byte limit. `APPROVE` sends the approval hash prefix and artifact run ID to `publish.yml`; that workflow resolves the immutable artifact and recomputes the complete SHA-256 over every slide, caption, and metadata before publishing. `EDIT` uses the `yestahl_edit_state` table for the next natural-language message. `REGENERATE` and `REJECT` are independent routes. `APPROVE ALL` dispatches `publish_all.yml` for the same artifact run.

The flow must be explicitly published in Activepieces after both OAuth connections are authorized.

## Production approval branch

The published flow order is:

1. Telegram Bot — New Update.
2. Code — parse an object or repeatedly JSON-decode a string, authorize the sender, and parse callback data.
3. Router — `{{step_2['dispatch']}}` **Exactly matches (Text)** `true`. Do not use **Is true (Boolean)**; Activepieces presents this Code output as text in the Router.
4. Telegram Bot — Answer Callback Query using `{{trigger['callback_query']['id']}}` with: `⏳ تم استلام موافقتك وبدأ النشر… سيصلك رابط البوست هنا بعد النجاح.`
5. GitHub — Trigger Workflow Dispatch for `Publish approved carousel (.github/workflows/publish.yml)` on `main`.

Workflow input mappings are:

- `publication_key`: `{{step_2['workflow_inputs']['publication_key']}}`
- `content_hash`: `{{step_2['workflow_inputs']['content_hash']}}`
- `artifact_run_id`: `{{step_2['workflow_inputs']['artifact_run_id']}}`

Never dispatch `telegram_control.yml` from the approval branch; that workflow receives callbacks and would loop instead of publishing. A successful Code step alone is not proof of publication: confirm the Router true branch, GitHub run, Meta permalink, and final Telegram confirmation.
