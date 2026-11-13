// The API's internal collab interface (`/internal/collab/*` on the internal port,
// header X-Herd-Internal-Token). The collab process stores nothing itself: it
// authenticates, loads and saves only through these calls.

export class ApiUnavailable extends Error {}

const TOKEN_HEADER = "X-Herd-Internal-Token";

export class InternalApi {
  /** @param {{ baseUrl: string, token: string, timeoutMs?: number }} options */
  constructor({ baseUrl, token, timeoutMs = 5000 }) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
    this.timeoutMs = timeoutMs;
  }

  /** `{status, body}`; `ApiUnavailable` when the API cannot be reached or fails (5xx). */
  async call(method, path, body) {
    let response;
    try {
      response = await fetch(`${this.baseUrl}/internal/collab${path}`, {
        method,
        headers: { [TOKEN_HEADER]: this.token, "Content-Type": "application/json" },
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

  auth(sessionToken, pageId) {
    return this.call("POST", "/auth", { session_token: sessionToken, page_id: pageId });
  }

  load(pageId, sessionId, generation) {
    const query = new URLSearchParams({ session_id: sessionId, generation: String(generation) });
    return this.call("GET", `/pages/${pageId}?${query}`);
  }

  save(pageId, { generation, ydoc, contentMd, editorSessionIds, sessionKey }) {
    return this.call("PUT", `/pages/${pageId}`, {
      generation,
      ydoc_b64: Buffer.from(ydoc).toString("base64"),
      content_md: contentMd,
      editor_session_ids: editorSessionIds,
      session_key: sessionKey,
    });
  }

  /** The latest state of the page could not be stored as Markdown (counted). */
  unrepresentable(pageId) {
    return this.call("POST", `/pages/${pageId}/unrepresentable`);
  }

  check(pageId, sessionIds, generation, unsavedSessionIds = []) {
    return this.call("POST", `/pages/${pageId}/check`, {
      session_ids: sessionIds,
      unsaved_session_ids: unsavedSessionIds,
      generation,
    });
  }
}
