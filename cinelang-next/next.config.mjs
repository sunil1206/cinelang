/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
      { protocol: 'https', hostname: 'img.opensubtitles.com' },
    ],
  },

  // Dev-only rewrite: proxy /api/ to local FastAPI so the browser never hits
  // localhost:8000 directly. In production, Nginx handles this routing.
  ...(process.env.NODE_ENV === 'development' && {
    async rewrites() {
      const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
      return [
        // FastAPI routes (skip NextAuth paths which are handled by Next.js)
        {
          source: '/api/:path((?!auth(?:/|$)).*)',
          destination: `${backendUrl}/api/:path`,
        },
      ]
    },
  }),
}

export default nextConfig
