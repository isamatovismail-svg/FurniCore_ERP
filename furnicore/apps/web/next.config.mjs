/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@furnicore/shared'],
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
