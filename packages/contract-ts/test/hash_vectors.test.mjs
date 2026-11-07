// Run: npm test --prefix packages/contract-ts   (or: node --test "packages/contract-ts/test/*.test.mjs")
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { canonical, payloadSha256 } from "../src/index.js";

const url = new URL("../../../schema/examples/hash_vectors.json", import.meta.url);
const { vectors } = JSON.parse(readFileSync(url, "utf8"));

for (const v of vectors) {
  test(`hash vector: ${v.name}`, async () => {
    assert.equal(canonical(v.input), v.canonical);
    assert.equal(await payloadSha256(v.input), v.sha256);
  });
}
