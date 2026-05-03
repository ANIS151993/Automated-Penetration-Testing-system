import type { Metadata } from "next";
import dynamic from "next/dynamic";
import "./globals.css";

const ChatWidget = dynamic(() => import("@/components/chat-widget"), { ssr: false });

export const metadata: Metadata = {
  title: "PentAI Pro",
  description: "LLM-powered automated penetration testing platform — by Md Anisur Rahman Chowdhury, Gannon University",
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
        <ChatWidget />
        <footer className="border-t border-border-subtle bg-surface-secondary py-3 px-6 flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[9px] text-text-tertiary uppercase tracking-widest">
            © 2026{" "}
            <a
              href="https://marcbd.site"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:text-text-primary transition-colors"
            >
              Md Anisur Rahman Chowdhury
            </a>
          </p>
          <div className="flex items-center gap-4">
            <a href="https://github.com/ANIS151993" target="_blank" rel="noopener noreferrer"
              className="font-mono text-[9px] text-text-tertiary hover:text-primary uppercase tracking-wider transition-colors">
              GitHub
            </a>
            <a href="https://linkedin.com/in/md-anisur-rahman-chowdhury-15862420a" target="_blank" rel="noopener noreferrer"
              className="font-mono text-[9px] text-text-tertiary hover:text-primary uppercase tracking-wider transition-colors">
              LinkedIn
            </a>
            <a href="https://marcbd.site" target="_blank" rel="noopener noreferrer"
              className="font-mono text-[9px] text-text-tertiary hover:text-primary uppercase tracking-wider transition-colors">
              Portfolio
            </a>
            <span className="font-mono text-[9px] text-text-tertiary uppercase tracking-wider">
              v4.2.0
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
