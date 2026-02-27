import { useCallback, useEffect, useState } from "react";

import { apiClient } from "../api/client";
import { usePolling } from "./usePolling";
import type { SchedulerState, SchedulerConfig } from "../types/scheduler";

function getErrorStatus(error: unknown): number | undefined {
  const err = error as Error & { status?: number };
  return err.status;
}

function getErrorMessage(error: unknown): string {
  const err = error as Error;
  return err?.message || "No se pudo cargar el programador automático.";
}

export function useScheduler() {
  const [data, setData] = useState<SchedulerState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await apiClient.getScheduler();
      setData(result);
      setError(null);
    } catch (e) {
      if (getErrorStatus(e) === 401) {
        setError("Acceso no autorizado. Configura el token del dashboard.");
      } else {
        setError(getErrorMessage(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  usePolling(refresh, 30_000, true);

  const toggle = useCallback(async () => {
    if (!data) return;
    setSaving(true);
    try {
      await apiClient.saveSchedulerConfig({
        enabled: !data.config.enabled,
        schedule: data.config.schedule,
      });
      await refresh();
    } finally {
      setSaving(false);
    }
  }, [data, refresh]);

  const saveConfig = useCallback(
    async (config: SchedulerConfig) => {
      setSaving(true);
      try {
        await apiClient.saveSchedulerConfig(config);
        await refresh();
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

  const addItem = useCallback(
    async (scheduled_date: string, topic?: string, template?: number, scheduled_time?: string) => {
      setSaving(true);
      try {
        await apiClient.addQueueItem({ scheduled_date, topic, template, scheduled_time });
        await refresh();
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

  const removeItem = useCallback(
    async (id: number) => {
      setSaving(true);
      try {
        await apiClient.removeQueueItem(id);
        await refresh();
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

  const autoFill = useCallback(
    async (days = 7) => {
      setSaving(true);
      try {
        const result = await apiClient.autoFillQueue({ days });
        await refresh();
        return result;
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

  return {
    data,
    loading,
    saving,
    error,
    toggle,
    saveConfig,
    addItem,
    removeItem,
    autoFill,
    refresh,
  };
}
