import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");
const APP_STORE_URL = "https://apps.apple.com/us/app/forked-recipes/id6760947117";

test("About page renders the Forked card between privacy and project links", async (t) => {
  globalThis.window = {
    location: { hostname: "localhost", pathname: "/cookdex/about" },
  };
  t.after(() => {
    delete globalThis.window;
  });

  const vite = await createServer({
    root: WEB_ROOT,
    server: { middlewareMode: true },
    appType: "custom",
    logLevel: "silent",
  });
  t.after(async () => {
    await vite.close();
  });

  const { default: AboutPage } = await vite.ssrLoadModule(
    "/src/pages/about/AboutPage.jsx"
  );
  const html = renderToStaticMarkup(
    React.createElement(AboutPage, {
      aboutMeta: { app_version: "test" },
      healthMeta: { ok: true },
      lastLoadedAt: "",
    })
  );

  assert.ok(html.includes("Also from Knownframe"));
  assert.ok(html.includes("<strong>Forked</strong>"));
  assert.ok(html.includes("Swipe-based discovery, dietary filtering, meal plans"));
  assert.ok(html.includes("Free on the App Store."));
  assert.ok(html.includes("View on the App Store"));
  assert.ok(html.includes(`href="${APP_STORE_URL}"`));
  assert.ok(html.includes('target="_blank"'));
  assert.ok(html.includes('rel="noreferrer"'));
  assert.ok(
    html.indexOf("Privacy &amp; Data") < html.indexOf("Also from Knownframe")
  );
  assert.ok(html.indexOf("Also from Knownframe") < html.indexOf("Project Links"));
});
