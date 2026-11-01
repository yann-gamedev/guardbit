import assert from "node:assert/strict";
import test from "node:test";
import { triggerLabel } from "../lib/labels.ts";
import { mockScan, pagePath, sortPages } from "../lib/scan.ts";
import { mocks, scanResponseSchema } from "../lib/types.ts";

test("sortPages: terinfeksi, waspada, tidak_dapat_diperiksa, aman; lalu skor R menurun", () => {
  const sorted = sortPages(mocks.scan.pages);
  assert.deepEqual(sorted.map((page) => page.page_id), ["pg_07", "pg_08", "pg_09", "pg_12", "pg_11", "pg_10"]);
  assert.equal(mocks.scan.pages[0].page_id, "pg_07");
  assert.equal(mocks.scan.pages[3].page_id, "pg_10", "array asal tidak diubah");
});

test("pagePath membuang domain, mempertahankan path dan query", () => {
  assert.equal(pagePath("https://kampus-a.example/berita/123"), "/berita/123");
  assert.equal(pagePath("https://kampus-a.example/"), "/");
  assert.equal(pagePath("https://kampus-a.example/cari?q=1"), "/cari?q=1");
});

test("triggerLabel memetakan prefiks L1-L4", () => {
  assert.equal(triggerLabel("L1:crawler_only_hosts=14"), "Beda untuk mesin pencari");
  assert.equal(triggerLabel("L1:blocked"), "Pemeriksaan diblokir");
  assert.equal(triggerLabel("L2:display_none"), "Tersembunyi (CSS)");
  assert.equal(triggerLabel("L3:prob=0.97"), "Teks judi");
  assert.equal(triggerLabel("L4:foreign_host_ratio=0.42"), "Tautan keluar asing");
  assert.equal(triggerLabel("L9:x"), null);
});

test("mockScan: skenario sesuai kontrak, running selesai setelah 2 polling, ID lain null", () => {
  for (const [id, polls] of [["scn_01", 0], ["scn_running", 0], ["scn_running", 2], ["scn_failed", 0], ["scn_kosong", 0]] as const) {
    scanResponseSchema.parse(mockScan(id, polls));
  }
  assert.equal(mockScan("scn_running", 1)?.status, "running");
  assert.equal(mockScan("scn_running", 2)?.status, "done");
  assert.equal(mockScan("scn_kosong")?.pages.length, 0);
  assert.equal(mockScan("scn_missing"), null);
});
