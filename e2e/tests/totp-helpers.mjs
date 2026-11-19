// The second factor (plan M9 task 16): an authenticator app in Node (RFC 6238 on
// `crypto`'s HMAC-SHA1, 6 digits, 30-second steps) and TOTP set up through the API.
// The app checks codes against the wall clock (not the e2e clock), so do these.
import { createHmac } from "node:crypto";
import { call } from "./helpers.mjs";

const STEP_SECONDS = 30;
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function base32(secret) {
  let bits = "";
  for (const char of secret.replace(/[\s=]/g, "").toUpperCase()) {
    bits += ALPHABET.indexOf(char).toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let at = 0; at + 8 <= bits.length; at += 8) bytes.push(parseInt(bits.slice(at, at + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 4226's HOTP of one counter (RFC 6238: the counter is the time step). */
export function hotp(secret, counter) {
  const message = Buffer.alloc(8);
  message.writeBigUInt64BE(BigInt(counter));
  const mac = createHmac("sha1", base32(secret)).update(message).digest();
  const offset = mac[mac.length - 1] & 0x0f;
  return String((mac.readUInt32BE(offset) & 0x7fffffff) % 10 ** 6).padStart(6, "0");
}

const stepNow = () => Math.floor(Date.now() / 1000 / STEP_SECONDS);

/** One person's app: each code is for a step newer than the last one used (the app
 *  takes a step once), the current one or the next (the app accepts one step either
 *  side); when both are used up it waits for the clock to reach a new step. */
export class Authenticator {
  constructor(secret) {
    this.secret = secret;
    this.last = -1;
  }

  async code() {
    for (;;) {
      const current = stepNow();
      const step = Math.max(current, this.last + 1);
      if (step <= current + 1) {
        this.last = step;
        return hotp(this.secret, step);
      }
      // Waiting for the wall clock to pass a step boundary, not for the app.
      const next = (current + 1) * STEP_SECONDS * 1000;
      await new Promise((resolve) => setTimeout(resolve, next - Date.now() + 50));
    }
  }
}

/** Sets TOTP up for the signed-in context through the API: its app and recovery codes. */
export async function enrollTotp(context, password) {
  const setup = await call(context, "POST", "/api/auth/me/totp/setup", { password });
  const app = new Authenticator(setup.secret);
  const confirmed = await call(context, "POST", "/api/auth/me/totp/confirm", {
    code: await app.code(),
  });
  return { app, recoveryCodes: confirmed.recovery_codes };
}
