import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PentAI Pro",
  description: "Automated penetration testing command center",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html className="dark" lang="en">
      <body className="bg-bg-primary text-text-primary font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
