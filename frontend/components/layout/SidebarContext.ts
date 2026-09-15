"use client";

import { createContext, useContext } from "react";

// Le repli est décidé dans AppShell, mais c'est PageContainer qui doit s'y
// adapter — or il reçoit ses enfants par `children` et n'est pas joignable
// par des props depuis AppShell. Un contexte évite de faire redescendre le
// booléen page par page, dans les sept écrans qui utilisent PageContainer.
export const SidebarContext = createContext(false);

export function useSidebarReplie(): boolean {
  return useContext(SidebarContext);
}
