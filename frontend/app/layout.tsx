import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

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
      <body className="bg-slate-50">
        <header className="border-b border-slate-200 bg-white">
          <a href="/" className="mx-auto flex max-w-5xl items-center px-4 py-3">
            <img
              src="/logo.svg"
              alt="Research Radar"
              width={240}
              height={75}
              className="h-14 w-auto"
            />
          </a>
        </header>
        {children}
      </body>
    </html>
  );
}