import { z } from "zod";
import {
  auditLogResponseSchema, findingIdSchema, findingResponseSchema,
  healthResponseSchema, mocks, quickCheckRequestSchema, quickCheckResponseSchema,
  remediationResponseSchema, scanIdSchema, scanResponseSchema, scanStartResponseSchema,
  siteCreateRequestSchema, siteCreateResponseSchema, siteIdSchema, siteVerifyResponseSchema,
} from "./types.ts";
import type { QuickCheckRequest, QuickCheckStatus, SiteCreateRequest } from "./types.ts";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function useMocks() {
  const value = process.env.NEXT_PUBLIC_USE_MOCKS ?? "true";
  if (value !== "true" && value !== "false") {
    throw new Error("NEXT_PUBLIC_USE_MOCKS harus true atau false.");
  }
  return value === "true";
}

async function request<T>(path: string, schema: z.ZodType<T>, mock: () => unknown, body?: unknown, method = "GET"): Promise<T> {
  if (useMocks()) return schema.parse(structuredClone(mock()));

  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base) throw new Error("NEXT_PUBLIC_API_URL wajib diisi saat mock dinonaktifkan.");
  const url = new URL(base);
  if (!/^https?:$/.test(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("NEXT_PUBLIC_API_URL harus URL HTTP(S) tanpa kredensial, query, atau fragmen.");
  }
  const response = await fetch(`${base.replace(/\/+$/, "")}${path}`, {
    method,
    headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "include",
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.timeout(30_000),
  });
  // Jangan tampilkan detail mentah backend: bisa memuat URL atau bukti privat.
  if (!response.ok) throw new ApiError(response.status, `Permintaan gagal (HTTP ${response.status}).`);
  const result = schema.safeParse(await response.json());
  if (!result.success) throw new ApiError(502, "Respons API tidak sesuai kontrak.");
  return result.data;
}

function requireMockId(actual: string, expected: string) {
  if (actual !== expected) throw new ApiError(404, "Data contoh tidak ditemukan.");
}

export function getHealth() {
  return request("/health", healthResponseSchema, () => ({ status: "ok", version: "0.1.0" }));
}

// Skenario hanya memilih fixture saat mock aktif; tidak dikirim ke backend.
export function quickCheck(input: QuickCheckRequest, scenario: QuickCheckStatus = "terindikasi") {
  const body = quickCheckRequestSchema.parse(input);
  return request("/quick-check", quickCheckResponseSchema, () => mocks.quickChecks[scenario], body, "POST");
}

export function createSite(input: SiteCreateRequest) {
  const body = siteCreateRequestSchema.parse(input);
  return request("/sites", siteCreateResponseSchema, () => ({ ...mocks.site, domain: body.domain }), body, "POST");
}

export function verifySite(id: string) {
  siteIdSchema.parse(id);
  return request(`/sites/${id}/verify`, siteVerifyResponseSchema, () => {
    requireMockId(id, mocks.site.site_id);
    return { verified: true, verified_at: "2026-10-31T16:00:00+07:00", message: "Domain terverifikasi" };
  }, undefined, "POST");
}

export function startScan(id: string) {
  siteIdSchema.parse(id);
  return request(`/sites/${id}/scan`, scanStartResponseSchema, () => {
    requireMockId(id, mocks.site.site_id);
    return { scan_id: mocks.scan.scan_id, status: "running" };
  }, undefined, "POST");
}

export function getScan(id: string) {
  scanIdSchema.parse(id);
  return request(`/scans/${id}`, scanResponseSchema, () => {
    requireMockId(id, mocks.scan.scan_id);
    return mocks.scan;
  });
}

export function getFinding(id: string) {
  findingIdSchema.parse(id);
  return request(`/findings/${id}`, findingResponseSchema, () => {
    requireMockId(id, mocks.finding.finding_id);
    return mocks.finding;
  });
}

export function getRemediation(id: string) {
  findingIdSchema.parse(id);
  return request(`/findings/${id}/remediation`, remediationResponseSchema, () => {
    requireMockId(id, mocks.finding.finding_id);
    return {
      finding_id: id, cms: "ojs",
      steps: [
        { title: "Cadangkan situs", detail: "Simpan salinan berkas dan basis data sebelum perbaikan." },
        { title: "Cari file template yang berubah", detail: "Bandingkan dengan cadangan bersih dan tinjau perubahan yang tidak dikenal." },
      ],
      source: "template", incident_report_draft: "Contoh laporan: indikasi penyusupan ditemukan pada Kampus A. Temuan perlu ditinjau pengelola.",
    };
  }, undefined, "POST");
}

export function getAuditLog() {
  return request("/audit-log", auditLogResponseSchema, () => [
    { id: 1, user: "christian", site_alias: "Kampus A", action: "scan", created_at: "2026-10-31T16:05:00+07:00" },
  ]);
}
