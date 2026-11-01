import assert from "node:assert/strict";
import test from "node:test";
import { pickScenario, urlError } from "../lib/quick-check.ts";

test("urlError menerima URL http(s) dengan domain bertitik", () => {
  for (const url of ["https://kampus-anda.ac.id", "http://sekolah-b.example/berita?id=1", "  https://desa-a.example/  "]) {
    assert.equal(urlError(url), null, url);
  }
});

test("urlError menolak input tidak valid dengan pesan Indonesia", () => {
  assert.match(urlError("")!, /Masukkan alamat/);
  assert.match(urlError("kampus-anda.ac.id")!, /http:\/\/ atau https:\/\//);
  assert.match(urlError("ftp://kampus-anda.ac.id")!, /http:\/\/ atau https:\/\//);
  assert.match(urlError("https://localhost")!, /domain belum lengkap/);
  assert.match(urlError("https://[::1]/")!, /domain belum lengkap/);
  assert.match(urlError("https://a:b@kampus-anda.ac.id")!, /kata sandi/);
  assert.match(urlError("https://")!, /tidak valid/);
});

test("pickScenario memetakan kata kunci mock", () => {
  assert.equal(pickScenario("https://kampus-aman.example"), "aman");
  assert.equal(pickScenario("https://BLOKIR.example"), "tidak_dapat_diperiksa");
  assert.equal(pickScenario("https://kampus-anda.ac.id"), "terindikasi");
});
