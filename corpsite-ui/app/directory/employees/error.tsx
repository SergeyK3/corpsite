"use client";

export default function Error({ error }: { error: Error }) {
  return (
    <div className="p-6">
      <div className="border rounded p-4 bg-white">
        <div className="font-semibold">Ошибка загрузки</div>
        <div className="text-sm text-gray-600 mt-2">{error.message}</div>
      </div>
    </div>
  );
}
