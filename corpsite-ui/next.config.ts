// corpsite-ui/next.config.ts

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ВАЖНО:
  // Никаких rewrites для /directory/*
  // UI-роуты (/directory/...) должны обрабатываться Next.js
};

export default nextConfig;
