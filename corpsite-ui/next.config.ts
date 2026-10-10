// corpsite-ui/next.config.ts

import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Keep client assets and navigation tied to the deployed source revision.
  deploymentId: process.env.NEXT_DEPLOYMENT_ID || execFileSync("git", ["rev-parse", "HEAD"], { cwd: projectRoot, encoding: "utf8" }).trim(),
  // Pin app root so Next.js ignores repo-root package-lock.json (ADR-INFRA-004).
  turbopack: {
    root: projectRoot,
  },
  outputFileTracingRoot: projectRoot,
  // Playwright ships native Chromium binaries; keep it external to the Next bundle.
  serverExternalPackages: ["playwright"],
  // ВАЖНО:
  // Никаких rewrites для /directory/* — UI-роуты обрабатывает Next.js.
  // API same-origin prefix /api проксируется nginx → FastAPI (см. docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md).
};

export default nextConfig;
