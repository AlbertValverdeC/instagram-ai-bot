import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient, setApiTokenGetter } from "./api/client";
import { CreatorJourneyPanel } from "./components/journey/CreatorJourneyPanel";
import { TopicCard } from "./components/content/TopicCard";
import { SlidesPreview } from "./components/content/SlidesPreview";
import { Lightbox } from "./components/content/Lightbox";
import { Header } from "./components/layout/Header";
import { MainNavigation } from "./components/layout/MainNavigation";
import type { MainView } from "./components/layout/MainNavigation";
import { KeysModal } from "./components/modals/KeysModal";
import { PromptsModal } from "./components/modals/PromptsModal";
import { SourcesModal } from "./components/modals/SourcesModal";
import { Controls } from "./components/pipeline/Controls";
import { SchedulerPanel } from "./components/scheduler/SchedulerPanel";
import { ActivityMonitor } from "./components/pipeline/ActivityMonitor";
import { PostDetailModal } from "./components/posts/PostDetailModal";
import { PostsHistory } from "./components/posts/PostsHistory";
import { RateLimitBar } from "./components/posts/RateLimitBar";
import { useActivityLog } from "./hooks/useActivityLog";
import { usePipelineState } from "./hooks/usePipelineState";
import type { ApiStateResponse, PostRecord, RateLimitInfo, TextProposal } from "./types";

const API_TOKEN_STORAGE_KEY = "dashboard_api_token";
const BOOTSTRAP_API_TOKEN =
  (import.meta.env.VITE_DASHBOARD_API_TOKEN as string | undefined)?.trim() || "";
const PUBLISH_ESTIMATED_MS = 90_000;

type DraftPublishUiState = {
  status: "publishing" | "success" | "error";
  progress: number;
  error?: string;
  updatedAt: number;
};

