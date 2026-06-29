import { chromium } from 'playwright';

const OUT = 'C:/Users/91720/AppData/Local/Temp/claude';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  try {
    // Login
    await page.goto('http://localhost:5173');
    await page.waitForSelector('input[type="email"]', { timeout: 15000 });
    await page.fill('input[type="email"]', 'hr@talentsync.local');
    await page.fill('input[type="password"]', 'hr123456');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/01_home.png` });
    console.log('01 Home/Workspace');

    // Paste non-compliant JD into textarea
    const jd = `HR Executive – Recruitment\n\nRequirements:\n- 1–3 years of HR experience\n- Female candidates preferred\n- Age below 28 years\n- Must be unmarried\n- Freshers need not apply.`;
    const ta = await page.$('textarea');
    if (ta) {
      await ta.fill(jd);
      await page.screenshot({ path: `${OUT}/02_jd_pasted.png` });
      console.log('02 JD pasted');

      // Find and click the process button
      const btn = page.locator('button').filter({ hasText: /process|analyze|check jd|normaliz/i }).first();
      if (await btn.count() > 0) {
        await btn.click();
        await page.waitForTimeout(5000);
        await page.screenshot({ path: `${OUT}/03_review_step.png` });
        console.log('03 Review step');
      }
    }

    // Navigate to step 3 Fix
    const step3btn = page.locator('button').filter({ hasText: /3|fix/i }).first();
    if (await step3btn.count() > 0) {
      await step3btn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${OUT}/04_fix_step.png` });
      console.log('04 Fix step');
    }

    // Click Auto-fix card
    const autoFixCard = page.locator('button').filter({ hasText: /auto.fix|auto fix/i }).first();
    if (await autoFixCard.count() > 0) {
      await autoFixCard.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/05_autofix_panel.png` });
      console.log('05 Auto-fix panel');
    }

    // Roles tab
    await page.locator('nav button').filter({ hasText: 'Roles' }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${OUT}/06_roles.png` });
    console.log('06 Roles view');

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: `${OUT}/error_state.png` });
  }

  await browser.close();
})();
