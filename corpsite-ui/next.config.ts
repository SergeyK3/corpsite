// corpsite-ui/next.config.ts

import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
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
