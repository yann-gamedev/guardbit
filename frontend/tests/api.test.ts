import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ApiError, createSite, getAuditLog, getFinding, getHealth, getRemediation,
  getScan, quickCheck, startScan, verifySite,
} from "../lib/api.ts";
import { mocks, quickCheckResponseSchema, scanResponseSchema } from "../lib/types.ts";
import { reasonLabels, statusLabels } from "../lib/labels.ts";

test("mock default: semua endpoint, label, dan enam fixture sesuai kontrak", async (t) => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error("Mock tidak boleh mengakses jaringan"); });
  const previous = process.env.NEXT_PUBLIC_USE_MOCKS;
  delete process.env.NEXT_PUBLIC_USE_MOCKS;
  t.after(() => {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_USE_MOCKS;
    else process.env.NEXT_PUBLIC_USE_MOCKS = previous;
  });
  assert.equal((await getHealth()).status, "ok");
  for (const status of ["aman", "terindikasi", "tidak_dapat_diperiksa"] as const) {
    const result = await quickCheck({ url: "https://kampus-a.example/" }, status);
    assert.equal(result.status, status);
    assert.deepEqual(Object.keys(result).sort(), ["cached", "checked_at", "pages_checked", "reasons", "status"]);
    assert.ok(statusLabels[result.status]);
    result.reasons.forEach((reason) => assert.ok(reasonLabels[reason]));
  }
  assert.equal((await createSite({ domain: "kampus-a.example" })).site_id, "ste_01");
  assert.equal((await verifySite("ste_01")).verified, true);
  assert.equal((await startScan("ste_01")).status, "running");
  const scan = await getScan("scn_01");
  assert.ok(scan.pages.length >= 6);
  assert.equal(scan.summary.pages, scan.pages.length);
  for (const label of ["terinfeksi", "waspada", "tidak_dapat_diperiksa"] as const) {
    assert.equal(scan.summary[label], scan.pages.filter((page) => page.label === label).length);
  }
  assert.equal(new Set(scan.pages.map((page) => page.label)).size, 4);
  scan.pages.filter((page) => page.label === "aman").forEach((page) => assert.equal(page.finding_id, null));
  const finding = await getFinding("fnd_12");
  assert.equal(scan.pages[0].finding_id, finding.finding_id);
  assert.equal(scan.pages[0].url, finding.url);
  assert.ok(finding.layers.L2.evidence[0].snippet.includes("[DISENSOR]"));
  assert.equal((await getRemediation("fnd_12")).source, "template");
  assert.equal((await getAuditLog())[0].site_alias, "Kampus A");
  await assert.rejects(getScan("scn_missing"), (error) => error instanceof ApiError && error.status === 404);
  await assert.rejects(getFinding("fnd_missing"), (error) => error instanceof ApiError && error.status === 404);
  scan.pages.length = 0;
  assert.equal((await getScan("scn_01")).pages.length, 6);
});

test("validasi menolak enum salah, skor di luar rentang, bukti publik, dan URL non-HTTP", () => {
  assert.equal(quickCheckResponseSchema.safeParse({ ...mocks.quickChecks.aman, status: "terinfeksi" }).success, false);
  assert.equal(quickCheckResponseSchema.safeParse({ ...mocks.quickChecks.aman, url: "https://kampus-a.example/" }).success, false);
  const scan = structuredClone(mocks.scan);
  scan.pages[0].r_score = 1.1;
  assert.equal(scanResponseSchema.safeParse(scan).success, false);
  assert.throws(() => quickCheck({ url: "file:///private" }));
  assert.throws(() => getScan("../audit-log"));
});

test("mode API: metode/path/body, respons buruk, HTTP error, konfigurasi wajib", async (t) => {
  const previousMode = process.env.NEXT_PUBLIC_USE_MOCKS;
  const previousUrl = process.env.NEXT_PUBLIC_API_URL;
  t.after(() => {
    if (previousMode === undefined) delete process.env.NEXT_PUBLIC_USE_MOCKS;
    else process.env.NEXT_PUBLIC_USE_MOCKS = previousMode;
    if (previousUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previousUrl;
  });
  process.env.NEXT_PUBLIC_USE_MOCKS = "false";
  process.env.NEXT_PUBLIC_API_URL = "https://api.example/";
  const calls: { url: string; options?: RequestInit }[] = [];
  const responses = [
    { status: "ok", version: "0.1.0" }, mocks.quickChecks.aman, mocks.site,
    { verified: true, verified_at: "2026-10-31T16:00:00+07:00", message: "Domain terverifikasi" },
    { scan_id: "scn_01", status: "running" }, mocks.scan, mocks.finding,
    { finding_id: "fnd_12", cms: "ojs", steps: [], source: "template", incident_report_draft: "Contoh" }, [],
  ];
  const fetchMock = t.mock.method(globalThis, "fetch", async (url: string | URL | Request, options?: RequestInit) => {
    calls.push({ url: String(url), options });
    return Response.json(responses.shift());
  });
  await getHealth();
  await quickCheck({ url: "https://kampus-a.example/" }, "tidak_dapat_diperiksa");
  await createSite({ domain: "kampus-a.example" });
  await verifySite("ste_01");
  await startScan("ste_01");
  await getScan("scn_01");
  await getFinding("fnd_12");
  await getRemediation("fnd_12");
  await getAuditLog();
  assert.deepEqual(calls.map(({ url, options }) => [url.replace("https://api.example", ""), options?.method]), [
    ["/health", "GET"], ["/quick-check", "POST"], ["/sites", "POST"],
    ["/sites/ste_01/verify", "POST"], ["/sites/ste_01/scan", "POST"],
    ["/scans/scn_01", "GET"], ["/findings/fnd_12", "GET"],
    ["/findings/fnd_12/remediation", "POST"], ["/audit-log", "GET"],
  ]);
  assert.equal(calls[1].options?.body, JSON.stringify({ url: "https://kampus-a.example/" }));
  calls.forEach(({ options }) => {
    assert.equal(options?.credentials, "include");
    assert.equal(options?.cache, "no-store");
    assert.equal(options?.redirect, "error");
  });
  fetchMock.mock.mockImplementation(async () => Response.json({ status: "invalid" }));
  await assert.rejects(getHealth(), (error) => error instanceof ApiError && error.status === 502);
  fetchMock.mock.mockImplementation(async () => Response.json({ detail: "rincian privat" }, { status: 403 }));
  await assert.rejects(getHealth(), (error) => error instanceof ApiError && error.status === 403 && !error.message.includes("privat"));
  delete process.env.NEXT_PUBLIC_API_URL;
  await assert.rejects(getHealth(), /NEXT_PUBLIC_API_URL/);
  process.env.NEXT_PUBLIC_USE_MOCKS = "typo";
  await assert.rejects(getHealth(), /NEXT_PUBLIC_USE_MOCKS/);
});
