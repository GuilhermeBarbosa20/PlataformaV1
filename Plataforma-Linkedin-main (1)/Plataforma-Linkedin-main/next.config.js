/** @type {import('next').NextConfig} */
const nextConfig = {
  // Output standalone for Docker deployment
  output: 'standalone',
  
  // Strict mode for better development experience
  reactStrictMode: true,
  
  // Security headers
  headers: async () => {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ];
  },

  // Image optimization configuration
  images: {
    domains: [
      'snqlekephnijmybflsea.supabase.co', // Supabase storage
      'media.licdn.com', // LinkedIn CDN
      'lh3.googleusercontent.com', // Google profile pictures
    ],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.supabase.co',
        pathname: '/storage/v1/object/public/**',
      },
    ],
  },

  // Environment variable validation
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.npm_package_version || '1.0.0',
  },

  // Webpack configuration for production
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Don't bundle server-only modules on client
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        crypto: false,
      };
    }
    return config;
  },

  // Experimental features
  experimental: {
    // Improve server components performance
    serverComponentsExternalPackages: ['google-auth-library'],
  },

  // Logging configuration
  logging: {
    fetches: {
      fullUrl: process.env.NODE_ENV === 'development',
    },
  },

  // Disable powered by header
  poweredByHeader: false,

  // Compress responses
  compress: true,

  // Generate ETags for caching
  generateEtags: true,
};

module.exports = nextConfig;
