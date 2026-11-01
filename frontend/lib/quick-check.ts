import type { QuickCheckStatus } from "./types.ts";

export const EXAMPLE_URL = "https://kampus-anda.ac.id";

// Mengembalikan pesan error Bahasa Indonesia, atau null jika URL layak dikirim.
export function urlError(raw: string): string | null {
  const value = raw.trim();
  if (!value) return "Masukkan alamat situs yang ingin diperiksa.";
  if (!/^https?:\/\//i.test(value)) return "Awali alamat dengan http:// atau https://.";
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return `Alamat tidak valid. Contoh: ${EXAMPLE_URL}`;
  }
  if (url.username || url.password) return "Alamat tidak boleh memuat nama pengguna atau kata sandi.";
  if (!/^([a-z0-9-]+\.)+[a-z0-9-]+$/.test(url.hostname)) return `Nama domain belum lengkap. Contoh: ${EXAMPLE_URL}`;
  return null;
}

// Hanya untuk mode mock: memilih fixture dari kata pada URL.
export function pickScenario(url: string): QuickCheckStatus {
  const value = url.toLowerCase();
  if (value.includes("aman")) return "aman";
  if (value.includes("blokir")) return "tidak_dapat_diperiksa";
  return "terindikasi";
}
