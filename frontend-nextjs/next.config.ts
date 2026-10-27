import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'standalone', // Para Docker
  basePath: '/app',
};

// @ts-expect-error next-pwa has no TypeScript definitions
import withPWAInit from 'next-pwa';

const withPWA = withPWAInit({
  dest: 'public',
  register: true,
  skipWaiting: true,
  clientsClaim: true,
  disable: process.env.NODE_ENV === 'development',
  // Usar nuestro Service Worker personalizado
  sw: 'sw-custom.js',
  // Configuración de cache
  runtimeCaching: [
    {
      urlPattern: /^https:\/\/riegoesp32\.victorfg\.work\/api\/.*/i,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'riego-api-v1',
        expiration: { maxEntries: 50, maxAgeSeconds: 300 },
        networkTimeoutSeconds: 10,
      },
    },
    {
      urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'riego-images-v1',
        expiration: { maxEntries: 60, maxAgeSeconds: 2592000 },
      },
    },
    {
      urlPattern: /\.(?:js|css|woff2?)$/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'riego-static-v1',
        expiration: { maxEntries: 60, maxAgeSeconds: 604800 },
      },
    },
    {
      urlPattern: /\/_next\/static\/.*/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'nextjs-static-v1',
        expiration: { maxEntries: 100, maxAgeSeconds: 604800 },
      },
    },
  ],
});

export default withPWA(nextConfig);
