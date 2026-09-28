import assert from "node:assert/strict";
import test from "node:test";

import { SECTIONS, sectionOf, sectionStatus, sourceNote } from "../src/pages/settings/sections.mjs";

test("every visible settings group lands in a section", () => {
  for (const group of ["Connection", "AI", "Direct DB", "Dredger", "Updates", "Runner"]) {
    assert.ok(sectionOf(group), group);
  }
  assert.equal(sectionOf("Web UI"), null);
  assert.equal(new Set(SECTIONS.map((s) => s.id)).size, SECTIONS.length);
});

test("Mealie needs both the address and the token", () => {
  assert.equal(sectionStatus("mealie", { MEALIE_URL: { has_value: true } }).tone, "warn");
  assert.equal(sectionStatus("mealie", { MEALIE_URL: { has_value: true }, MEALIE_API_KEY: { has_value: true } }).text, "Set up");
});

test("AI status follows the provider being drafted", () => {
  const specs = { CATEGORIZER_PROVIDER: { value: "chatgpt" }, OPENAI_API_KEY: { has_value: true } };
  assert.deepEqual(sectionStatus("ai", specs), { text: "OpenAI", tone: "ok" });
  assert.deepEqual(sectionStatus("ai", specs, { CATEGORIZER_PROVIDER: "none" }), { text: "Off", tone: "" });
  assert.equal(sectionStatus("ai", specs, { CATEGORIZER_PROVIDER: "anthropic" }).tone, "warn");
});

test("an AI provider nobody chose isn't a warning", () => {
  const untouched = { CATEGORIZER_PROVIDER: { value: "chatgpt", source: "default" } };
  assert.deepEqual(sectionStatus("ai", untouched, { CATEGORIZER_PROVIDER: "chatgpt" }), { text: "Not set up", tone: "" });
  const picked = { CATEGORIZER_PROVIDER: { value: "chatgpt", source: "ui_setting" } };
  assert.equal(sectionStatus("ai", picked, { CATEGORIZER_PROVIDER: "chatgpt" }).tone, "warn");
});

test("the database is optional, so not having one isn't a warning", () => {
  assert.equal(sectionStatus("database", {}).tone, "");
  assert.equal(sectionStatus("database", { MEALIE_DB_URL: { has_value: true } }).text, "Set up");
});

test("source notes only speak up about the compose file or a broken secret", () => {
  assert.equal(sourceNote({ source: "ui_setting" }), "");
  assert.equal(sourceNote({ source: "default" }), "");
  assert.match(sourceNote({ source: "environment" }), /compose file/);
  assert.match(sourceNote({ source: "ui_secret", environment_too: true }), /value here is the one used/);
  assert.match(sourceNote({ source: "ui_secret_invalid" }), /Enter it again/);
});

test("language settings show names, not codes", async () => {
  const { choiceLabel } = await import("../src/pages/settings/sections.mjs");
  assert.equal(choiceLabel("DREDGER_TARGET_LANGUAGE", "de", "en"), "German");
  assert.equal(choiceLabel("DREDGER_TARGET_LANGUAGE", "no", "en"), "Norwegian");
  assert.equal(choiceLabel("DREDGER_TARGET_LANGUAGE", "de", "fr"), "Allemand");
  assert.equal(choiceLabel("MEALIE_DB_TYPE", "postgres", "en"), "postgres");
  assert.equal(choiceLabel("MEALIE_DB_TYPE", "", "en"), "— disabled —");
});
