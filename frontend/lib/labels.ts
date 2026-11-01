import type { PageLabel, QuickCheckReason, QuickCheckStatus } from "./types.ts";

export const statusLabels = {
  aman: "Aman",
  waspada: "Waspada",
  terinfeksi: "Terinfeksi",
  terindikasi: "Terindikasi",
  tidak_dapat_diperiksa: "Tidak dapat diperiksa",
} satisfies Record<PageLabel | QuickCheckStatus, string>;

export const reasonLabels = {
  konten_judi_tersembunyi: "Ditemukan konten berindikasi judi yang disembunyikan dari pengunjung",
  konten_berbeda_untuk_mesin_pencari: "Isi halaman berbeda untuk mesin pencari dan pengunjung",
  pengalihan_ke_situs_luar: "Pengunjung dialihkan ke situs di luar domain",
  teks_judi_tersamarkan: "Ditemukan teks promosi judi yang disamarkan",
  tautan_keluar_mencurigakan: "Banyak tautan keluar ke domain tidak dikenal",
  situs_memblokir_pemeriksaan: "Situs memblokir pemeriksaan otomatis",
} satisfies Record<QuickCheckReason, string>;

// Kelas warna per label halaman; pasangan token sama dengan kartu Cek Cepat (F2-I1), merah untuk terinfeksi.
export const labelTones = {
  terinfeksi: { chip: "bg-error-bg text-error-ink", bar: "bg-error-ink" },
  waspada: { chip: "bg-warn-bg text-warn-ink", bar: "bg-warn-line" },
  tidak_dapat_diperiksa: { chip: "bg-neutral-bg text-neutral-ink", bar: "bg-neutral-line" },
  aman: { chip: "bg-safe-bg text-safe-ink", bar: "bg-safe-line" },
} satisfies Record<PageLabel, { chip: string; bar: string }>;

const triggerLayers: Record<string, string> = {
  L1: "Beda untuk mesin pencari",
  L2: "Tersembunyi (CSS)",
  L3: "Teks judi",
  L4: "Tautan keluar asing",
};

// "L2:display_none" -> "Tersembunyi (CSS)". L1:blocked bukan cloaking, jadi dipisah. Prefiks tak dikenal -> null.
export function triggerLabel(trigger: string): string | null {
  const [layer, detail] = trigger.split(":", 2);
  if (layer === "L1" && detail === "blocked") return "Pemeriksaan diblokir";
  return triggerLayers[layer] ?? null;
}
