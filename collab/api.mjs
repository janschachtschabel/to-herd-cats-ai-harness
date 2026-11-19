// The API's internal collab interface (`/internal/collab/*` on the internal port,
// header X-Herd-Internal-Token). The collab process stores nothing itself: it
// authenticates, loads and saves only through these calls, each with the grants the
// API's relay handed it for exactly one page and generation (`Authorization: Bearer
// herd_cg_...` on the connection; plan M9 decision 16). A grant goes into a body or a
// header, never into a URL or a log line. Every call for a page names this instance
// (`instanceId`), saves and checks also the epoch of its binding to the page (plan M9
// decision 17); without an instance (no HERD_COLLAB_ADVERTISE_URL) they name none.

export class ApiUnavailable extends Error {}

const TOKEN_HEADER = "X-Herd-Internal-Token";
const GRANT_HEADER = "X-Herd-Grant";

export class InternalApi {
  /** @param {{ baseUrl: string, token: string, timeoutMs?: number, instanceId?: string | null }} options */
  constructor({ baseUrl, token, timeoutMs = 5000, instanceId = null }) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
    this.timeoutMs = timeoutMs;
    this.instanceId = instanceId;
  }

  /** This instance and the epoch it loaded the page with (both or neither: an API of
   * 1.0.0 answers no epoch). */
  owned(epoch) {
    return this.instanceId && Number.isInteger(epoch)
      ? { instance_id: this.instanceId, epoch }
      : {};
  }

  /** The heartbeat: alive, reached at `url`, maybe draining. */
  announce({ id, url, draining }) {
    return this.call("POST", "/instances", { id, url, draining });
  }

  /** All saved: this instance's pages are free. */
  release(id) {
    return this.call("DELETE", `/instances/${id}`);
  }

  /** `{status, body}`; `ApiUnavailable` when the API cannot be reached or fails (5xx). */
  async call(method, path, body, headers = {}) {
    let response;
    try {
      response = await fetch(`${this.baseUrl}/internal/collab${path}`, {
        method,
        headers: { ...headers, [TOKEN_HEADER]: this.token, "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (error) {
      throw new ApiUnavailable(`internal api unreachable: ${error.name}`);
    }
    if (response.status >= 500) {
      throw new ApiUnavailable(`internal api answered ${response.status}`);
    }
    const text = await response.text();
    let parsed = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }
    return { status: response.status, body: parsed };
  }

  /** Who the connection's grant edits as: `{user, session_ref, generation}`. */
  auth(grant, pageId, generation) {
    const body = { grant, page_id: pageId, generation };
    if (this.instanceId) body.instance_id = this.instanceId;
    return this.call("POST", "/auth", body);
  }

  load(pageId, grant, generation) {
    const query = new URLSearchParams({ generation: String(generation) });
    if (this.instanceId) query.set("instance_id", this.instanceId);
    return this.call("GET", `/pages/${pageId}?${query}`, undefined, { [GRANT_HEADER]: grant });
  }

  save(pageId, { generation, ydoc, contentMd, editorGrants, sessionKey, epoch }) {
    return this.call("PUT", `/pages/${pageId}`, {
      generation,
      ydoc_b64: Buffer.from(ydoc).toString("base64"),
      content_md: contentMd,
      editor_grants: editorGrants,
      session_key: sessionKey,
      ...this.owned(epoch),
    });
  }

  /** The latest state of the page could not be stored as Markdown (counted). */
  unrepresentable(pageId) {
    return this.call("POST", `/pages/${pageId}/unrepresentable`);
  }

  /** A browser's editor changed the document it had just loaded (counted). */
  loadMutation(pageId) {
    return this.call("POST", `/pages/${pageId}/load-mutation`);
  }

  /** Whether the generation and the grants still hold (each one named is extended). */
  check(pageId, grants, generation, unsavedGrants = [], epoch = null) {
    return this.call("POST", `/pages/${pageId}/check`, {
      grants,
      unsaved_grants: unsavedGrants,
      generation,
      ...this.owned(epoch),
    });
  }
}
