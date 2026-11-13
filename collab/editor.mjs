// The live editor as the browser runs it: the schema's extensions (`schema.mjs`), the
// binding to the page's Y.Doc and the load guard. One list for the browser's live
// editor and for the collab process, which runs it headless when a page is opened
// (`settle.mjs`, review M2 T1/T2): no extension that may change the document is
// configured in the browser only. (The browser adds the other people's cursors, which
// only draw decorations.)
//
// The load guard (review M2, ruling B): while the person has not done anything in the
// editor (keyboard, paste, drop, pointer, toolbar), a local change of the shared
// document can only come from a plugin reacting to the document being loaded or to
// someone else's change. Such a change is a defect: it is not applied (so it is never
// synced) and `onLoadMutation(transaction)` is told; it answers whether to let it
// through after all (the collab process's headless editor does, to see what the
// plugins do).
import { Extension } from "@tiptap/core";
import Collaboration from "@tiptap/extension-collaboration";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { SYNC_META, extensions } from "./schema.mjs";

export { SYNC_META };
export const FIELD = "default"; // the Y.XmlFragment of the page's document

// Everything a person does in the editor starts with one of these (captured before the
// editor's own handlers, so a task item's checkbox counts too).
const INPUT_EVENTS = [
  "keydown",
  "beforeinput",
  "compositionstart",
  "paste",
  "drop",
  "cut",
  "pointerdown",
  "mousedown",
  "touchstart",
];

export const loadGuardKey = new PluginKey("herdLoadGuard");

const LoadGuard = Extension.create({
  name: "loadGuard",
  addOptions: () => ({ onLoadMutation: () => false }),
  addStorage: () => ({ input: false }),
  addProseMirrorPlugins() {
    const { storage, options } = this;
    const input = () => {
      storage.input = true;
    };
    return [
      new Plugin({
        key: loadGuardKey,
        view(view) {
          for (const type of INPUT_EVENTS) view.dom.addEventListener(type, input, true);
          return {
            destroy() {
              for (const type of INPUT_EVENTS) view.dom.removeEventListener(type, input, true);
            },
          };
        },
        filterTransaction: (transaction) =>
          storage.input ||
          !transaction.docChanged ||
          transaction.getMeta(SYNC_META) !== undefined ||
          options.onLoadMutation(transaction) === true,
      }),
    ];
  },
});

/** The person did something outside the editor's own surface (a toolbar button). */
export function markInput(editor) {
  editor.storage.loadGuard.input = true;
}

/** Whether the person has done anything in the editor yet. */
export function hadInput(editor) {
  return editor.storage.loadGuard.input === true;
}

/** The live editor's extensions, bound to the Y.Doc's `field`. */
export function liveExtensions({ document, field = FIELD, onLoadMutation = () => false }) {
  return [
    ...extensions(),
    Collaboration.configure({ document, field }),
    LoadGuard.configure({ onLoadMutation }),
  ];
}
