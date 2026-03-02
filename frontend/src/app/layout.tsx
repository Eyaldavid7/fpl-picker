import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/lib/providers";
import Navigation from "@/components/Navigation";

export const metadata: Metadata = {
  title: "FPL Team Picker",
  description:
    "ML-powered Fantasy Premier League assistant for optimal squad selection, transfer planning, and chip strategy",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">
        <Providers>
          {/* Navigation header */}
          <Navigation />

          {/* Main content */}
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>

          {/* Footer */}
          <footer className="border-t border-[var(--border)] py-4 text-center text-xs text-[var(--muted-foreground)]">
            <p>
              FPL Team Picker - Not affiliated with the official Fantasy Premier
              League
            </p>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
