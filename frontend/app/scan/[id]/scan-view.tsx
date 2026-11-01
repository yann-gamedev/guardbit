"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getScan } from "@/lib/api";
import { labelTones, statusLabels, triggerLabel } from "@/lib/labels";
import { LABEL_ORDER, pagePath, sortPages } from "@/lib/scan";
import { pageLabelSchema } from "@/lib/types";
import type { PageLabel, ScanPage, ScanResponse } from "@/lib/types";

const POLL_MS = 3000;
const dateFormat = new Intl.DateTimeFormat("id-ID", { dateStyle: "long", timeStyle: "short", timeZone: "Asia/Jakarta" });
const scoreFormat = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

type State =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "error" }
  | { kind: "ready"; scan: ScanResponse };

const link = "font-semibold text-accent underline underline-offset-4 hover:text-accent-strong";

export default function ScanView({ id }: { id: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const params = useSearchParams();
  const parsed = pageLabelSchema.safeParse(params.get("label"));
  const filter = parsed.success ? parsed.data : null;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load(polls: number) {
      try {
        const scan = await getScan(id, polls);
        if (cancelled) return;
        setState({ kind: "ready", scan });
        if (scan.status === "running") timer = setTimeout(() => load(polls + 1), POLL_MS);
      } catch (error) {
        if (cancelled) return;
        // ID salah format (ZodError) diperlakukan sama dengan 404.
        const missing = !(error instanceof ApiError) || error.status === 404;
        setState({ kind: missing ? "missing" : "error" });
      }
    }
    load(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id]);

  function setFilter(label: PageLabel | null) {
    // Filter disimpan di URL agar bisa dibagikan; history API native terintegrasi dengan useSearchParams.
    window.history.replaceState(null, "", label ? `?label=${label}` : window.location.pathname);
  }

  if (state.kind === "loading") {
    return <p role="status" className="rounded-lg border border-line bg-surface p-5 text-muted">Memuat hasil pemindaian…</p>;
  }
  if (state.kind === "missing" || state.kind === "error") {
    return (
      <div role="alert" className="rounded-lg border border-error-ink bg-error-bg p-5 text-error-ink">
        <h2 className="font-semibold">{state.kind === "missing" ? "Pemindaian tidak ditemukan" : "Hasil pemindaian gagal dimuat"}</h2>
        <p className="mt-1 text-ink">
          {state.kind === "missing"
            ? "Periksa kembali tautan, atau buka daftar situs untuk memulai pemindaian baru."
            : "Periksa koneksi internet Anda, lalu muat ulang halaman."}
        </p>
        <p className="mt-3"><Link href="/sites" className={link}>Buka Situs Saya</Link></p>
      </div>
    );
  }

  const { scan } = state;
  const pages = sortPages(scan.pages).filter((page) => !filter || page.label === filter);
  const counts = Object.fromEntries(LABEL_ORDER.map((label) => [label, scan.pages.filter((page) => page.label === label).length]));

  return (
    <div className="space-y-8">
      <section aria-labelledby="situs" className="space-y-3">
        <h2 id="situs" className="text-xl font-semibold text-ink">{scan.site_alias}</h2>
        <dl className="grid gap-x-6 gap-y-1 text-sm text-muted sm:grid-cols-[auto_1fr]">
          <dt>Mulai</dt>
          <dd className="text-ink">{dateFormat.format(new Date(scan.started_at))} WIB</dd>
          <dt>Selesai</dt>
          <dd className="text-ink">{scan.finished_at ? `${dateFormat.format(new Date(scan.finished_at))} WIB` : "Belum selesai"}</dd>
        </dl>
        <ScanStatus status={scan.status} />
      </section>

      <section aria-labelledby="ringkasan">
        <h2 id="ringkasan" className="sr-only">Ringkasan</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Halaman diperiksa" value={scan.summary.pages} />
          <Stat label={statusLabels.terinfeksi} value={scan.summary.terinfeksi} tone="text-error-ink" />
          <Stat label={statusLabels.waspada} value={scan.summary.waspada} tone="text-warn-ink" />
          <Stat label={statusLabels.tidak_dapat_diperiksa} value={scan.summary.tidak_dapat_diperiksa} tone="text-neutral-ink" />
        </dl>
      </section>

      <section aria-labelledby="halaman" className="space-y-4">
        <h2 id="halaman" className="text-xl font-bold text-ink">Halaman</h2>
        {scan.pages.length === 0 ? (
          <p className="rounded-lg border border-line bg-surface p-5 text-muted">
            {scan.status === "running" ? "Halaman akan muncul di sini selama pemindaian berjalan." : "Tidak ada halaman yang diperiksa pada pemindaian ini."}
          </p>
        ) : (
          <>
            <div role="group" aria-label="Saring berdasarkan label" className="flex flex-wrap gap-2">
              <FilterButton active={!filter} onClick={() => setFilter(null)}>Semua ({scan.pages.length})</FilterButton>
              {LABEL_ORDER.map((label) => (
                <FilterButton key={label} active={filter === label} onClick={() => setFilter(label)}>
                  {statusLabels[label]} ({counts[label]})
                </FilterButton>
              ))}
            </div>
            {pages.length === 0 ? (
              <p className="rounded-lg border border-line bg-surface p-5 text-muted">Tidak ada halaman berlabel {statusLabels[filter!]}.</p>
            ) : (
              <PageList pages={pages} />
            )}
          </>
        )}
      </section>
    </div>
  );
}

