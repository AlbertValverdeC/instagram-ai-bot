import { useCallback, useEffect, useState } from "react";

import { apiClient } from "../api/client";
import { usePolling } from "./usePolling";
import type { SchedulerState, SchedulerConfig } from "../types/scheduler";

export function useScheduler() {
  const [data, setData] = useState<SchedulerState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const result = await apiClient.getScheduler();
      setData(result);
    } catch {
      // keep stale data
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

  return { data, loading, saving, toggle, saveConfig, addItem, removeItem, autoFill, refresh };
}
