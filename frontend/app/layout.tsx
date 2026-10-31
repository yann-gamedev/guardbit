import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "GuardBit",
  description: "Deteksi dini penyusupan judi online pada website instansi publik.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body className="bg-white text-slate-900">
        <a href="#konten" className="sr-only focus:not-sr-only">Lewati navigasi</a>
        <header className="border-b p-4">
          <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-6">
            <Link href="/" className="text-xl font-bold">GuardBit</Link>
            <nav aria-label="Navigasi utama" className="flex flex-wrap gap-4">
              <Link href="/" className="underline">Cek Cepat</Link>
              <Link href="/sites" className="underline">Situs Saya</Link>
              <Link href="/login" className="underline">Masuk</Link>
            </nav>
          </div>
        </header>
        <main id="konten" className="mx-auto max-w-4xl space-y-4 p-6">{children}</main>
      </body>
    </html>
  );
}
