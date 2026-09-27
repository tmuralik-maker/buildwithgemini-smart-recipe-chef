const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  console.log('Starting Playwright browser...');
  const outputDir = path.join(__dirname, 'demo_recordings');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: {
      dir: outputDir,
      size: { width: 1280, height: 720 }
    }
  });

  const page = await context.newPage();
  console.log('Navigating to http://localhost:8080...');
  await page.goto('http://localhost:8080/');
  await page.waitForTimeout(2500);

  // Demo Step 1: Click example prompt chip (Primary domain feature: Search pasta recipes)
  console.log('Executing Step 1: Click example prompt button...');
  const exampleBtn = await page.$('.example-btn[data-prompt*="Search"]');
  if (exampleBtn) {
    await exampleBtn.click();
  } else {
    await page.fill('#input', 'Search for easy Italian pasta recipes');
    await page.click('button.send-btn');
  }

  // Wait for first response
  console.log('Waiting for Step 1 agent response...');
  await page.waitForFunction(() => {
    const msgs = document.querySelectorAll('.msg.agent');
    if (msgs.length === 0) return false;
    const last = msgs[msgs.length - 1];
    return !last.classList.contains('loading') && !last.textContent.includes('cooking up');
  }, { timeout: 60000 });

  console.log('Step 1 complete. Pausing for 6 seconds to display recipe results...');
  await page.waitForTimeout(6000);

  // Demo Step 2: Richer prompt with tool call & generated image
  console.log('Executing Step 2: Rich prompt with image generation tool call...');
  await page.fill('#input', 'Generate a realistic dish image of a freshly cooked bowl of creamy Spaghetti Carbonara');
  await page.waitForTimeout(1000);
  await page.click('button.send-btn');

  // Wait for second response
  console.log('Waiting for Step 2 agent response with generated image tool call...');
  await page.waitForFunction(() => {
    const msgs = document.querySelectorAll('.msg.agent');
    if (msgs.length < 2) return false;
    const last = msgs[msgs.length - 1];
    return !last.classList.contains('loading') && !last.textContent.includes('cooking up');
  }, { timeout: 90000 });

  console.log('Step 2 complete. Pausing for 6 seconds to display generated image...');
  await page.waitForTimeout(6000);

  const videoPage = page.video();
  await context.close();
  await browser.close();

  if (videoPage) {
    const videoPath = await videoPage.path();
    console.log('DEMO_VIDEO_RECORDED_AT:', videoPath);

    // Copy recorded video to artifacts directory so it can be embedded cleanly
    const artifactDir = '/config/.gemini/antigravity/brain/a7c1523d-2afc-484f-83d0-d1724f980e93';
    const destPath = path.join(artifactDir, 'smart_recipe_chef_demo.webm');
    fs.copyFileSync(videoPath, destPath);
    console.log('COPIED_TO_ARTIFACT:', destPath);
  } else {
    console.log('Video recording finished.');
  }
})();
