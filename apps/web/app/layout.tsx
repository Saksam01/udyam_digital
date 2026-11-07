import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Udyam Digital, Accel Business",
  description: "Discover, buy and activate business connectivity in one sitting.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
  appleWebApp: { capable: true, title: "Udyam Digital", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#ED1C24",
};

const FONTS =
  "https://fonts.googleapis.com/css2?family=Anek+Latin:wght@400;500;600;700&family=Anek+Devanagari:wght@400;500;600;700&family=Anek+Tamil:wght@400;500;600;700&family=Anek+Telugu:wght@400;500;600;700&family=Anek+Bangla:wght@400;500;600;700&family=Anek+Kannada:wght@400;500;600;700&family=Anek+Gurmukhi:wght@400;500;600;700&display=swap";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href={FONTS} rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  );
}
