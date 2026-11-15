// The API's internal collab interface (`/internal/collab/*` on the internal port,
// header X-Herd-Internal-Token). The collab process stores nothing itself: it
// authenticates, loads and saves only through these calls, each with the grants the
// API's relay handed it for exactly one page and generation (`Authorization: Bearer
// herd_cg_...` on the connection; plan M9 decision 16). A grant goes into a body or a
// header, never into a URL or a log line.

export class ApiUnavailable extends Error {}

const TOKEN_HEADER = "X-Herd-Internal-Token";
const GRANT_HEADER = "X-Herd-Grant";

export class InternalApi {
  /** @param {{ baseUrl: string, token: string, timeoutMs?: number }} options */
  constructor({ baseUrl, token, timeoutMs = 5000 }) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
    this.timeoutMs = timeoutMs;
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
    return this.call("POST", "/auth", { grant, page_id: pageId, generation });
  }

  load(pageId, grant, generation) {
    const query = new URLSearchParams({ generation: String(generation) });
    return this.call("GET", `/pages/${pageId}?${query}`, undefined, { [GRANT_HEADER]: grant });
  }

  save(pageId, { generation, ydoc, contentMd, editorGrants, sessionKey }) {
    return this.call("PUT", `/pages/${pageId}`, {
      generation,
      ydoc_b64: Buffer.from(ydoc).toString("base64"),
      content_md: contentMd,
      editor_grants: editorGrants,
      session_key: sessionKey,
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
  check(pageId, grants, generation, unsavedGrants = []) {
    return this.call("POST", `/pages/${pageId}/check`, {
      grants,
      unsaved_grants: unsavedGrants,
      generation,
    });
  }
}
