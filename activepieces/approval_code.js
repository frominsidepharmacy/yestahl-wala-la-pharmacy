// Paste this entire function into the Activepieces Code step.
// Inputs: update (Telegram trigger output), allowed_user_id.
export const code = async (inputs) => {
  let update = inputs.update;
  for (let attempt = 0; attempt < 3 && typeof update === "string"; attempt += 1) {
    try {
      update = JSON.parse(update);
    } catch (_) {
      update = {};
      break;
    }
  }
  if (!update || typeof update !== "object") update = {};

  const callback = update.callback_query || {};
  const actorId = callback.from?.id ?? update.message?.from?.id ?? "";
  const authorized = String(actorId) === String(inputs.allowed_user_id);
  const raw = String(callback.data || "");
  const parts = raw.split(":");
  const action = parts[0] || "";

  const result = {
    authorized,
    action,
    dispatch_route: "ignore",
    callback_query_id: String(callback.id || ""),
    workflow_inputs: {},
  };
  if (!authorized || action !== "approve" || parts.length !== 5) return result;

  const [, publicationKey, version, contentHash, artifactRunId] = parts;
  if (
    !publicationKey ||
    !/^v\d+$/.test(version) ||
    !/^[a-f0-9]{12}$/i.test(contentHash) ||
    !/^\d+$/.test(artifactRunId)
  ) {
    return result;
  }

  result.dispatch_route = "publish";
  result.workflow_inputs = {
    publication_key: publicationKey,
    content_hash: contentHash,
    artifact_run_id: artifactRunId,
  };
  return result;
};