function ScanStatus({ status }: { status: ScanResponse["status"] }) {
  if (status === "running") {
    return (
      <p role="status" className="flex items-center gap-3 rounded-md bg-neutral-bg px-4 py-3 text-neutral-ink">
        <span aria-hidden className="size-4 shrink-0 motion-safe:animate-spin rounded-full border-2 border-neutral-line border-t-transparent" />
        Pemindaian sedang berjalan. Hasil diperbarui otomatis setiap 3 detik.
      </p>
    );
  }
  if (status === "failed") {
    return (
      <p role="alert" className="rounded-md bg-error-bg px-4 py-3 text-error-ink">
        Pemindaian gagal sebelum selesai. Hasil di bawah mungkin tidak lengkap; mulai pemindaian ulang dari Situs Saya.
      </p>
    );
  }
  return <p className="font-medium text-safe-ink">Pemindaian selesai.</p>;
}

function Stat({ label, value, tone = "text-ink" }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={`mt-1 text-3xl font-bold tabular-nums ${tone}`}>{value}</dd>
    </div>
  );
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className="min-h-11 rounded-md border border-line bg-surface px-3 text-sm font-medium text-ink hover:border-accent active:bg-neutral-bg aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-white"
    >
      {children}
    </button>
  );
}

function LabelChip({ label }: { label: PageLabel }) {
  return <span className={`inline-block shrink-0 rounded px-2 py-0.5 text-sm font-semibold whitespace-nowrap ${labelTones[label].chip}`}>{statusLabels[label]}</span>;
}

function Score({ page }: { page: ScanPage }) {
  return (
    <span className="flex items-center gap-2">
      <span className="w-10 text-right tabular-nums">{scoreFormat.format(page.r_score)}</span>
      <span aria-hidden className="h-1.5 w-16 overflow-hidden rounded-full bg-neutral-bg">
        <span className={`block h-full ${labelTones[page.label].bar}`} style={{ width: `${page.r_score * 100}%` }} />
      </span>
    </span>
  );
}

function Triggers({ triggers }: { triggers: string[] }) {
  const labels = [...new Set(triggers.map(triggerLabel).filter((label) => label !== null))];
  if (labels.length === 0) return <p className="text-sm text-muted">Tidak ada</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {labels.map((label) => <li key={label} className="rounded border border-line px-2 py-0.5 text-sm text-ink">{label}</li>)}
    </ul>
  );
}

function Evidence({ page }: { page: ScanPage }) {
  if (!page.finding_id) {
    return <button type="button" disabled title="Tidak ada temuan untuk halaman ini" className="block min-h-11 text-sm whitespace-nowrap text-muted disabled:cursor-not-allowed">Lihat bukti</button>;
  }
  return (
    <Link href={`/finding/${page.finding_id}`} className={`inline-flex min-h-11 items-center text-sm whitespace-nowrap ${link}`}>
      Lihat bukti<span className="sr-only"> untuk {pagePath(page.url)}</span>
    </Link>
  );
}

function PageList({ pages }: { pages: ScanPage[] }) {
  return (
    <>
      <table className="hidden w-full border-collapse overflow-hidden rounded-lg bg-surface text-left sm:table">
        <thead className="border-b border-line text-sm text-muted">
          <tr>
            <th scope="col" className="p-3 font-medium">Halaman</th>
            <th scope="col" className="p-3 font-medium">Skor R</th>
            <th scope="col" className="p-3 font-medium">Label</th>
            <th scope="col" className="p-3 font-medium">Pemicu</th>
            <th scope="col" className="p-3 font-medium"><span className="sr-only">Bukti</span></th>
          </tr>
        </thead>
        <tbody>
          {pages.map((page) => (
            <tr key={page.page_id} className="border-b border-line last:border-0 align-middle">
              <td className="min-w-44 p-3 font-mono text-sm break-all">{pagePath(page.url)}</td>
              <td className="p-3"><Score page={page} /></td>
              <td className="p-3"><LabelChip label={page.label} /></td>
              <td className="p-3"><Triggers triggers={page.triggers} /></td>
              <td className="p-3 text-right"><Evidence page={page} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="space-y-3 sm:hidden">
        {pages.map((page) => (
          <li key={page.page_id} className="space-y-3 rounded-lg border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <span className="min-w-0 font-mono text-sm break-all">{pagePath(page.url)}</span>
              <LabelChip label={page.label} />
            </div>
            <div className="flex items-center gap-2 text-sm"><span className="text-muted">Skor R</span><Score page={page} /></div>
            <Triggers triggers={page.triggers} />
            <Evidence page={page} />
          </li>
        ))}
      </ul>
    </>
  );
}
