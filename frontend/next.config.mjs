import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    // Pin the workspace root: a stray package-lock.json in the parent
    // directory would otherwise make Turbopack infer A:\Projects.
    root: fileURLToPath(new URL(".", import.meta.url)),
  },
};

export default nextConfig;
