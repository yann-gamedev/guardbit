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