// Patterns to parse from incremental E2E pipeline output
const E2E_PATTERNS: Array<{
  key: string;
  regex: RegExp;
  status: "info" | "running" | "success" | "error";
  message: (m: RegExpMatchArray) => string;
}> = [
  {
    key: "s1-start",
    regex: /STEP 1: Research/,
    status: "running",
    message: () => "Investigando temas trending...",
  },
  {
    key: "s1-topic",
    regex: /✓ Topic: (.+)/,
    status: "success",
    message: (m) => `Tema: ${m[1].substring(0, 80)}`,
  },
  {
    key: "s1-viral",
    regex: /Virality: ([\d.]+)\/10/,
    status: "info",
    message: (m) => `Virality score: ${m[1]}/10`,
  },
  {
    key: "s2-start",
    regex: /STEP 2: Content/,
    status: "running",
    message: () => "Generando texto del carrusel...",
  },
  {
    key: "s2-done",
    regex: /✓ Generated (\d+) slides/,
    status: "success",
    message: (m) => `${m[1]} slides de texto generados`,
  },
  {
    key: "s3-start",
    regex: /STEP 3: Design/,
    status: "running",
    message: () => "Diseñando imágenes del carrusel...",
  },
  {
    key: "s3-cover",
    regex: /cover background generated/,
    status: "info",
    message: () => "Fondo de portada IA generado",
  },
  {
    key: "s3-done",
    regex: /✓ Created (\d+) slide images/,
    status: "success",
    message: (m) => `${m[1]} imágenes creadas`,
  },
  {
    key: "s4-start",
    regex: /STEP 4: Engagement/,
    status: "running",
    message: () => "Calculando estrategia de engagement...",
  },
  {
    key: "s4-done",
    regex: /✓ Day type: (\S+)/,
    status: "success",
    message: (m) => `Estrategia: ${m[1]}`,
  },
  {
    key: "s5-start",
    regex: /STEP 5: Publish/,
    status: "running",
    message: () => "Subiendo a Instagram...",
  },
  {
    key: "s5-saved",
    regex: /Saved generated carousel to post store \(id=(\d+)/,
    status: "info",
    message: (m) => `Carrusel guardado en BBDD (id=${m[1]})`,
  },
  {
    key: "s5-ratelimit",
    regex: /Application request limit reached/,
    status: "error",
    message: () => "Meta API rate limit alcanzado, reintentando...",
  },
  {
    key: "s5-recover",
    regex: /post IS live on IG! Recovered media_id=(\S+)/,
    status: "success",
    message: (m) => `Recuperado: post live en IG (${m[1]})`,
  },
  {
    key: "s5-done",
    regex: /✓ Published! Media ID: (\S+)/,
    status: "success",
    message: (m) => `Publicado! Media ID: ${m[1]}`,
  },
  {
    key: "done-history",
    regex: /✓ Saved to history/,
    status: "success",
    message: () => "Guardado en historial",
  },
];

function errorStatus(error: unknown): number | undefined {
  const err = error as Error & { status?: number };
  return err.status;
}

function errorMessage(error: unknown): string {
  const err = error as Error & { body?: Record<string, unknown> };
  const body = err.body || {};
  const base =
    (typeof body.error === "string" && body.error) ||
    (typeof body.error_summary === "string" && body.error_summary) ||
    err.message ||
    "Error desconocido";
  const outputTail = typeof body.output_tail === "string" ? body.output_tail : "";
  if (outputTail) {
    return `${base}\n\nDetalle:\n${outputTail}`;
  }
  return base;
}

function formatWorkspaceTimestamp(value?: string | null): string {
  const text = String(value || "").trim();
  if (!text) return "sin datos";
  try {
    return new Date(text).toLocaleString();
  } catch {
    return text;
  }
}

export default function App() {
  const [apiToken, setApiToken] = useState<string>(
    () => localStorage.getItem(API_TOKEN_STORAGE_KEY) || BOOTSTRAP_API_TOKEN,
  );
  const [tokenInput, setTokenInput] = useState("");

  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [topicInput, setTopicInput] = useState("");

  const [dashboardState, setDashboardState] = useState<ApiStateResponse>({
    topic: null,
    content: null,
    proposals: [],
    slides: [],
    history_count: 0,
  });
  const [slidesCacheBust, setSlidesCacheBust] = useState(Date.now());
  const [proposals, setProposals] = useState<TextProposal[]>([]);
  const [proposalTopics, setProposalTopics] = useState<Record<string, unknown>[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
  const [generatingProposals, setGeneratingProposals] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);

  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [rateLimit, setRateLimit] = useState<RateLimitInfo | null>(null);
  const [postsLoading, setPostsLoading] = useState(true);
  const [dbStatusText, setDbStatusText] = useState("Cargando estado de DB...");
  const [dbStatusColor, setDbStatusColor] = useState<"green" | "orange" | "red" | "dim">("dim");
  const [syncing, setSyncing] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedPost, setSelectedPost] = useState<PostRecord | null>(null);

  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxSlides, setLightboxSlides] = useState<string[]>([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const [keysOpen, setKeysOpen] = useState(false);
  const [promptsOpen, setPromptsOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [activeView, setActiveView] = useState<MainView>("create");
  const [draftPublishUi, setDraftPublishUi] = useState<Record<number, DraftPublishUiState>>({});
  const [clearingWorkspace, setClearingWorkspace] = useState(false);

  const { statusState, running, refreshStatus, setRunningLabel, setStatusState } =
    usePipelineState();
  const {
    entries,
    activeOperation,
    e2eRawOutput,
    pushEntry,
    startOperation,
    endOperation,
    updateE2eRawOutput,
    clearLog,
  } = useActivityLog();
  const prevStatusRef = useRef(statusState.status);
  const seenE2eKeysRef = useRef<Set<string>>(new Set());
  const publishProgressTimersRef = useRef<Record<number, number>>({});

  useEffect(() => {
    setApiTokenGetter(() => apiToken);
  }, [apiToken]);

  useEffect(() => {
    if (!apiToken && BOOTSTRAP_API_TOKEN) {
      setApiToken(BOOTSTRAP_API_TOKEN);
      localStorage.setItem(API_TOKEN_STORAGE_KEY, BOOTSTRAP_API_TOKEN);
      return;
    }
    if (apiToken && localStorage.getItem(API_TOKEN_STORAGE_KEY) !== apiToken) {
      localStorage.setItem(API_TOKEN_STORAGE_KEY, apiToken);
    }
  }, [apiToken]);

  const clearPublishProgressTimer = useCallback((postId: number) => {
    const timer = publishProgressTimersRef.current[postId];
    if (!timer) return;
    window.clearInterval(timer);
    delete publishProgressTimersRef.current[postId];
  }, []);

  const startPublishProgress = useCallback(
    (postId: number) => {
      clearPublishProgressTimer(postId);
      const startedAt = Date.now();
      setDraftPublishUi((prev) => ({
        ...prev,
        [postId]: {
          status: "publishing",
          progress: 6,
          updatedAt: startedAt,
        },
      }));

      const timer = window.setInterval(() => {
        const elapsed = Date.now() - startedAt;
        const nextProgress = Math.min(
          94,
          Math.max(8, Math.round((elapsed / PUBLISH_ESTIMATED_MS) * 88) + 6),
        );
        setDraftPublishUi((prev) => {
          const current = prev[postId];
          if (!current || current.status !== "publishing") {
            return prev;
          }
          if (nextProgress <= current.progress) {
            return prev;
          }
          return {
            ...prev,
            [postId]: {
              ...current,
              progress: nextProgress,
              updatedAt: Date.now(),
            },
          };
        });
      }, 900);

      publishProgressTimersRef.current[postId] = timer;
    },
    [clearPublishProgressTimer],
  );

  useEffect(() => {
    return () => {
      Object.values(publishProgressTimersRef.current).forEach((timer) => {
        window.clearInterval(timer);
      });
      publishProgressTimersRef.current = {};
    };
  }, []);

  const loadDbStatus = useCallback(async () => {
    try {
      const data = await apiClient.getDbStatus();
      if (data.warning) {
        setDbStatusText(`⚠️ ${data.warning}`);
        setDbStatusColor("orange");
        return;
      }
      setDbStatusText(
        `✅ DB ${data.dialect || "unknown"} (${data.persistent_ok ? "persistente" : "no persistente"})`,
      );
      setDbStatusColor("green");
    } catch (error) {
      if (errorStatus(error) === 401) {
        setDbStatusText("Acceso no autorizado. Configura el token del dashboard.");
        setDbStatusColor("orange");
        return;
      }
      setDbStatusText("No se pudo obtener estado de base de datos.");
      setDbStatusColor("orange");
    }
  }, []);

  const loadPosts = useCallback(async () => {
    setPostsLoading(true);
    try {
      const data = await apiClient.getPosts(20);
      setPosts(data.posts || []);
      setRateLimit(data.rate_limit ?? null);
    } catch {
      setPosts([]);
      setRateLimit(null);
    } finally {
      setPostsLoading(false);
    }
  }, []);

  const loadState = useCallback(async () => {
    try {
      const data = await apiClient.getState();
      setDashboardState(data);
      setProposals(Array.isArray(data.proposals) ? data.proposals : []);
      setSlidesCacheBust(Date.now());
      await Promise.all([loadDbStatus(), loadPosts()]);
    } catch (error) {
      if (errorStatus(error) === 401) {
        setDashboardState({
          topic: null,
          content: null,
          proposals: [],
          slides: [],
          history_count: 0,
        });
        setProposals([]);
        setPosts([]);
        setDbStatusText("Acceso no autorizado. Configura el token del dashboard.");
        setDbStatusColor("orange");
      }
    }
  }, [loadDbStatus, loadPosts]);

  const clearWorkspaceSession = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = Boolean(options?.silent);
      setClearingWorkspace(true);
      if (!silent) {
        pushEntry("running", "Limpiando sesión de trabajo actual...", null);
      }
      try {
        const data = await apiClient.clearWorkspace();
        if (!silent) {
          pushEntry(
            "success",
            `Sesión limpia. Archivos: ${data.cleared_files.length}, slides: ${data.cleared_slides}.`,
            null,
          );
        }
        setTopicInput("");
        await loadState();
        return true;
      } catch (error) {
        if (!silent) {
          pushEntry("error", `No se pudo limpiar sesión: ${errorMessage(error)}`, null);
        }
        return false;
      } finally {
        setClearingWorkspace(false);
      }
    },
    [loadState, pushEntry],
  );

  useEffect(() => {
    void loadState();
    void refreshStatus();
  }, [loadState, refreshStatus]);

  useEffect(() => {
    const prev = prevStatusRef.current;
    const next = statusState.status;
    if (prev === "running" && (next === "done" || next === "error")) {
      void loadState();
    }
    prevStatusRef.current = next;
  }, [statusState.status, loadState]);

  // E2E bridge: observe pipeline status transitions
  useEffect(() => {
    const prev = prevStatusRef.current;
    const next = statusState.status;

    if (prev !== "running" && next === "running") {
      seenE2eKeysRef.current.clear();
      startOperation(4, statusState.mode || "Pipeline E2E");
      pushEntry("running", `Pipeline ${statusState.mode || "E2E"} iniciado...`, 4);
    }
    if (prev === "running" && next === "done") {
      const elapsed = statusState.elapsed ? `${statusState.elapsed}s` : "";
      pushEntry("success", `Pipeline completado ${elapsed}`.trim(), 4);
      endOperation();
    }
    if (prev === "running" && next === "error") {
      pushEntry("error", statusState.error_summary || "Error en pipeline", 4);
      endOperation();
    }
  }, [
    statusState.status,
    statusState.mode,
    statusState.elapsed,
    statusState.error_summary,
    pushEntry,
    startOperation,
    endOperation,
  ]);

  // E2E bridge: parse incremental output for step-by-step entries
  useEffect(() => {
    const output = statusState.output;
    if (output) {
      updateE2eRawOutput(output);
    }

    if (statusState.status !== "running" || !output) return;

    const seen = seenE2eKeysRef.current;
    for (const pat of E2E_PATTERNS) {
      if (seen.has(pat.key)) continue;
      const match = output.match(pat.regex);
      if (match) {
        seen.add(pat.key);
        pushEntry(pat.status, pat.message(match), 4);
      }
    }
  }, [statusState.output, statusState.status, pushEntry, updateE2eRawOutput]);

  useEffect(() => {
    if (proposals.length === 0) {
      setSelectedProposalId(null);
      return;
    }
    const stillExists =
      selectedProposalId && proposals.some((p) => String(p.id) === selectedProposalId);
    if (!stillExists) {
      setSelectedProposalId(String(proposals[0].id || "p1"));
    }
  }, [proposals, selectedProposalId]);

  const run = useCallback(
    async (mode: "test" | "dry-run" | "live") => {
      if (
        mode === "live" &&
        !window.confirm("¿Ejecutar en modo LIVE?\nEsto publicará en Instagram.")
      ) {
        return;
      }

      setRunningLabel(mode);
      const payload: { mode: "test" | "dry-run" | "live"; template?: number; topic?: string } = {
        mode,
      };
      const topic = topicInput.trim();
      if (topic) {
        payload.topic = topic;
      }
      if (selectedTemplate !== null) {
        payload.template = selectedTemplate;
      }

      try {
        const result = await apiClient.runPipeline(payload);
        if (result.status !== "started") {
          await refreshStatus();
        }
      } catch (error) {
        setStatusState({
          status: "error",
          output: `Error: ${errorMessage(error)}`,
          error_summary: errorMessage(error),
          mode,
          elapsed: null,
        });
      }
    },
    [refreshStatus, selectedTemplate, setRunningLabel, setStatusState, topicInput],
  );

  const searchTopicOnly = useCallback(async () => {
    const topic = topicInput.trim();
    if (!topic) {
      window.alert("Escribe un tema primero.");
      return;
    }

    setRunningLabel("research-only");

    try {
      const result = await apiClient.searchTopic(topic);
      if (result.status !== "started") {
        await refreshStatus();
      }
    } catch (error) {
      setStatusState({
        status: "error",
        output: `Error: ${errorMessage(error)}`,
        error_summary: errorMessage(error),
        mode: "research-only",
        elapsed: null,
      });
    }
  }, [refreshStatus, setRunningLabel, setStatusState, topicInput]);

  const generateProposals = useCallback(async () => {
    setGeneratingProposals(true);
    startOperation(1, "Generando propuestas");
    pushEntry("running", "Buscando noticias y creando propuestas...", 1);
    const t0 = Date.now();
    try {
      const topic = topicInput.trim();
      const data = await apiClient.generateProposals({ topic: topic || undefined, count: 3 });
      const nextProposals = Array.isArray(data.proposals) ? data.proposals : [];
      const nextTopics = Array.isArray(data.topics) ? data.topics : data.topic ? [data.topic] : [];
      setDashboardState((prev) => ({ ...prev, topic: data.topic }));
      setProposals(nextProposals);
      setProposalTopics(nextTopics as Record<string, unknown>[]);
      setSelectedProposalId(nextProposals.length > 0 ? String(nextProposals[0].id || "p1") : null);
      const dur = Math.round((Date.now() - t0) / 1000);
      pushEntry("success", `${nextProposals.length} propuestas generadas en ${dur}s`, 1);
      endOperation();
      await Promise.all([loadPosts(), loadDbStatus()]);
    } catch (error) {
      pushEntry("error", `Error al generar propuestas: ${errorMessage(error)}`, 1);
      endOperation();
    } finally {
      setGeneratingProposals(false);
    }
  }, [loadDbStatus, loadPosts, topicInput, pushEntry, startOperation, endOperation]);

  const createDraftFromProposal = useCallback(async () => {
    if (!dashboardState.topic) {
      window.alert("Primero genera propuestas.");
      return;
    }
    const selectedIndex = proposals.findIndex((p) => String(p.id) === selectedProposalId);
    const selected = selectedIndex >= 0 ? proposals[selectedIndex] : undefined;
    if (!selected) {
      window.alert("Selecciona una propuesta.");
      return;
    }

    // Use the corresponding topic for this proposal (each proposal = different topic)
    const matchingTopic = (proposalTopics[selectedIndex] || dashboardState.topic) as Record<
      string,
      unknown
    >;

    setCreatingDraft(true);
    startOperation(2, "Creando draft y slides");
    pushEntry("running", "Creando draft y slides...", 2);
    const t0 = Date.now();
    try {
      const data = await apiClient.createDraft({
        topic: matchingTopic,
        proposal: selected,
        template: selectedTemplate ?? undefined,
      });
      setDashboardState((prev) => ({
        ...prev,
        topic: data.topic,
        content: data.content,
        slides: data.slides,
      }));
      setSlidesCacheBust(Date.now());
      const dur = Math.round((Date.now() - t0) / 1000);
      pushEntry("success", `Draft #${data.post_id} guardado en ${dur}s`, 2);
      endOperation();
      await loadPosts();
    } catch (error) {
      pushEntry("error", `Error al crear borrador: ${errorMessage(error)}`, 2);
      endOperation();
    } finally {
      setCreatingDraft(false);
    }
  }, [
    dashboardState.topic,
    proposals,
    proposalTopics,
    selectedProposalId,
    selectedTemplate,
    loadPosts,
    pushEntry,
    startOperation,
    endOperation,
  ]);

  const syncNow = useCallback(async () => {
    setSyncing(true);
    pushEntry("running", "Sincronizando estado + métricas de Instagram...", null);
    try {
      const data = await apiClient.syncInstagram(30);
      const checked = data.checked ?? 0;
      const updated = data.updated ?? 0;
      const failed = data.failed ?? 0;
      const pendingChecked = data.pending_checked ?? 0;
      const pendingReconciled = data.pending_reconciled ?? 0;
      const importCreated = Number(data.import_created ?? 0);
      const importExisting = Number(data.import_existing ?? 0);
      const partial = Boolean(data.partial || data.timed_out);
      const remaining = Number(data.remaining ?? 0);
      const elapsed = Number(data.elapsed_seconds ?? 0);
      const importSuffix =
        importCreated > 0 || importExisting > 0
          ? ` Importados ${importCreated} nuevos (${importExisting} ya existentes).`
          : "";
      const partialSuffix = partial
        ? ` Parcial por tiempo (${elapsed || "?"}s), quedan ${remaining} posts pendientes.`
        : "";
      pushEntry(
        failed > 0 ? "error" : "success",
        `Sync IG: revisados ${checked}, actualizados ${updated}, fallidos ${failed}. Pendientes revisados ${pendingChecked}, reconciliados ${pendingReconciled}.${importSuffix}${partialSuffix}`,
        null,
      );
      await loadPosts();
    } catch (error) {
      pushEntry("error", `Sync falló: ${errorMessage(error)}`, null);
    } finally {
      setSyncing(false);
    }
  }, [loadPosts, pushEntry]);

  const publishDraft = useCallback(
    async (postId: number): Promise<boolean> => {
      if (!window.confirm(`¿Publicar draft #${postId} en Instagram ahora?`)) {
        return false;
      }
      startPublishProgress(postId);
      startOperation(3, `Publicando draft #${postId}`);
      pushEntry("running", `Publicando draft #${postId}...`, 3);
      const t0 = Date.now();
      let success = false;
      try {
        const data = await apiClient.publishPost(postId);
        const dur = Math.round((Date.now() - t0) / 1000);
        clearPublishProgressTimer(postId);
        setDraftPublishUi((prev) => ({
          ...prev,
          [postId]: {
            status: "success",
            progress: 100,
            updatedAt: Date.now(),
          },
        }));
        window.setTimeout(() => {
          setDraftPublishUi((prev) => {
            const current = prev[postId];
            if (!current || current.status !== "success") return prev;
            const { [postId]: _, ...rest } = prev;
            return rest;
          });
        }, 6000);
        pushEntry(
          "success",
          `Draft #${postId} publicado en ${dur}s → Media ID ${data.media_id || "-"}`,
          3,
        );
        success = true;
      } catch (error) {
        clearPublishProgressTimer(postId);
        setDraftPublishUi((prev) => ({
          ...prev,
          [postId]: {
            status: "error",
            progress: 100,
            error: errorMessage(error),
            updatedAt: Date.now(),
          },
        }));
        pushEntry("error", `Error al publicar (#${postId}): ${errorMessage(error)}`, 3);
      } finally {
        endOperation();
        await loadPosts();
      }
      return success;
    },
    [loadPosts, pushEntry, startOperation, endOperation, startPublishProgress, clearPublishProgressTimer],
  );

  const retryPublish = useCallback(
    async (postId: number) => {
      if (!window.confirm(`¿Reintentar publicación del post #${postId}?`)) {
        return;
      }
      startOperation(3, `Reintentando #${postId}`);
      pushEntry("running", `Reintentando publicación de #${postId}...`, 3);
      const t0 = Date.now();
      try {
        const data = await apiClient.retryPublish(postId);
        const reconciled = Boolean((data as { reconciled?: boolean }).reconciled);
        const dur = Math.round((Date.now() - t0) / 1000);
        pushEntry(
          "success",
          reconciled
            ? `Reconciliado OK (#${postId}) en ${dur}s → Media ID ${data.media_id || "-"}`
            : `Reintento OK (#${postId}) en ${dur}s → Media ID ${data.media_id || "-"}`,
          3,
        );
        endOperation();
      } catch (error) {
        pushEntry("error", `Reintento falló (#${postId}): ${errorMessage(error)}`, 3);
        endOperation();
      } finally {
        await loadPosts();
      }
    },
    [loadPosts, pushEntry, startOperation, endOperation],
  );

  const openPostDetail = useCallback(async (postId: number) => {
    setDetailOpen(true);
    setDetailLoading(true);
    try {
      const data = await apiClient.getPostDetail(postId);
      setSelectedPost(data.post || null);
    } catch {
      setSelectedPost(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const saveToken = () => {
    const token = tokenInput.trim();
    if (!token) {
      window.alert("Introduce un token antes de guardar.");
      return;
    }
    localStorage.setItem(API_TOKEN_STORAGE_KEY, token);
    setApiToken(token);
    setTokenInput("");
  };

  const clearToken = () => {
    localStorage.removeItem(API_TOKEN_STORAGE_KEY);
    setApiToken("");
    setTokenInput("");
  };

  const openLightbox = (slides: string[], index: number) => {
    setLightboxSlides(slides);
    setLightboxIndex(index);
    setLightboxOpen(true);
  };

  const publishingDraft = Object.values(draftPublishUi).some((state) => state.status === "publishing");
  const flowBusy = running || generatingProposals || creatingDraft || publishingDraft;
  const scheduledCount = posts.filter((post) => String(post.status || "") === "generated").length;
  const publishedCount = posts.filter((post) => {
    const status = String(post.status || "");
    return status === "published" || status === "published_active";
  }).length;
  const draftsPendingPublish = posts.filter((post) => String(post.status || "") === "draft").length;
  const latestDraftId = posts.find((post) => String(post.status || "") === "draft")?.id ?? null;
  const latestEntry = entries.length > 0 ? entries[entries.length - 1] : null;
  const workspaceHasData = Boolean(
    dashboardState.workspace_has_data ||
      dashboardState.topic ||
      dashboardState.content ||
      (dashboardState.slides || []).length > 0 ||
      proposals.length > 0,
  );
  const workspaceUpdatedLabel = formatWorkspaceTimestamp(dashboardState.workspace_updated_at);
  const publishLatestDraft = useCallback(async () => {
    if (!latestDraftId) {
      window.alert("No hay borradores pendientes para publicar.");
      return;
    }
    const published = await publishDraft(latestDraftId);
    if (published) {
      const cleared = await clearWorkspaceSession({ silent: true });
      if (cleared) {
        pushEntry("success", "Proyecto publicado. Sesión de trabajo limpiada automáticamente.", null);
      }
    }
  }, [latestDraftId, publishDraft, clearWorkspaceSession, pushEntry]);
  const tokenConfigured = !!apiToken.trim();

  return (
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-background-dark font-body text-slate-100">
      <Header
        status={statusState.status}
        tokenConfigured={tokenConfigured}
        tokenInput={tokenInput}
        onTokenInputChange={setTokenInput}
        onSaveToken={saveToken}
        onClearToken={clearToken}
        onOpenSources={() => setSourcesOpen(true)}
        onOpenPrompts={() => setPromptsOpen(true)}
        onOpenKeys={() => setKeysOpen(true)}
      />
      <MainNavigation activeView={activeView} onChange={setActiveView} />

      {activeView === "create" && (
        <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-4 p-4 pb-24 sm:p-6 sm:pb-24 lg:p-10 lg:pb-12">
          <section className="rounded-xl border border-border-dark bg-secondary-dark p-3">
            <p className="text-sm font-semibold text-white">Sesión de trabajo actual</p>
            <p className="mt-0.5 text-xs text-text-subtle">
              1) Encuentra temática (manual o automática) 2) Elige propuesta 3) Crea borrador 4)
              Publica o déjalo en historial.
            </p>
            <div className="mt-2 rounded-lg border border-border-dark bg-surface-dark/40 px-3 py-2">
              <p className="text-[11px] text-text-subtle">
                Lo de “Tema actual” y “Slides” viene de esta sesión local (archivos `last_*` + `slide_*`).
              </p>
              <p className="mt-1 text-[11px] text-text-subtle">
                Estado:{" "}
                <span className={`font-semibold ${workspaceHasData ? "text-white" : "text-text-subtle"}`}>
                  {workspaceHasData ? "con datos en sesión" : "sesión vacía"}
                </span>{" "}
                · Última edición: <span className="text-primary">{workspaceUpdatedLabel}</span>
              </p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-wide text-text-subtle">Propuestas</p>
                <p className="text-sm font-semibold text-white">{proposals.length}</p>
              </div>
              <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-wide text-text-subtle">Borradores</p>
                <p className="text-sm font-semibold text-white">{draftsPendingPublish}</p>
              </div>
              <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-wide text-text-subtle">Programados</p>
                <p className="text-sm font-semibold text-white">{scheduledCount}</p>
              </div>
              <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-wide text-text-subtle">Publicados</p>
                <p className="text-sm font-semibold text-white">{publishedCount}</p>
              </div>
            </div>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() => setActiveView("schedule")}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-xs font-semibold text-text-subtle transition hover:border-primary/35 hover:text-white"
              >
                <span className="material-symbols-outlined text-[16px]">event_upcoming</span>
                Ir a Programador
              </button>
              <button
                type="button"
                onClick={() => setActiveView("history")}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-xs font-semibold text-text-subtle transition hover:border-primary/35 hover:text-white"
              >
                <span className="material-symbols-outlined text-[16px]">history</span>
                Ir a Historial
              </button>
              <button
                type="button"
                onClick={() => void clearWorkspaceSession()}
                disabled={clearingWorkspace || flowBusy || !workspaceHasData}
                data-loading={clearingWorkspace ? "true" : undefined}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-xs font-semibold text-text-subtle transition hover:border-primary/35 hover:text-white disabled:opacity-40"
              >
                <span className="material-symbols-outlined text-[16px]">ink_eraser</span>
                Limpiar sesión
              </button>
            </div>
          </section>

          <CreatorJourneyPanel
            busy={flowBusy}
            topic={topicInput}
            proposals={proposals}
            selectedProposalId={selectedProposalId}
            generatingProposals={generatingProposals}
            creatingDraft={creatingDraft}
            publishingDraft={publishingDraft}
            draftCount={draftsPendingPublish}
            onTopicChange={setTopicInput}
            onFindTopics={() => void generateProposals()}
            onSelectProposal={setSelectedProposalId}
            onCreateDraft={() => void createDraftFromProposal()}
            onPublishLatestDraft={() => void publishLatestDraft()}
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="space-y-4 lg:col-span-7">
              <SlidesPreview
                slides={dashboardState.slides}
                cacheBust={slidesCacheBust}
                onOpen={openLightbox}
              />
            </div>
            <div className="space-y-4 lg:col-span-5">
              <TopicCard topic={dashboardState.topic} />
              <RateLimitBar rateLimit={rateLimit} />
            </div>
          </div>

          <section className="rounded-xl border border-border-dark bg-secondary-dark">
            <button
              type="button"
              onClick={() => setAdvancedOpen((prev) => !prev)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <div>
                <p className="font-display text-sm font-semibold text-white">Modo avanzado</p>
                <p className="text-xs text-text-subtle">
                  Test mode, dry run, e2e live, templates y research directo.
                </p>
              </div>
              <span
                className={`material-symbols-outlined text-text-subtle transition-transform ${advancedOpen ? "rotate-180" : ""}`}
              >
                expand_more
              </span>
            </button>
            {advancedOpen && (
              <div className="border-t border-border-dark p-4">
                <Controls
                  running={running || generatingProposals || creatingDraft}
                  topic={topicInput}
                  selectedTemplate={selectedTemplate}
                  onTopicChange={setTopicInput}
                  onSelectTemplate={setSelectedTemplate}
                  onRun={run}
                  onSearchTopic={searchTopicOnly}
                />
              </div>
            )}
          </section>

          <section className="rounded-xl border border-border-dark bg-secondary-dark">
            <button
              type="button"
              onClick={() => setActivityOpen((prev) => !prev)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <div>
                <p className="font-display text-sm font-semibold text-white">Actividad y debug</p>
                <p className="text-xs text-text-subtle">
                  {latestEntry
                    ? `Último evento: ${latestEntry.message}`
                    : "Sin actividad todavía. Aquí verás progreso y errores."}
                </p>
              </div>
              <span
                className={`material-symbols-outlined text-text-subtle transition-transform ${activityOpen ? "rotate-180" : ""}`}
              >
                expand_more
              </span>
            </button>
            {activityOpen && (
              <div className="border-t border-border-dark">
                <ActivityMonitor
                  entries={entries}
                  activeOperation={activeOperation}
                  e2eRawOutput={e2eRawOutput}
                  onClear={clearLog}
                />
              </div>
            )}
          </section>
        </main>
      )}

      {activeView === "schedule" && (
        <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-4 p-4 pb-24 sm:p-6 sm:pb-24 lg:p-10 lg:pb-12">
          <section className="rounded-xl border border-border-dark bg-secondary-dark p-3">
            <p className="text-sm font-semibold text-white">Programador automático</p>
            <p className="mt-0.5 text-xs text-text-subtle">
              Configura días, horas y número de publicaciones por día. Todo lo programado se gestiona
              desde aquí.
            </p>
          </section>
          <SchedulerPanel />
        </main>
      )}

      {activeView === "history" && (
        <main className="w-full flex-1 pb-24 md:pb-12">
          <PostsHistory
            posts={posts}
            loading={postsLoading}
            dbStatusText={dbStatusText}
            dbStatusColor={dbStatusColor}
            publishUi={draftPublishUi}
            syncing={syncing}
            onSync={syncNow}
            onPublish={publishDraft}
            onRetry={retryPublish}
            onOpen={openPostDetail}
          />
        </main>
      )}

      <MainNavigation activeView={activeView} onChange={setActiveView} mobile />

      <Lightbox
        open={lightboxOpen}
        slides={lightboxSlides}
        index={lightboxIndex}
        cacheBust={slidesCacheBust}
        onClose={() => setLightboxOpen(false)}
        onPrev={() =>
          setLightboxIndex(
            (prev) => (prev - 1 + lightboxSlides.length) % Math.max(1, lightboxSlides.length),
          )
        }
        onNext={() => setLightboxIndex((prev) => (prev + 1) % Math.max(1, lightboxSlides.length))}
      />

      <KeysModal open={keysOpen} onClose={() => setKeysOpen(false)} />
      <PromptsModal open={promptsOpen} onClose={() => setPromptsOpen(false)} />
      <SourcesModal open={sourcesOpen} onClose={() => setSourcesOpen(false)} />
      <PostDetailModal
        open={detailOpen}
        post={selectedPost}
        loading={detailLoading}
        onClose={() => setDetailOpen(false)}
        onPublish={publishDraft}
      />
    </div>
  );
}
