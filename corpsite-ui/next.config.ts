// corpsite-ui/next.config.ts

import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Pin Turbopack root to corpsite-ui (avoid picking repo-root package-lock.json).
  turbopack: {
    root: projectRoot,
  },
  // ВАЖНО:
  // Никаких rewrites для /directory/* — UI-роуты обрабатывает Next.js.
  // API same-origin prefix /api проксируется nginx → FastAPI (см. docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md).
};

export default nextConfig;
