import assert from "node:assert/strict";
import test from "node:test";

import { generatePassword, signInAddress, suggestUsername } from "../src/pages/users/people.mjs";

test("sign-in names come from what people type", () => {
  assert.equal(suggestUsername("Sam Lee"), "sam-lee");
  assert.equal(suggestUsername("  Kitchen Tablet!! "), "kitchen-tablet");
  assert.equal(suggestUsername("José"), "jose");
  assert.equal(suggestUsername("a.b_c"), "a.b_c");
});

test("temporary passwords meet the server's rules", () => {
  for (let i = 0; i < 50; i += 1) {
    const password = generatePassword();
    assert.equal(password.length, 14);
    assert.match(password, /[a-z]/);
    assert.match(password, /[A-Z]/);
    assert.match(password, /\d/);
  }
});

test("the sign-in address includes the base path", () => {
  assert.equal(signInAddress({ origin: "https://home.lan:4820" }, "/cookdex/"), "https://home.lan:4820/cookdex");
  assert.equal(signInAddress({ origin: "http://x" }, null), "http://x");
});
