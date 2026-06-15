// corpsite-ui/next.config.ts

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ВАЖНО:
  // Никаких rewrites для /directory/* — UI-роуты обрабатывает Next.js.
  // API same-origin prefix /api проксируется nginx → FastAPI (см. docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md).
};

export default nextConfig;
