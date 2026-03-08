// FILE: corpsite-ui/app/directory/positions/page.tsx
export default function PositionsPage() {
  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-4">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-6 py-6">
            <h1 className="text-2xl font-semibold text-zinc-100">Должности</h1>
          </div>

          <div className="px-6 py-6">
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-4 text-sm text-zinc-300">
              Раздел в подготовке. Здесь будет CRUD справочника должностей.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}