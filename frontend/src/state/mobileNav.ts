import { useSyncExternalStore } from "react";

// Off-canvas sidebar state for phone widths. Each page renders its own <SidebarNav />,
// so the open flag lives outside React (module-level store) and the header toggles it.
let open = false;
const listeners = new Set<() => void>();

export function setMobileNavOpen(v: boolean) {
  if (open === v) return;
  open = v;
  listeners.forEach(l => l());
}

export function useMobileNavOpen(): boolean {
  return useSyncExternalStore(
    cb => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    () => open,
  );
}
