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

test("About page renders the Forked card after the other cards", async (t) => {
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
  assert.ok(html.includes("Cook from your library with Forked"));
  assert.ok(html.includes("Free to download. Forked Pro is an optional one-time upgrade."));
  assert.ok(html.includes('alt="Download on the App Store"'));
  assert.ok(html.includes('alt="QR code that opens Forked on the App Store"'));
  // Bundled images only: the About page promises no requests beyond those it lists.
  assert.ok(!/src="https?:/.test(html), "About images should be bundled, not loaded from another site.");
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
  // The stylesheets in the order index.css loads them.
  const stylesDir = path.join(WEB_ROOT, "src", "styles");
  const index = await fs.readFile(path.join(stylesDir, "index.css"), "utf8");
  const files = [...index.matchAll(/@import "\.\/([^"]+)";/g)].map((match) => match[1]);
  const styles = (await Promise.all(files.map((file) => fs.readFile(path.join(stylesDir, file), "utf8")))).join("\n");

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
    Math.abs(desktopBoxes.meta.y - desktopBoxes.privacy.y) <= 1,
    "CookDex and Privacy should start on the same row."
  );
  const topRowBottom = Math.max(
    desktopBoxes.links.y + desktopBoxes.links.height,
    desktopBoxes.privacy.y + desktopBoxes.privacy.height
  );
  assert.ok(desktopBoxes.forked.y >= topRowBottom, "The Forked card should sit below the other cards.");
  assert.ok(
    Math.abs(desktopBoxes.forked.x - desktopBoxes.meta.x) <= 1
      && Math.abs(
        desktopBoxes.forked.x + desktopBoxes.forked.width
          - (desktopBoxes.privacy.x + desktopBoxes.privacy.width)
      ) <= 1,
    "The Forked card should span the full width."
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
