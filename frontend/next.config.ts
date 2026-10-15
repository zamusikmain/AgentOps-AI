import type { NextConfig } from 'next';
const config: NextConfig = { distDir: process.env.NEXT_DIST_DIR || '.next', poweredByHeader: false, experimental: { cpus: 1 } };
export default config;
