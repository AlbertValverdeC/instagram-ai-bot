import { useCallback, useMemo, useState } from "react";

import { apiClient } from "../api/client";
import { usePolling } from "./usePolling";
import type { ApiStatusResponse, PipelineStatus } from "../types";

const INITIAL_STATUS: ApiStatusResponse = {
  status: "idle",
  output: "Listo. Selecciona un modo y haz click para ejecutar el pipeline.",
  error_summary: null,
  mode: null,
  elapsed: null,
};

export function usePipelineState() {
  const [statusState, setStatusState] = useState<ApiStatusResponse>(INITIAL_STATUS);

  const refreshStatus = useCallback(async () => {
    try {
      const next = await apiClient.getStatus();
      setStatusState(next);
    } catch (error) {
      const err = error as Error & { status?: number };
      if (err.status === 401) {
        setStatusState({
          status: "error",
          output: "Error: Unauthorized. Configura el token en la parte superior derecha.",
          error_summary: "Unauthorized",
          mode: null,
          elapsed: null,
        });
        return;
      }
      setStatusState((prev) => ({
        ...prev,
        status: "error",
        output: prev.output || `Error de conexión: ${err.message}`,
        error_summary: err.message,
      }));
    }
  }, []);

  const running = statusState.status === "running";
  usePolling(refreshStatus, 1500, running);

  const setRunningLabel = useCallback((modeLabel: string) => {
    setStatusState({
      status: "running",
      output: `Iniciando pipeline (${modeLabel})...\n`,
      error_summary: null,
      mode: modeLabel,
      elapsed: null,
    });
  }, []);

  const mergedStatus = useMemo(() => {
    const status = statusState.status as PipelineStatus;
    return {
      ...statusState,
      status,
      output: statusState.output || "Esperando output...",
    };
  }, [statusState]);

  return {
    statusState: mergedStatus,
    running,
    refreshStatus,
    setRunningLabel,
    setStatusState,
  };
}
