// What the browser's live editor does to a document when it loads it (review M2
// T1/T2, ruling A). The collab process runs the browser's editor headless: the same
// extensions (`editor.mjs`), bound to a fresh Y.Doc the way the browser binds it, that
// then receives the page's state as the browser receives it on joining. Every plugin
// that appends a transaction runs as in the browser (table repair, autolink, ...), and
// the binding writes what they change into the Y.Doc. That change is what the browser
// would send without anyone typing.
//
// ProseMirror needs a DOM for its view; the headless editor drives the editor state
// directly (as the view does: apply, then update the plugin views). Plugin views that
// need a DOM (drag handling, the drop cursor) only react to DOM events and are left out.
import { Editor } from "@tiptap/core";
import { EditorState } from "@tiptap/pm/state";
import * as Y from "yjs";
import { liveExtensions } from "./editor.mjs";

// What the browser's editor holds before the document arrives (Tiptap's empty content).
const PLACEHOLDER = { type: "doc", content: [{ type: "paragraph" }] };
const SERVER = Symbol("server");
const ignore = () => {};
const NO_DOM = { addEventListener: ignore, removeEventListener: ignore, parentElement: null };

/** The headless editor on `client`: its state, plugin views and a dispatch like the
 * browser's view. `mutations` counts the transactions the load guard saw. */
function headless(client) {
  const found = { mutations: 0, invalid: null };
  const editor = new Editor({
    element: null,
    content: PLACEHOLDER,
    extensions: liveExtensions({
      document: client,
      onLoadMutation: () => {
        found.mutations += 1;
        return true; // let it through: the point is to see what the plugins do
      },
    }),
    enableContentCheck: true,
    onContentError: ({ error }) => {
      found.invalid ??= error.message;
    },
  });
  let state = EditorState.create({
    doc: editor.state.doc,
    plugins: editor.extensionManager.plugins,
  });
  const views = [];
  const view = {
    get state() {
      return state;
    },
    dom: NO_DOM,
    root: null,
    editable: true,
    composing: false,
    isDestroyed: false,
    hasFocus: () => false,
    dispatch(transaction) {
      const before = state;
      state = state.apply(transaction);
      for (const pluginView of views) pluginView.update?.(view, before);
    },
  };
  for (const plugin of state.plugins) {
    if (!plugin.spec.view) continue;
    try {
      views.push(plugin.spec.view(view));
    } catch (error) {
      if (!(error instanceof ReferenceError)) throw error; // `window` / `document` missing
    }
  }
  const destroy = () => {
    for (const pluginView of views) pluginView.destroy?.();
    editor.destroy();
  };
  return { view, found, destroy };
}

/**
 * What the browser's editor makes of the Y.Doc when it joins: `{ json, update,
 * mutations, invalid }`. `json` is the document it then shows, `update` the Yjs update
 * it would send (null when it sends none), `mutations` how many local changes the
 * load guard saw, `invalid` the content error that would stop the browser (or null).
 */
export function settle(ydoc) {
  const client = new Y.Doc();
  const updates = [];
  client.on("update", (update, origin) => {
    if (origin !== SERVER) updates.push(update);
  });
  const { view, found, destroy } = headless(client);
  try {
    Y.applyUpdate(client, Y.encodeStateAsUpdate(ydoc), SERVER);
    // The binding writes the plugins' changes into the Y.Doc on the editor's next
    // transaction (in the browser: a cursor, a selection, a focus change).
    view.dispatch(view.state.tr);
    return {
      json: view.state.doc.toJSON(),
      update: updates.length ? Y.mergeUpdates(updates) : null,
      mutations: found.mutations,
      invalid: found.invalid,
    };
  } finally {
    destroy();
    client.destroy();
  }
}
