import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
test('update banner renders, dismisses, and returns for a newer version', async t => {
  const dir = await fs.mkdtemp(path.join(root, '.banner-test-'));
  t.after(() => fs.rm(dir, {recursive: true, force: true}));
  await fs.writeFile(path.join(dir, 'entry.jsx'), `
    import React from 'react';
    import {createRoot} from 'react-dom/client';
    import UpdateNotice from '../src/components/UpdateNotice.jsx';
    const root = createRoot(document.getElementById('root'));
    window.renderVersion = latest => root.render(<UpdateNotice status={{latest, update_available:true,
      release_url:'https://github.com/thekannen/CookDex/releases/tag/v'+latest}} />);
    window.renderVersion('2026.10.0');
  `);
  const vite = await createServer({root, logLevel:'silent', server:{host:'127.0.0.1',port:0}, optimizeDeps:{include:['react','react-dom/client']},
    plugins:[{name:'banner-test', configureServer(server) {
      server.middlewares.use('/__banner-test', (req,res) => {
        res.setHeader('Content-Type','text/html');
        res.end(`<html><body><div id="root"></div><script type="module" src="/${path.basename(dir)}/entry.jsx"></script></body></html>`);
      });
    }}]});
  await vite.listen();
  t.after(() => vite.close());
  const browser = await chromium.launch({headless:true});
  t.after(() => browser.close());
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${vite.httpServer.address().port}/__banner-test`);
  await page.getByRole('button', {name:'Dismiss update notice'}).waitFor({timeout:30000}).catch(error => { throw new Error(errors.join('\n') || error.message); });
  assert.match(await page.getByRole('status').innerText(), /2026.10.0/);
  await page.getByRole('button', {name:'Dismiss update notice'}).click();
  await page.getByRole('status').waitFor({state:'detached'});
  await page.reload();
  await page.waitForFunction(() => typeof window.renderVersion === 'function');
  assert.equal(await page.getByRole('status').count(), 0);
  await page.evaluate(() => window.renderVersion('2026.11.0'));
  await page.getByRole('status').waitFor();
  assert.match(await page.getByRole('status').innerText(), /2026.11.0/);
  assert.deepEqual(errors, []);
});
