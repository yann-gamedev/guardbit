# GuardBit

> Deteksi dini penyusupan judi online pada website instansi publik melalui analisis cloaking dan klasifikasi teks yang tahan obfuskasi.

Tim **Teori Ninja** — Hackathon INCEPTION 2026, subtema 5 *Smart Public Services and Digital Trust*.

<!-- TODO (J21): isi semua bagian bertanda TODO. Hapus komentar ini sebelum tag submission-24h. -->

## Demo

- Aplikasi: TODO (URL Vercel)
- API: TODO (URL backend)
- Video demo (≤ 3 menit): TODO
- Pitch deck: TODO
- Devpost: TODO
- Akun demo untuk juri: dikirim lewat Devpost, tidak ditulis di repo.

## Masalah

TODO: 3–4 kalimat dari proposal (BSSN 2024, Zagi dkk. 2025: median 32,7 jam, 51,7% disembunyikan dengan `display:none`).

## Cara kerja

TODO: diagram arsitektur + tabel L1–L4 dan skor R (lihat `docs/architecture.md`).

## Hasil evaluasi

| Metrik | Target | Hasil | Catatan |
| --- | --- | --- | --- |
| Recall | ≥ 0,90 | TODO | n halaman terinfeksi = TODO |
| Precision | ≥ 0,90 | TODO | |
| False positive halaman bersih | ≤ 5% | TODO | n halaman bersih = TODO |
| Selisih F1 asli vs obfuskasi | ≤ 5 poin | TODO | |
| Waktu deteksi (replay) | ≤ 6 jam | TODO | |

Semua hasil dilaporkan apa adanya, termasuk yang tidak mencapai target.

## Menjalankan secara lokal

TODO: langkah backend (Python + Playwright) dan frontend (Next.js), plus `.env.example`.

## Etika dan batasan

- Nama instansi disamarkan, tautan judol disensor, temuan dilaporkan ke pemilik situs atau IdADX PANDI.
- Mode Riset hanya membaca halaman publik, tanpa login atau eksploitasi, dengan laju rendah dan log audit.
- Cloaking berbasis IP Googlebot tidak dapat dideteksi dari luar.
- Status "Aman" pada Cek Cepat hanya berarti tidak ditemukan indikasi pada halaman yang diperiksa.

## AI Use and Third-Party Declaration

### Pekerjaan sebelum Hacking Day

Sebelum Challenge Brief dirilis, tim hanya menyiapkan riset, proposal, dan dokumen rancangan internal (tidak dipublikasikan di repo). Satu-satunya skrip pra-sprint adalah alat pengumpul data uji `research/snapshot/collect.py` (dibuat dengan bantuan AI), yang bukan bagian dari produk. Seluruh kode produk ditulis selama 24-hour build sprint; lihat commit history.

### Penggunaan AI

| Alat AI | Dipakai untuk | Bagian |
| --- | --- | --- |
| TODO (API LLM) | Fitur produk: penjelasan temuan dan panduan perbaikan | `backend/app/remediation` |

Keputusan deteksi (status Aman/Waspada/Terinfeksi) tidak memakai LLM.

### Dataset

| Dataset | Sumber | Lisensi |
| --- | --- | --- |
| Judi Online (komentar YouTube, 10.230 baris berlabel) | https://www.kaggle.com/datasets/yaemico/judionline | Apache-2.0 |
| Dataset Judol TikTok Komentar (tidak berlabel; TODO: dipakai/tidak) | https://www.kaggle.com/datasets/aginanjar/dataset-judol-tiktok-komentar | GPL-3.0 |
| Judul + abstrak berbahasa Indonesia (negatif) | https://openalex.org | CC0 |
| Snapshot situs temuan | Dikumpulkan tim, dilabeli manual, tidak dipublikasikan | — |

### Library dan layanan pihak ketiga

Dependensi langsung skeleton backend (versi dipin di `backend/requirements.txt`): FastAPI, Uvicorn, SQLAlchemy, Pydantic, pydantic-settings, HTTPX, Playwright, APScheduler, pytest, dan pytest-asyncio. Image Docker: `mcr.microsoft.com/playwright/python:v1.64.1-noble`, dengan paket `playwright==1.64.1`.

Build Docker belum diverifikasi karena Docker CLI belum tersedia. Detektor, crawler, scheduler, dan integrasi LLM belum diimplementasikan; endpoint selain health masih HTTP 501. Test kontrak membaca dokumen internal `docs/plan/prompts/kontrak.md` yang tidak dipublikasikan, sehingga checkout publik belum bisa menjalankan seluruh test tanpa salinan kontrak dari tim.

TODO: lengkapi deklarasi dependensi frontend, model teks, dataset yang benar-benar digunakan, dan layanan deploy setelah ditambahkan.

## Tim

| Nama | Peran |
| --- | --- |
| Christian Bagus Prasetya (ketua) — UPN "Veteran" Jawa Timur | Crawler, L1, L2, L4, penjadwal |
| Loeis Darmawan — UPN "Veteran" Jawa Timur | Normalisasi dan model L3, evaluasi |
| Setiawan Prayogo — Universitas Wijaya Kusuma Surabaya | Dasbor, tingkat akses, deploy, pitch deck |
