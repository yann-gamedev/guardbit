export default async function FindingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <h1 className="text-2xl font-bold">Detail Temuan</h1>
      <p>ID temuan: {id}</p>
      <p>Bukti deteksi dan panduan perbaikan belum tersedia. Tautan berbahaya akan ditampilkan sebagai [DISENSOR].</p>
    </>
  );
}
