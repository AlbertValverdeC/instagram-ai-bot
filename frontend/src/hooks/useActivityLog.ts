import { useCallback, useRef, useState } from "react";

import type { ActivityEntry, ActivityEntryStatus } from "../types/activity";

let entryCounter = 0;

interface ActiveOperation {
  level: 1 | 2 | 3 | 4;
  label: string;
  startedAt: number;
}

export function useActivityLog() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [activeOperation, setActiveOperation] = useState<ActiveOperation | null>(null);
  const [e2eRawOutput, setE2eRawOutput] = useState("");
  const activeOpRef = useRef<ActiveOperation | null>(null);

  const pushEntry = useCallback(
    (
      status: ActivityEntryStatus,
      message: string,
      level?: 1 | 2 | 3 | 4 | null,
      detail?: string,
    ) => {
      const entry: ActivityEntry = {
        id: `ae-${++entryCounter}`,
        timestamp: new Date(),
        status,
        level: level ?? null,
        message,
        detail,
      };
      setEntries((prev) => [...prev, entry]);
    },
    [],
  );

  const startOperation = useCallback((level: 1 | 2 | 3 | 4, label: string) => {
    const op: ActiveOperation = { level, label, startedAt: Date.now() };
    activeOpRef.current = op;
    setActiveOperation(op);
  }, []);

  const endOperation = useCallback(() => {
    activeOpRef.current = null;
    setActiveOperation(null);
  }, []);

  const updateE2eRawOutput = useCallback((output: string) => {
    setE2eRawOutput(output);
  }, []);

  const clearLog = useCallback(() => {
    setEntries([]);
    setActiveOperation(null);
    activeOpRef.current = null;
    setE2eRawOutput("");
  }, []);

  return {
    entries,
    activeOperation,
    e2eRawOutput,
    pushEntry,
    startOperation,
    endOperation,
    updateE2eRawOutput,
    clearLog,
  };
}
