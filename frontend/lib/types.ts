import { z } from "zod";
import quickIndicated from "../mocks/quick-check-terindikasi.json" with { type: "json" };
import quickSafe from "../mocks/quick-check-aman.json" with { type: "json" };
import quickBlocked from "../mocks/quick-check-tidak-dapat-diperiksa.json" with { type: "json" };
import scan from "../mocks/scan.json" with { type: "json" };
import finding from "../mocks/finding.json" with { type: "json" };
import site from "../mocks/sites.json" with { type: "json" };

// Skema menjadi sumber tipe sekaligus validasi JSON; tanpa cast literal impor JSON.
const score = z.number().min(0).max(1);
const count = z.number().int().nonnegative();
const time = z.iso.datetime({ offset: true }).refine((value) => value.endsWith("+07:00"));
const httpUrl = z.url({ protocol: /^https?$/ });
export const siteIdSchema = z.string().regex(/^ste_[A-Za-z0-9_-]+$/);
export const scanIdSchema = z.string().regex(/^scn_[A-Za-z0-9_-]+$/);
export const findingIdSchema = z.string().regex(/^fnd_[A-Za-z0-9_-]+$/);
const pageIdSchema = z.string().regex(/^pg_[A-Za-z0-9_-]+$/);
export const quickCheckStatusSchema = z.enum(["aman", "terindikasi", "tidak_dapat_diperiksa"]);
export const pageLabelSchema = z.enum(["aman", "waspada", "terinfeksi", "tidak_dapat_diperiksa"]);
export const scanStatusSchema = z.enum(["running", "done", "failed"]);
export const layerStatusSchema = z.enum(["ok", "partial", "blocked", "skipped"]);
export const profileSchema = z.enum(["browser", "crawler", "search"]);
export const quickCheckReasonSchema = z.enum([
  "konten_judi_tersembunyi", "konten_berbeda_untuk_mesin_pencari",
  "pengalihan_ke_situs_luar", "teks_judi_tersamarkan",
  "tautan_keluar_mencurigakan", "situs_memblokir_pemeriksaan",
]);
export const l2ReasonSchema = z.enum([
  "display_none", "visibility_hidden", "opacity_zero", "offscreen",
  "tiny_text", "same_color", "zero_size", "clipped",
]);
export const remediationSourceSchema = z.enum(["template", "template+llm"]);
export const errorStatusSchema = z.union([
  z.literal(400), z.literal(401), z.literal(403), z.literal(404), z.literal(429), z.literal(501),
]);

export const healthResponseSchema = z.strictObject({ status: z.literal("ok"), version: z.literal("0.1.0") });
export const quickCheckRequestSchema = z.strictObject({ url: httpUrl });
export const quickCheckResponseSchema = z.strictObject({
  status: quickCheckStatusSchema,
  reasons: z.array(quickCheckReasonSchema),
  pages_checked: count,
  checked_at: time,
  cached: z.boolean(),
});
export const siteCreateRequestSchema = z.strictObject({
  domain: z.string().max(253).regex(/^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/),
});
export const siteCreateResponseSchema = z.strictObject({
  site_id: siteIdSchema,
  domain: siteCreateRequestSchema.shape.domain,
  token: z.string(),
  verify_path: z.string(),
  verified: z.boolean(),
});
export const siteVerifyResponseSchema = z.strictObject({
  verified: z.boolean(), verified_at: time.nullable(), message: z.string(),
});
export const scanStartResponseSchema = z.strictObject({ scan_id: scanIdSchema, status: z.literal("running") });
export const scanSummarySchema = z.strictObject({
  pages: count, terinfeksi: count, waspada: count, tidak_dapat_diperiksa: count,
});
export const scanPageSchema = z.strictObject({
  page_id: pageIdSchema, url: httpUrl, r_score: score, label: pageLabelSchema,
  triggers: z.array(z.string()), finding_id: findingIdSchema.nullable(),
}).refine((page) => page.label !== "aman" || page.finding_id === null);
export const scanResponseSchema = z.strictObject({
  scan_id: scanIdSchema, site_alias: z.string(), status: scanStatusSchema,
  started_at: time, finished_at: time.nullable(), summary: scanSummarySchema,
  pages: z.array(scanPageSchema),
});
export const l1EvidenceSchema = z.strictObject({ profile: profileSchema, note: z.string() });
export const l2EvidenceSchema = z.strictObject({
  selector: z.string(), reason: l2ReasonSchema, link_count: count, snippet: z.string(),
});
export const l3EvidenceSchema = z.strictObject({ selector: z.string(), prob: score, top_ngrams: z.array(z.string()) });
export const l4EvidenceSchema = z.strictObject({ foreign_host_ratio: score, note: z.string() });
const layerSchema = <T extends z.ZodType>(evidence: T) => z.strictObject({
  status: layerStatusSchema, score, evidence: z.array(evidence),
});
export const findingLayersSchema = z.strictObject({
  L1: layerSchema(l1EvidenceSchema), L2: layerSchema(l2EvidenceSchema),
  L3: layerSchema(l3EvidenceSchema), L4: layerSchema(l4EvidenceSchema),
});
export const findingResponseSchema = z.strictObject({
  finding_id: findingIdSchema, page_id: pageIdSchema, url: httpUrl,
  label: pageLabelSchema, r_score: score, layers: findingLayersSchema,
  screenshots: z.partialRecord(profileSchema, z.string()), checked_at: time,
});
export const remediationStepSchema = z.strictObject({ title: z.string(), detail: z.string() });
export const remediationResponseSchema = z.strictObject({
  finding_id: findingIdSchema, cms: z.string(), steps: z.array(remediationStepSchema),
  source: remediationSourceSchema, incident_report_draft: z.string(),
});
export const auditEntrySchema = z.strictObject({
  id: z.number().int().positive(), user: z.string(), site_alias: z.string(),
  action: z.string(), created_at: time,
});
export const auditLogResponseSchema = z.array(auditEntrySchema);
export const errorResponseSchema = z.strictObject({ detail: z.string() });

