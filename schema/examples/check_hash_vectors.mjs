// Reference canonical-JSON hash for JavaScript/TypeScript layers (Scoping Doc 26.13).
// Run: node schema/examples/check_hash_vectors.mjs   — exits non-zero on any mismatch.
// Copy canonical() and payloadSha256() into the doctor web app; in the browser use crypto.subtle.digest.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

export function canonical(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  const keys = Object.keys(value).sort(); // code-unit order matches Python for the ASCII keys we use
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
}

export function payloadSha256(value) {
  return createHash("sha256").update(Buffer.from(canonical(value), "utf8")).digest("hex");
}

const { vectors } = JSON.parse(readFileSync(new URL("./hash_vectors.json", import.meta.url), "utf8"));
let failed = 0;
for (const v of vectors) {
  const c = canonical(v.input);
  const h = payloadSha256(v.input);
  const ok = c === v.canonical && h === v.sha256;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"} ${v.name}`);
}
process.exit(failed ? 1 : 0);
