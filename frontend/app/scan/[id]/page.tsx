import { Suspense } from "react";
import ScanView from "./scan-view";

export default async function ScanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6 py-4 sm:py-8">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Hasil Pemindaian</h1>
      <Suspense fallback={<p role="status" className="text-muted">Memuat hasil pemindaian…</p>}>
        <ScanView id={id} />
      </Suspense>
    </div>
  );
}
