import { mocks } from "./types.ts";
import type { PageLabel, ScanPage, ScanResponse } from "./types.ts";

export const LABEL_ORDER: readonly PageLabel[] = ["terinfeksi", "waspada", "tidak_dapat_diperiksa", "aman"];

// Label terburuk dulu, lalu skor R menurun. Tidak mengubah array asal.
export function sortPages(pages: readonly ScanPage[]): ScanPage[] {
  return pages.toSorted((a, b) => LABEL_ORDER.indexOf(a.label) - LABEL_ORDER.indexOf(b.label) || b.r_score - a.r_score);
}

// ponytail: domain selalu dibuang karena respons scan tidak punya penanda situs riset/verified; lihat usulan di F2-I2.
export function pagePath(url: string): string {
  const { pathname, search } = new URL(url);
  return pathname + search;
}

function summarize(pages: ScanPage[]): ScanResponse["summary"] {
  const count = (label: PageLabel) => pages.filter((page) => page.label === label).length;
  return { pages: pages.length, terinfeksi: count("terinfeksi"), waspada: count("waspada"), tidak_dapat_diperiksa: count("tidak_dapat_diperiksa") };
}

// Hanya mode mock. `polls` = jumlah polling sebelumnya; scn_running selesai pada polling ke-2. null = tidak ditemukan.
export function mockScan(id: string, polls = 0): ScanResponse | null {
  const done = mocks.scan;
  if (id === done.scan_id) return done;
  if (id === "scn_running") {
    if (polls >= 2) return { ...done, scan_id: id };
    const pages = done.pages.slice(0, 3);
    return { ...done, scan_id: id, status: "running", finished_at: null, summary: summarize(pages), pages };
  }
  if (id === "scn_failed") return { ...done, scan_id: id, status: "failed", summary: summarize([]), pages: [] };
  if (id === "scn_kosong") return { ...done, scan_id: id, summary: summarize([]), pages: [] };
  return null;
}
