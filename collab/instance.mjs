// This process as one of several collab instances (plan M9 decision 17). It picks an
// id at start and announces itself to the API every 5 s with the address the relay
// reaches it at (HERD_COLLAB_ADVERTISE_URL); the API binds each page to one instance
// and sends every connection of the page there. Silent for 15 s, an instance counts
// as gone and its pages go to others.
//
// Stopping (SIGTERM) drains: the instance announces itself draining (it gets no new
// pages), saves what is unsaved and closes its connections (`server.mjs`), then
// releases its pages so that the browsers, reconnecting, land on another instance at
// once. The heartbeat stops before the release, so none brings the instance back.
import { ApiUnavailable } from "./api.mjs";

export const HEARTBEAT_MS = 5000;

export function announcer({ api, id, url, intervalMs = HEARTBEAT_MS, log = () => {} }) {
  let timer = null;
  let beating = Promise.resolve();
  let failing = false;

  async function announce(draining) {
    try {
      const answer = await api.announce({ id, url, draining });
      if (answer.status !== 204) throw new ApiUnavailable(`answered ${answer.status}`);
      if (failing) log("collab instance announced again", { instance_id: id });
      failing = false;
    } catch (error) {
      if (!(error instanceof ApiUnavailable)) throw error;
      if (!failing) log("collab instance announcement failed", { instance_id: id });
      failing = true;
    }
  }

  function beat() {
    beating = announce(false);
    return beating;
  }

  return {
    start() {
      beat();
      timer = setInterval(beat, intervalMs);
      timer.unref();
    },
    /** No new pages from now on (the last word on this instance's state). */
    async drain() {
      clearInterval(timer);
      await beating;
      await announce(true);
    },
    /** Everything is saved: the instance's pages are free for others. */
    async release() {
      try {
        await api.release(id);
      } catch (error) {
        if (!(error instanceof ApiUnavailable)) throw error;
        // The bindings run out by themselves (the instance stops beating).
        log("collab instance release failed", { instance_id: id });
      }
    },
  };
}
