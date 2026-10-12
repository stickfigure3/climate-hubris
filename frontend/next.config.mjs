/** @type {import('next').NextConfig} */
const nextConfig = {
  // Fully static: the build output in out/ is uploaded to Amplify Hosting as-is.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
