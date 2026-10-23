import type { Metadata } from "next";
import { Inter, Newsreader } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

// Locked type tokens — see /design/brief.md.
// Display serif (Newsreader) for wordmark, titles, abstract.
// Grotesk (Inter) for scanning UI and meta.
const display = Newsreader({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Research Radar",
  description:
    "Search and explore recent research papers in computer vision and large language models.",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${sans.variable} bg-paper font-sans text-ink antialiased`}>
        {children}
      </body>
    </html>
  );
}