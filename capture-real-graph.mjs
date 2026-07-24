import { chromium } from 'playwright';
import { mkdirSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const IMOVEL_ID = '274';
const SCREENSHOT_PATH = join(homedir(), '.hermes', 'cache', 'screenshots', 'graph-real.png');

mkdirSync(join(homedir(), '.hermes', 'cache', 'screenshots'), { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1400, height: 800 } });

try {
  // Step 1: Login via API to get JWT
  const boot = await context.newPage();
  const { token } = await boot.evaluate(async () => {
    const res = await fetch('http://localhost:8787/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'viewer@cadeia.test', password: 'dev-password' })
    });
    const body = await res.json();
    return { token: body.token };
  });
  await boot.close();
  console.log(`JWT: ${token.slice(0,20)}...`);

  // Step 2: Navigate, inject token, reload
  const page = await context.newPage();
  await page.goto(`http://localhost:5176/graph?imovelId=${IMOVEL_ID}`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(t => window.localStorage.setItem('token', t), token);

  // Log fetch-related console errors
  page.on('console', msg => {
    if (msg.text().includes('401') || msg.text().includes('403') || msg.text().includes('Unauthorized')
        || msg.text().includes('graph') || msg.text().includes('error')) {
      console.log(`[${msg.type()}] ${msg.text().slice(0, 250)}`);
    }
  });

  await page.reload({ waitUntil: 'networkidle' });

  // Wait for nodes
  try {
    await page.waitForSelector('.react-flow__node', { timeout: 15000 });
    console.log('Nodes found!');
  } catch {
    console.log('No nodes — checking state...');
    const html = await page.evaluate(() => document.body.innerText.slice(0, 500));
    console.log('Page text:', html);
  }
  await page.waitForTimeout(2000);

  // DOM counts
  const counts = await page.evaluate(() => ({
    nodes: document.querySelectorAll('.react-flow__node').length,
    edges: document.querySelectorAll('.react-flow__edge').length,
  }));
  console.log(`DOM: ${counts.nodes} nodes, ${counts.edges} edges`);

  // Hide chrome
  await page.evaluate(() => {
    document.querySelectorAll('.react-flow__controls, .react-flow__minimap, a[href*="reactflow"], .react-flow__attribution')
      .forEach(el => el.style.display = 'none');
  });

  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: false });
  console.log(`Screenshot: ${SCREENSHOT_PATH}`);
} finally {
  await browser.close();
}
