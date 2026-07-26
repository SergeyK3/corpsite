"use client";

import * as React from "react";

import type { MeInfo } from "./types";

const CurrentUserContext = React.createContext<MeInfo | null>(null);

export function CurrentUserProvider({
  value,
  children,
}: {
  value: MeInfo | null;
  children: React.ReactNode;
}) {
  return <CurrentUserContext.Provider value={value}>{children}</CurrentUserContext.Provider>;
}

/** Profile loaded by AppShell via GET /auth/me (single source of truth). */
export function useCurrentUser(): MeInfo | null {
  return React.useContext(CurrentUserContext);
}
