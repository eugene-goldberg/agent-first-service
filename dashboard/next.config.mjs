/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config, { dev }) => {
    if (dev) {
      // Avoid flaky filesystem cache corruption in local dev sessions.
      config.cache = false;
    }
    return config;
  },
};

export default nextConfig;
