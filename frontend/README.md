# GuardBit — skeleton frontend F1-I1

Next.js App Router, TypeScript strict, Tailwind CSS. Halaman `/` (Cek Cepat, F2-I1) sudah interaktif; empat route lain masih placeholder berbahasa Indonesia, belum ada login atau tampilan bukti.

Cek Cepat saat mock aktif: URL berisi `aman` → Aman, `blokir` → Tidak dapat diperiksa, lainnya → Terindikasi, dengan jeda 1,5 detik. Validasi URL ada di `lib/quick-check.ts`.

## Lokal

Gunakan Node.js 22.13+ (Vercel: Node.js 22.x).

```sh
npm ci
npm run dev
```

Buka `/`, `/scan/scn_01`, `/finding/fnd_12`, `/login`, `/sites` pada `http://localhost:3000`.

```sh
npm test
npm run build
npm run typecheck
# Dengan server dev/start masih berjalan:
npm run test:routes
```

`npm run build` menjalankan test lebih dahulu, termasuk validasi keenam JSON. Tes route memakai HTTP dan memeriksa status 200, judul, header, bahasa; bukan uji interaksi browser.

## Kontrak dan API

Sumber kebenaran: `docs/plan/prompts/kontrak.md` di root repo. `lib/types.ts` memakai skema Zod strict dan tipe `z.infer`, termasuk union literal status/label/reason. Enam mock diimpor di sana dan diparse tanpa cast `as` yang menyembunyikan kesalahan enum JSON. Validasi runtime juga menolak field tambahan, skor di luar 0–1, dan waktu tanpa zona +07:00. TypeScript sendiri tidak memvalidasi isi JSON saat runtime; test/prebuild menjadi gate fixture.

`lib/api.ts` mengekspor `getHealth`, `quickCheck`, `createSite`, `verifySite`, `startScan`, `getScan`, `getFinding`, `getRemediation`, `getAuditLog`. Default `NEXT_PUBLIC_USE_MOCKS=true`, tanpa request jaringan. `quickCheck({ url }, "aman" | "terindikasi" | "tidak_dapat_diperiksa")` memilih skenario fixture; argumen kedua tidak dikirim ke API nyata. Default skenario `terindikasi`.

`sites.json` adalah objek respons **POST /sites**, bukan daftar dari endpoint rekaan GET /sites. Kontrak belum mengatur login atau daftar situs. Detail mock tersedia untuk `scn_01` dan `fnd_12`; ID lain menghasilkan `ApiError(404)`, termasuk `fnd_13`/`fnd_14` yang hanya contoh baris scan. Screenshot hanya path kontrak, tidak ada berkas gambar. Mock tidak menyimpan perubahan verifikasi atau scan.

Untuk backend nyata, salin `.env.example` ke `.env.local`, set `NEXT_PUBLIC_USE_MOCKS=false` dan `NEXT_PUBLIC_API_URL` ke origin backend. URL HTTPS diperlukan untuk frontend HTTPS. Nilai `NEXT_PUBLIC_*` bukan rahasia dan dibundel saat build: perubahan memerlukan restart dev/redeploy.

Adapter memvalidasi request/response, memakai `credentials: include`, tanpa cache, timeout 30 detik, menolak redirect, dan tidak menampilkan detail mentah error backend. Endpoint produk backend saat ini masih stub. Integrasi login/cookie lintas origin dan otorisasi belum diuji; adapter bukan kontrol akses. Jangan hubungkan data privat sebelum backend menegakkan otorisasi dan penyensoran. Halaman placeholder tidak memanggil endpoint privat.

## Deploy Vercel

1. Import repo dan pilih branch `feat/frontend-skeleton` untuk preview, atau merge dahulu ke branch produksi yang disepakati.
2. Set **Root Directory** ke `frontend`, framework **Next.js**, Node.js **22.x**.
3. Install Command: `npm ci`. Build Command: `npm run build`. Output Directory: default Next.js; jangan memakai static export.
4. Set `NEXT_PUBLIC_USE_MOCKS=true` untuk Preview dan Production. `NEXT_PUBLIC_API_URL` tidak diperlukan pada mode mock.
5. Deploy. Buka kelima path di atas langsung dari URL Vercel, termasuk refresh `/scan/scn_01` dan `/finding/fnd_12`. Tidak perlu rewrite atau `vercel.json`.
6. Untuk mode nyata, set `NEXT_PUBLIC_USE_MOCKS=false`, isi `NEXT_PUBLIC_API_URL`, tambahkan origin Vercel pada `FRONTEND_ORIGIN` backend, lalu redeploy. Pastikan sesi dan otorisasi backend sudah siap.

Verifikasi HTTP remote dapat memakai `FRONTEND_TEST_URL` berisi URL deploy lalu `npm run test:routes`. Deployment Protection Vercel mungkin meminta login; tes HTTP tanpa sesi tidak melewatinya.

## AI Use and Third-Party Declaration

Skeleton, tipe/skema, mock, adapter, dan tes dibuat dengan bantuan AI pada tugas F1-I1; tim wajib meninjau dan memahami perubahan. Tidak menyalin kode produk pra-sprint.

Dependensi langsung: Next.js (MIT), React/React DOM (MIT), Tailwind CSS dan plugin PostCSS (MIT), Zod (MIT), TypeScript (Apache-2.0), serta tipe Node/React/React DOM dari DefinitelyTyped (MIT). Versi terpasang dikunci di `package-lock.json`. Zod dipakai karena tipe TypeScript saja tidak memvalidasi JSON dari jaringan maupun literal enum dalam file JSON. Tidak memakai pustaka komponen, autentikasi, atau test framework tambahan; tes memakai `node:test` dan `node:assert`.
