import { useSyncExternalStore } from "react";

export const MOBILE_MAX = 768;
const QUERY = `(max-width: ${MOBILE_MAX}px)`;

export function useIsMobile(): boolean {
  return useSyncExternalStore(
    cb => {
      const mq = window.matchMedia(QUERY);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    },
    () => window.matchMedia(QUERY).matches,
  );
}
