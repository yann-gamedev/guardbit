import assert from "node:assert/strict";

const base = process.env.FRONTEND_TEST_URL ?? "http://localhost:3000";
for (const [path, heading] of [
  ["/", "Cek Cepat"],
  ["/scan/scn_01", "Hasil Pemindaian"],
  ["/finding/fnd_12", "Detail Temuan"],
  ["/login", "Masuk"],
  ["/sites", "Situs Saya"],
]) {
  const response = await fetch(new URL(path, base), { redirect: "error", signal: AbortSignal.timeout(60_000) });
  assert.equal(response.status, 200, path);
  const html = await response.text();
  assert.ok(html.includes('lang="id"'), path);
  assert.ok(html.includes("GuardBit"), path);
  assert.match(html, new RegExp(`<h1[^>]*>${heading}</h1>`), path);
  console.log(`OK ${path}`);
}
