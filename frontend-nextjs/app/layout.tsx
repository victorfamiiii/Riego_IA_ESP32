/* eslint-disable @next/next/no-page-custom-font */
import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ServiceWorkerRegistration from "./components/ServiceWorkerRegistration";
import FCMHandler from "./components/FCMHandler";
import TwemojiProvider from "./components/TwemojiProvider";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Sistema de Riego Inteligente - TFG 2025",
  description: "Sistema de riego inteligente con ESP32 y monitoreo en tiempo real de temperatura y humedad",
  generator: "Next.js",
  manifest: "/app/manifest.json",
  keywords: ["riego", "esp32", "iot", "arduino", "agricultura", "temperatura", "humedad"],
  authors: [
    { name: "Victor Feo Galan" },
  ],
  icons: [
    { rel: "apple-touch-icon", url: "/app/apple-touch-icon.png", sizes: "180x180" },
    { rel: "icon", type: "image/png", url: "/app/favicon-32x32.png", sizes: "32x32" },
    { rel: "icon", type: "image/png", url: "/app/favicon-16x16.png", sizes: "16x16" },
    { rel: "icon", type: "image/png", url: "/app/icon-192x192.png", sizes: "192x192" },
    { rel: "icon", type: "image/png", url: "/app/icon-512x512.png", sizes: "512x512" },
  ],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  viewportFit: "cover",
  themeColor: "#4caf50",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={inter.variable}>
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/icon?family=Material+Icons"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Icons+Outlined&display=swap"
        />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Riego IoT" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className={`${inter.className} antialiased`}>
        <ServiceWorkerRegistration />
        <FCMHandler />
        <TwemojiProvider />
        <main>
          {children}
        </main>
      </body>
    </html>
  );
}