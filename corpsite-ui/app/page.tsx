// FILE: corpsite-ui/app/page.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthed } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthed()) {
      router.replace("/login");
      return;
    }
    router.replace("/tasks");
  }, [router]);

  return null;
}