export type SiteID = z.infer<typeof siteIdSchema>;
export type ScanID = z.infer<typeof scanIdSchema>;
export type PageID = z.infer<typeof pageIdSchema>;
export type FindingID = z.infer<typeof findingIdSchema>;
export type QuickCheckStatus = z.infer<typeof quickCheckStatusSchema>;
export type PageLabel = z.infer<typeof pageLabelSchema>;
export type ScanStatus = z.infer<typeof scanStatusSchema>;
export type LayerStatus = z.infer<typeof layerStatusSchema>;
export type Profile = z.infer<typeof profileSchema>;
export type QuickCheckReason = z.infer<typeof quickCheckReasonSchema>;
export type L2Reason = z.infer<typeof l2ReasonSchema>;
export type RemediationSource = z.infer<typeof remediationSourceSchema>;
export type ErrorStatus = z.infer<typeof errorStatusSchema>;
export type HealthResponse = z.infer<typeof healthResponseSchema>;
export type QuickCheckRequest = z.infer<typeof quickCheckRequestSchema>;
export type QuickCheckResponse = z.infer<typeof quickCheckResponseSchema>;
export type SiteCreateRequest = z.infer<typeof siteCreateRequestSchema>;
export type SiteCreateResponse = z.infer<typeof siteCreateResponseSchema>;
export type SiteVerifyResponse = z.infer<typeof siteVerifyResponseSchema>;
export type ScanStartResponse = z.infer<typeof scanStartResponseSchema>;
export type ScanSummary = z.infer<typeof scanSummarySchema>;
export type ScanPage = z.infer<typeof scanPageSchema>;
export type L1Evidence = z.infer<typeof l1EvidenceSchema>;
export type L2Evidence = z.infer<typeof l2EvidenceSchema>;
export type L3Evidence = z.infer<typeof l3EvidenceSchema>;
export type L4Evidence = z.infer<typeof l4EvidenceSchema>;
export type FindingLayers = z.infer<typeof findingLayersSchema>;
export type LayerResult<Evidence> = { status: LayerStatus; score: number; evidence: Evidence[] };
export type FindingResponse = z.infer<typeof findingResponseSchema>;
export type RemediationStep = z.infer<typeof remediationStepSchema>;
export type RemediationResponse = z.infer<typeof remediationResponseSchema>;
export type AuditEntry = z.infer<typeof auditEntrySchema>;
export type AuditLogResponse = z.infer<typeof auditLogResponseSchema>;
export type ErrorResponse = z.infer<typeof errorResponseSchema>;

// Impor keenam JSON wajib lolos skema saat test/build; enum salah tidak disembunyikan dengan `as`.
export const mocks = {
  quickChecks: {
    terindikasi: quickCheckResponseSchema.parse(quickIndicated),
    aman: quickCheckResponseSchema.parse(quickSafe),
    tidak_dapat_diperiksa: quickCheckResponseSchema.parse(quickBlocked),
  } satisfies Record<QuickCheckStatus, QuickCheckResponse>,
  scan: scanResponseSchema.parse(scan),
  finding: findingResponseSchema.parse(finding),
  site: siteCreateResponseSchema.parse(site),
};
