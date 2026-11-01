"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";
import { ApiError, mocksEnabled, quickCheck } from "@/lib/api";
import { reasonLabels, statusLabels } from "@/lib/labels";
import { EXAMPLE_URL, pickScenario, urlError } from "@/lib/quick-check";
import type { QuickCheckResponse } from "@/lib/types";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "result"; data: QuickCheckResponse }
  | { kind: "error"; message: string };

const dateFormat = new Intl.DateTimeFormat("id-ID", { dateStyle: "long", timeStyle: "short", timeZone: "Asia/Jakarta" });

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 429) return "Terlalu banyak pemeriksaan dalam waktu singkat. Tunggu sebentar, lalu coba lagi.";
  if (error instanceof ApiError && error.status < 500) return "Permintaan tidak dapat diproses. Periksa alamat situs, lalu coba lagi.";
  return "Tidak dapat terhubung ke layanan GuardBit. Periksa koneksi internet Anda, lalu coba lagi.";
}

export default function QuickCheckPage() {
  const [url, setUrl] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [state, setState] = useState<State>({ kind: "idle" });
  const inputRef = useRef<HTMLInputElement>(null);
  const requestId = useRef(0);
  const ids = { input: useId(), hint: useId(), error: useId() };

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = urlError(url);
    setFieldError(problem);
    if (problem) {
      inputRef.current?.focus();
      return;
    }
    const current = ++requestId.current;
    setState({ kind: "loading" });
    try {
      const target = url.trim();
      // ponytail: jeda dan pemilih skenario hanya untuk mock; hapus saat backend nyata dipakai di demo.
      if (mocksEnabled()) await new Promise((resolve) => setTimeout(resolve, 1500));
      const data = await quickCheck({ url: target }, pickScenario(target));
      if (current === requestId.current) setState({ kind: "result", data });
    } catch (error) {
      if (current === requestId.current) setState({ kind: "error", message: errorMessage(error) });
    }
  }

  const loading = state.kind === "loading";

  return (
    <div className="mx-auto max-w-2xl space-y-8 py-4 sm:py-10">
      <section aria-labelledby="judul" className="space-y-3">
        <h1 id="judul" className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">Cek Cepat</h1>
        <p className="text-lg text-muted">
          GuardBit memeriksa apakah situs instansi Anda disusupi konten judi online yang disembunyikan dari pengunjung.
        </p>
      </section>

      <form onSubmit={onSubmit} noValidate className="space-y-3 rounded-lg border border-line bg-surface p-5 sm:p-6">
        <label htmlFor={ids.input} className="block text-base font-semibold">Alamat situs</label>
        <p id={ids.hint} className="text-sm text-muted">Tulis lengkap dengan http:// atau https://, misalnya {EXAMPLE_URL}</p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            ref={inputRef}
            id={ids.input}
            name="url"
            type="url"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            placeholder={EXAMPLE_URL}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            aria-invalid={fieldError ? true : undefined}
            aria-describedby={fieldError ? `${ids.hint} ${ids.error}` : ids.hint}
            className="min-h-12 w-full min-w-0 rounded-md border border-neutral-line bg-surface px-3 text-base text-ink placeholder:text-neutral-line aria-invalid:border-error-ink"
          />
          <button
            type="submit"
            disabled={loading}
            className="min-h-12 shrink-0 rounded-md bg-accent px-5 font-semibold text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-70"
          >
            {loading ? "Memeriksa…" : "Periksa situs"}
          </button>
        </div>
        {fieldError && <p id={ids.error} className="text-sm font-medium text-error-ink">{fieldError}</p>}
      </form>

      <div aria-live="polite" aria-busy={loading}>
        {state.kind === "idle" && (
          <p className="text-muted">Hasil pemeriksaan akan muncul di sini. Hasil publik hanya berisi status dan kategori alasan.</p>
        )}
        {state.kind === "loading" && (
          <p role="status" className="rounded-lg border border-line bg-surface p-5 text-ink">
            Sedang memeriksa situs. Proses ini biasanya memerlukan beberapa detik.
          </p>
        )}
        {state.kind === "error" && (
          <div role="alert" className="rounded-lg border border-error-ink bg-error-bg p-5 text-error-ink">
            <h2 className="font-semibold">Pemeriksaan gagal</h2>
            <p className="mt-1">{state.message}</p>
          </div>
        )}
        {state.kind === "result" && <ResultCard data={state.data} />}
      </div>
    </div>
  );
}

function ResultCard({ data }: { data: QuickCheckResponse }) {
  const checkedAt = dateFormat.format(new Date(data.checked_at));
  const meta = (
    <p className="mt-4 text-sm text-muted">
      Diperiksa {checkedAt} WIB{data.pages_checked > 0 && `, ${data.pages_checked} halaman`}{data.cached && ". Hasil dari pemeriksaan sebelumnya"}.
    </p>
  );

  if (data.status === "aman") {
    return (
      <section aria-labelledby="hasil" className="rounded-lg border-l-4 border-safe-line bg-safe-bg p-5 sm:p-6">
        <h2 id="hasil" className="text-xl font-bold text-safe-ink">{statusLabels.aman}</h2>
        <p className="mt-2 text-ink">Tidak ditemukan indikasi konten judi online pada halaman yang diperiksa.</p>
        <p className="mt-3 font-medium text-ink">
          Hanya halaman yang diperiksa yang dinilai; ini bukan jaminan seluruh situs bersih.
        </p>
        {meta}
      </section>
    );
  }

  if (data.status === "terindikasi") {
    return (
      <section aria-labelledby="hasil" className="rounded-lg border-l-4 border-warn-line bg-warn-bg p-5 sm:p-6">
        <h2 id="hasil" className="text-xl font-bold text-warn-ink">{statusLabels.terindikasi}</h2>
        <p className="mt-2 text-ink">Pemeriksaan menemukan tanda berikut:</p>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-ink">
          {data.reasons.map((reason) => <li key={reason}>{reasonLabels[reason]}</li>)}
        </ul>
        {meta}
        <p className="mt-4">
          <Link href="/sites" className="font-semibold text-accent underline underline-offset-4 hover:text-accent-strong">
            Verifikasi kepemilikan untuk melihat detail
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="hasil" className="rounded-lg border-l-4 border-neutral-line bg-neutral-bg p-5 sm:p-6">
      <h2 id="hasil" className="text-xl font-bold text-neutral-ink">{statusLabels.tidak_dapat_diperiksa}</h2>
      <p className="mt-2 text-ink">
        Situs ini memblokir pemeriksaan otomatis, sehingga GuardBit tidak dapat menilai isinya. Status ini bukan berarti situs aman.
      </p>
      <p className="mt-3 text-ink">
        Jika Anda pengelola situs ini,{" "}
        <Link href="/sites" className="font-semibold text-accent underline underline-offset-4 hover:text-accent-strong">
          verifikasi kepemilikan domain
        </Link>{" "}
        agar pemeriksaan dapat dilakukan lebih lengkap.
      </p>
      {meta}
    </section>
  );
}
