import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Nyaya — Indian Law RAG Assistant",
  description:
    "Ask questions about the DPDP Act 2023, RTI Act 2005 and Consumer Protection Act 2019. Answers cite the exact section.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${sourceSerif.variable} h-full antialiased`}
    >
      <body className="flex h-full flex-col font-sans">
        <header className="shrink-0 border-b border-border bg-surface">
          <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="font-serif text-xl font-semibold tracking-tight">Nyaya</span>
              <span className="hidden text-sm text-muted sm:inline">Indian law, with citations</span>
            </Link>
            <nav className="flex gap-1 text-sm">
              <Link href="/" className="rounded-md px-3 py-1.5 hover:bg-accent-soft">
                Ask
              </Link>
              <Link href="/eval" className="rounded-md px-3 py-1.5 hover:bg-accent-soft">
                Evaluation
              </Link>
            </nav>
          </div>
        </header>
        <div className="min-h-0 flex-1">{children}</div>
      </body>
    </html>
  );
}
