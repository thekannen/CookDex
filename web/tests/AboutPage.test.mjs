import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");
const APP_STORE_URL = "https://apps.apple.com/us/app/forked-recipes/id6760947117";

test("About page renders the Forked card after the left-column project links", async (t) => {
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
  assert.ok(html.indexOf("CookDex vtest") < html.indexOf("Project Links"));
  assert.ok(
    html.indexOf("Project Links") < html.indexOf("Privacy &amp; Data")
  );
  assert.ok(
    html.indexOf("Privacy &amp; Data") < html.indexOf("Also from Knownframe")
  );
});

test("About cards stay compact at desktop width and fit one column when narrow", async (t) => {
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
  const styles = await fs.readFile(path.join(WEB_ROOT, "src", "styles.css"), "utf8");

  const browser = await chromium.launch({ headless: true });
  t.after(async () => {
    await browser.close();
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  await page.setContent(`
    <!doctype html>
    <html data-theme="dark">
      <head>
        <style>${styles}</style>
        <style>#about-test-shell { width: 1100px; }</style>
      </head>
      <body>
        <main id="about-test-shell">${html}</main>
      </body>
    </html>
  `);

  const card = (heading) =>
    page.locator("article.card").filter({ hasText: heading }).first();
  const desktopBoxes = {
    meta: await card("CookDex vtest").boundingBox(),
    privacy: await card("Privacy & Data").boundingBox(),
    forked: await card("Also from Knownframe").boundingBox(),
    links: await card("Project Links").boundingBox(),
  };
  assert.ok(Object.values(desktopBoxes).every(Boolean), "Every About card should render.");
  assert.ok(
    Math.abs(desktopBoxes.meta.y - desktopBoxes.privacy.y) <= 1
      && Math.abs(desktopBoxes.meta.y - desktopBoxes.forked.y) <= 1,
    "The three desktop columns should start on the same row."
  );
  const leftColumnGap =
    desktopBoxes.links.y - (desktopBoxes.meta.y + desktopBoxes.meta.height);
  assert.ok(
    leftColumnGap >= 12 && leftColumnGap <= 20,
    `Project Links should sit one grid gap below CookDex; received ${leftColumnGap}px.`
  );

  await page.setViewportSize({ width: 740, height: 1200 });
  await page.locator("#about-test-shell").evaluate((element) => {
    element.style.width = "auto";
  });
  const narrowBoxes = await Promise.all([
    card("CookDex vtest").boundingBox(),
    card("Project Links").boundingBox(),
    card("Privacy & Data").boundingBox(),
    card("Also from Knownframe").boundingBox(),
  ]);
  assert.ok(narrowBoxes.every(Boolean), "Every About card should render when narrow.");
  assert.ok(
    narrowBoxes.every((box) => Math.abs(box.x - narrowBoxes[0].x) <= 1),
    "Narrow About cards should share one column."
  );
  assert.ok(
    narrowBoxes.every((box) => box.x + box.width <= 740),
    "Narrow About cards should not overflow the viewport."
  );
});
