import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  // Note: rewrites() are not supported with output: "export" (static site).
  // The frontend calls the backend directly via NEXT_PUBLIC_API_URL instead.
};

export default nextConfig;
