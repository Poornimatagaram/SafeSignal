// Canonical JSON and payload hashing (Scoping Doc 26.13). Must match sentinel_contract (Python) byte for byte;
// verified against schema/examples/hash_vectors.json by test/hash_vectors.test.mjs.
// Uses Web Crypto (browsers and Node 18+), so payloadSha256 is async.

export const SCHEMA_VERSION = "2.0"; // value of `schema_version` inside every payload
export const CONTRACT_VERSION = "2.3"; // release of schema/ as a whole; the service sends it as X-Schema-Version

export function canonical(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  const keys = Object.keys(value).sort(); // code-unit order matches Python for the ASCII keys we use
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
}

export async function payloadSha256(value) {
  const bytes = new TextEncoder().encode(canonical(value));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
