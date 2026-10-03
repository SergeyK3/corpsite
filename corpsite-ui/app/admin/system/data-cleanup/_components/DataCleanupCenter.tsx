"use client";
import { useState } from "react";
import TestPersonnelDataAdminClient from "../../test-personnel-data/_components/TestPersonnelDataAdminClient";
import TechnicalPersonnelOrdersPanel from "./TechnicalPersonnelOrdersPanel";
export default function DataCleanupCenter() { const [category, setCategory] = useState<"test" | "orders">("test"); return <div className="space-y-4"><header><h1 className="text-2xl font-semibold">Очистка данных</h1><p className="text-sm text-zinc-600">Единый центр с изолированными правилами удаления для каждой категории.</p></header><div className="flex gap-2"><button className="rounded border px-3 py-2" onClick={() => setCategory("test")}>Тестовые сотрудники и пользователи</button><button className="rounded border px-3 py-2" onClick={() => setCategory("orders")}>Технические кадровые приказы</button></div>{category === "test" ? <TestPersonnelDataAdminClient /> : <TechnicalPersonnelOrdersPanel />}</div>; }
