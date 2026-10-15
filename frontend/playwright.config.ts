import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e',workers:1,timeout:180000,reporter:[['./e2e/secret-safe-reporter.ts'],['list']],
  use:{baseURL:'http://127.0.0.1:3011',headless:true,trace:'off',
    launchOptions:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:undefined},
  webServer:[
    {command:process.platform==='win32'?'..\\backend\\.venv\\Scripts\\python.exe ..\\scripts\\e2e-backend.py':'../backend/.venv/bin/python ../scripts/e2e-backend.py',url:'http://127.0.0.1:8011/health',reuseExistingServer:false,timeout:180000},
    {command:'npm run start -- --port 3011',url:'http://127.0.0.1:3011',reuseExistingServer:false,timeout:180000,
      env:{NEXT_DIST_DIR:process.env.NEXT_DIST_DIR||'.next-auth-production',BACKEND_URL:'http://127.0.0.1:8011',API_TOKEN:'e2e-test-token',NEXT_TELEMETRY_DISABLED:'1'}}
  ]
});
