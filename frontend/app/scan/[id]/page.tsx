export default async function ScanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <h1 className="text-2xl font-bold">Hasil Pemindaian</h1>
      <p>ID pemindaian: {id}</p>
      <p>Ringkasan dan daftar halaman belum tersedia. Akses data memerlukan otorisasi.</p>
    </>
  );
}
