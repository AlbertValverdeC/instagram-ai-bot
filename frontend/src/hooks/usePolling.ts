import { useEffect, useRef } from "react";

export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  active: boolean,
) {
  const cbRef = useRef(callback);

  useEffect(() => {
    cbRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!active) {
      return;
    }

    const id = window.setInterval(() => {
      void cbRef.current();
    }, intervalMs);

    return () => window.clearInterval(id);
  }, [active, intervalMs]);
}
