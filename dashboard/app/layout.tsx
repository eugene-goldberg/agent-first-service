import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent-First Services — Live Demo",
  description: "Two agents cooperating through a self-describing API.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
