import type { Metadata } from "next";
import { Overpass, IBM_Plex_Mono } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

const sans = Overpass({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Research Radar",
  description:
    "Search and explore recent research papers in computer vision and large language models.",
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${sans.variable} ${mono.variable} grid-bg bg-deep font-sans text-ice antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
