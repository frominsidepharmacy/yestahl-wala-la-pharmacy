"""Execute the production JavaScript, without Telegram or GitHub side effects."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_code(update, allowed="123"):
    source = (ROOT / "activepieces/approval_code.js").read_text()
    source += "\nconsole.log(JSON.stringify(await code(" + json.dumps(
        {"update": update, "allowed_user_id": allowed}
    ) + ")));"
    return json.loads(subprocess.check_output(
        ["node", "--input-type=module", "-e", source], text=True
    ))


def callback(key="pharmacy-test"):
    return {"callback_query": {"id": "callback-1", "from": {"id": 123},
            "data": f"approve:{key}:v1:abcdef123456:123456"}}


def test_both_series_and_trigger_shapes():
    for key in ("pharmacy-test", "biz-test"):
        update = callback(key)
        for shaped in (update, json.dumps(update), json.dumps(json.dumps(update)),
                       {"body": update}, {"body": json.dumps(update)}):
            result = run_code(shaped)
            assert result["dispatch_route"] == "publish"
            assert result["callback_query_id"] == "callback-1"
            assert result["workflow_inputs"] == {
                "publication_key": key, "content_hash": "abcdef123456",
                "artifact_run_id": "123456",
            }


def test_fail_closed():
    for update in ({}, None, [], "invalid json", {"body": "invalid"}):
        assert run_code(update)["dispatch_route"] == "ignore"
    for allowed in ("", None, "999"):
        assert run_code(callback(), allowed)["dispatch_route"] == "ignore"
    for data in ("approve:x:v1:bad:123", "reject:x:v1:abcdef123456:123",
                 "approve:x:v1:abcdef123456:123:extra"):
        update = callback()
        update["callback_query"]["data"] = data
        assert run_code(update)["dispatch_route"] == "ignore"
    update = callback()
    del update["callback_query"]["id"]
    assert run_code(update)["dispatch_route"] == "ignore"


def test_normalized_acknowledgement_is_nonblocking():
    spec = json.loads((ROOT / "activepieces/flow_configuration.json").read_text())
    ack = spec["approvalBranch"]["answerCallbackQuery"]
    assert ack["callbackQueryId"] == "{{step_2['callback_query_id']}}"
    assert ack["continueOnFailure"] is True
