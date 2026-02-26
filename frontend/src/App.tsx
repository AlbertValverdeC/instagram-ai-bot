import { useCallback, useEffect, useRef, useState } from 'react';

import { apiClient, setApiTokenGetter } from './api/client';
import { ProposalSelector } from './components/content/ProposalSelector';
import { TopicCard } from './components/content/TopicCard';
import { SlidesPreview } from './components/content/SlidesPreview';
import { Lightbox } from './components/content/Lightbox';
import { Header } from './components/layout/Header';
import { KeysModal } from './components/modals/KeysModal';
import { PromptsModal } from './components/modals/PromptsModal';
import { SourcesModal } from './components/modals/SourcesModal';
import { Controls } from './components/pipeline/Controls';
import { ConsoleOutput } from './components/pipeline/ConsoleOutput';
import { PostDetailModal } from './components/posts/PostDetailModal';
import { PostsHistory } from './components/posts/PostsHistory';
import { usePipelineState } from './hooks/usePipelineState';
import type { ApiStateResponse, PostRecord, TextProposal } from './types';

const API_TOKEN_STORAGE_KEY = 'dashboard_api_token';

function errorStatus(error: unknown): number | undefined {
  const err = error as Error & { status?: number };
  return err.status;
}

function errorMessage(error: unknown): string {
  const err = error as Error & { body?: Record<string, unknown> };
  const body = err.body || {};
  const base =
    (typeof body.error === 'string' && body.error) ||
    (typeof body.error_summary === 'string' && body.error_summary) ||
    err.message ||
    'Error desconocido';
  const outputTail = typeof body.output_tail === 'string' ? body.output_tail : '';
  if (outputTail) {
    return `${base}\n\nDetalle:\n${outputTail}`;
  }
  return base;
}

export default function App() {
  const [apiToken, setApiToken] = useState<string>(() => localStorage.getItem(API_TOKEN_STORAGE_KEY) || '');
  const [tokenInput, setTokenInput] = useState('');

  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [topicInput, setTopicInput] = useState('');

  const [dashboardState, setDashboardState] = useState<ApiStateResponse>({
    topic: null,
    content: null,
    proposals: [],
    slides: [],
    history_count: 0
  });
  const [slidesCacheBust, setSlidesCacheBust] = useState(Date.now());
  const [proposals, setProposals] = useState<TextProposal[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
  const [generatingProposals, setGeneratingProposals] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);

  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [postsLoading, setPostsLoading] = useState(true);
  const [dbStatusText, setDbStatusText] = useState('Cargando estado de DB...');
  const [dbStatusColor, setDbStatusColor] = useState<'green' | 'orange' | 'red' | 'dim'>('dim');
  const [syncMessage, setSyncMessage] = useState('');
  const [syncColor, setSyncColor] = useState<'green' | 'orange' | 'red' | 'dim'>('dim');
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

  const { statusState, running, refreshStatus, setRunningLabel, setStatusState } = usePipelineState();
  const prevStatusRef = useRef(statusState.status);

  useEffect(() => {
    setApiTokenGetter(() => apiToken);
  }, [apiToken]);

  const loadDbStatus = useCallback(async () => {
    try {
      const data = await apiClient.getDbStatus();
      if (data.warning) {
        setDbStatusText(`⚠️ ${data.warning}`);
        setDbStatusColor('orange');
        return;
      }
      setDbStatusText(`✅ DB ${data.dialect || 'unknown'} (${data.persistent_ok ? 'persistente' : 'no persistente'})`);
      setDbStatusColor('green');
    } catch (error) {
      if (errorStatus(error) === 401) {
        setDbStatusText('Acceso no autorizado. Configura el token del dashboard.');
        setDbStatusColor('orange');
        return;
      }
      setDbStatusText('No se pudo obtener estado de base de datos.');
      setDbStatusColor('orange');
    }
  }, []);

  const loadPosts = useCallback(async () => {
    setPostsLoading(true);
    try {
      const data = await apiClient.getPosts(20);
      setPosts(data.posts || []);
    } catch {
      setPosts([]);
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
        setDashboardState({ topic: null, content: null, proposals: [], slides: [], history_count: 0 });
        setProposals([]);
        setPosts([]);
        setDbStatusText('Acceso no autorizado. Configura el token del dashboard.');
        setDbStatusColor('orange');
      }
    }
  }, [loadDbStatus, loadPosts]);

  useEffect(() => {
    void loadState();
    void refreshStatus();
  }, [loadState, refreshStatus]);

  useEffect(() => {
    const prev = prevStatusRef.current;
    const next = statusState.status;
    if (prev === 'running' && (next === 'done' || next === 'error')) {
      void loadState();
    }
    prevStatusRef.current = next;
  }, [statusState.status, loadState]);

  useEffect(() => {
    if (proposals.length === 0) {
      setSelectedProposalId(null);
      return;
    }
    const stillExists = selectedProposalId && proposals.some((p) => String(p.id) === selectedProposalId);
    if (!stillExists) {
      setSelectedProposalId(String(proposals[0].id || 'p1'));
    }
  }, [proposals, selectedProposalId]);

  const run = useCallback(
    async (mode: 'test' | 'dry-run' | 'live') => {
      if (mode === 'live' && !window.confirm('¿Ejecutar en modo LIVE?\nEsto publicará en Instagram.')) {
        return;
      }

      setRunningLabel(mode);
      const payload: { mode: 'test' | 'dry-run' | 'live'; template?: number; topic?: string } = { mode };
      const topic = topicInput.trim();
      if (topic) {
        payload.topic = topic;
      }
      if (selectedTemplate !== null) {
        payload.template = selectedTemplate;
      }

      try {
        const result = await apiClient.runPipeline(payload);
        if (result.status !== 'started') {
          await refreshStatus();
        }
      } catch (error) {
        setStatusState({
          status: 'error',
          output: `Error: ${errorMessage(error)}`,
          error_summary: errorMessage(error),
          mode,
          elapsed: null
        });
      }
    },
    [refreshStatus, selectedTemplate, setRunningLabel, setStatusState, topicInput]
  );

  const searchTopicOnly = useCallback(async () => {
    const topic = topicInput.trim();
    if (!topic) {
      window.alert('Escribe un tema primero.');
      return;
    }

    setRunningLabel('research-only');

    try {
      const result = await apiClient.searchTopic(topic);
      if (result.status !== 'started') {
        await refreshStatus();
      }
    } catch (error) {
      setStatusState({
        status: 'error',
        output: `Error: ${errorMessage(error)}`,
        error_summary: errorMessage(error),
        mode: 'research-only',
        elapsed: null
      });
    }
  }, [refreshStatus, setRunningLabel, setStatusState, topicInput]);

  const generateProposals = useCallback(async () => {
    setGeneratingProposals(true);
    setSyncMessage('Nivel 1 en ejecución: buscando noticias y creando propuestas...');
    setSyncColor('dim');
    try {
      const topic = topicInput.trim();
      const data = await apiClient.generateProposals({ topic: topic || undefined, count: 3 });
      const nextProposals = Array.isArray(data.proposals) ? data.proposals : [];
      setDashboardState((prev) => ({ ...prev, topic: data.topic }));
      setProposals(nextProposals);
      setSelectedProposalId(nextProposals.length > 0 ? String(nextProposals[0].id || 'p1') : null);
      setSyncMessage(`Nivel 1 completado: ${nextProposals.length} propuestas generadas.`);
      setSyncColor('green');
      await Promise.all([loadPosts(), loadDbStatus()]);
    } catch (error) {
      setSyncMessage(`Nivel 1 falló: ${errorMessage(error)}`);
      setSyncColor('red');
    } finally {
      setGeneratingProposals(false);
    }
  }, [loadDbStatus, loadPosts, topicInput]);

  const createDraftFromProposal = useCallback(async () => {
    if (!dashboardState.topic) {
      window.alert('Primero genera propuestas (Nivel 1).');
      return;
    }
    const selected = proposals.find((p) => String(p.id) === selectedProposalId);
    if (!selected) {
      window.alert('Selecciona una propuesta.');
      return;
    }

    setCreatingDraft(true);
    setSyncMessage('Nivel 2 en ejecución: creando draft y slides...');
    setSyncColor('dim');
    try {
      const data = await apiClient.createDraft({
        topic: dashboardState.topic as Record<string, unknown>,
        proposal: selected,
        template: selectedTemplate ?? undefined
      });
      setDashboardState((prev) => ({
        ...prev,
        topic: data.topic,
        content: data.content,
        slides: data.slides
      }));
      setSlidesCacheBust(Date.now());
      setSyncMessage(`Nivel 2 completado: draft #${data.post_id} guardado en BBDD.`);
      setSyncColor('green');
      await loadPosts();
    } catch (error) {
      setSyncMessage(`Nivel 2 falló: ${errorMessage(error)}`);
      setSyncColor('red');
    } finally {
      setCreatingDraft(false);
    }
  }, [dashboardState.topic, proposals, selectedProposalId, selectedTemplate, loadPosts]);

  const syncNow = useCallback(async () => {
    setSyncing(true);
    setSyncMessage('Sincronizando estado + métricas de Instagram...');
    setSyncColor('dim');
    try {
      const data = await apiClient.syncInstagram(30);
      const checked = data.checked ?? 0;
      const updated = data.updated ?? 0;
      const failed = data.failed ?? 0;
      const pendingChecked = data.pending_checked ?? 0;
      const pendingReconciled = data.pending_reconciled ?? 0;
      setSyncMessage(
        `Sync IG completado: revisados ${checked}, actualizados ${updated}, fallidos ${failed}. ` +
          `Pendientes revisados ${pendingChecked}, reconciliados ${pendingReconciled}.`
      );
      setSyncColor(failed > 0 ? 'orange' : 'green');
      await loadPosts();
    } catch (error) {
      setSyncMessage(errorMessage(error));
      setSyncColor('red');
    } finally {
      setSyncing(false);
    }
  }, [loadPosts]);

  const publishDraft = useCallback(
    async (postId: number) => {
      if (!window.confirm(`¿Publicar draft #${postId} en Instagram ahora?`)) {
        return;
      }
      setSyncMessage(`Nivel 3 en ejecución: publicando draft #${postId}...`);
      setSyncColor('dim');
      try {
        const data = await apiClient.publishPost(postId);
        setSyncMessage(`Nivel 3 completado (#${postId}) → Media ID ${data.media_id || '-'}`);
        setSyncColor('green');
        await loadPosts();
      } catch (error) {
        setSyncMessage(`Nivel 3 falló (#${postId}): ${errorMessage(error)}`);
        setSyncColor('red');
      }
    },
    [loadPosts]
  );

  const retryPublish = useCallback(
    async (postId: number) => {
      if (!window.confirm(`¿Reintentar publicación del post #${postId}?`)) {
        return;
      }
      setSyncMessage(`Reintentando publicación de #${postId}...`);
      setSyncColor('dim');
      try {
        const data = await apiClient.retryPublish(postId);
        const reconciled = Boolean((data as { reconciled?: boolean }).reconciled);
        setSyncMessage(
          reconciled
            ? `Reconciliado OK (#${postId}) → Media ID ${data.media_id || '-'}`
            : `Reintento OK (#${postId}) → Media ID ${data.media_id || '-'}`
        );
        setSyncColor('green');
      } catch (error) {
        setSyncMessage(`Reintento falló (#${postId}): ${errorMessage(error)}`);
        setSyncColor('red');
      } finally {
        await loadPosts();
      }
    },
    [loadPosts]
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
      window.alert('Introduce un token antes de guardar.');
      return;
    }
    localStorage.setItem(API_TOKEN_STORAGE_KEY, token);
    setApiToken(token);
    setTokenInput('');
  };

  const clearToken = () => {
    localStorage.removeItem(API_TOKEN_STORAGE_KEY);
    setApiToken('');
    setTokenInput('');
  };

  const openLightbox = (slides: string[], index: number) => {
    setLightboxSlides(slides);
    setLightboxIndex(index);
    setLightboxOpen(true);
  };

  const tokenConfigured = !!apiToken.trim();

  return (
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden bg-background-dark font-display text-slate-100">
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

      <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-8 p-6 lg:p-10">
        <Controls
          running={running || generatingProposals || creatingDraft}
          topic={topicInput}
          selectedTemplate={selectedTemplate}
          onTopicChange={setTopicInput}
          onSelectTemplate={setSelectedTemplate}
          onRun={run}
          onSearchTopic={searchTopicOnly}
        />

        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-dark bg-secondary-dark p-4">
          <div>
            <p className="text-sm font-semibold text-white">Flujo por niveles</p>
            <p className="text-xs text-text-subtle">
              Nivel 1: propuestas, Nivel 2: draft+slides, Nivel 3: publicar draft, Nivel 4: E2E live.
            </p>
          </div>
          <button
            type="button"
            onClick={generateProposals}
            disabled={running || generatingProposals || creatingDraft}
            className="rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-background-dark transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {generatingProposals ? 'Nivel 1 en curso...' : 'Nivel 1 · Generar propuestas'}
          </button>
        </section>

        <ProposalSelector
          proposals={proposals}
          selectedId={selectedProposalId}
          loading={generatingProposals}
          creatingDraft={creatingDraft}
          onSelect={setSelectedProposalId}
          onCreateDraft={createDraftFromProposal}
        />

        {/* Content Grid: Topic+Console left, Slides right */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          <div className="flex flex-col gap-6 lg:col-span-5">
            <TopicCard topic={dashboardState.topic} />
            <ConsoleOutput status={statusState.status} elapsed={statusState.elapsed} output={statusState.output} />
          </div>
          <div className="lg:col-span-7">
            <SlidesPreview slides={dashboardState.slides} cacheBust={slidesCacheBust} onOpen={openLightbox} />
          </div>
        </div>

        <PostsHistory
          posts={posts}
          loading={postsLoading}
          dbStatusText={dbStatusText}
          dbStatusColor={dbStatusColor}
          syncMessage={syncMessage}
          syncColor={syncColor}
          syncing={syncing}
          onSync={syncNow}
          onPublish={publishDraft}
          onRetry={retryPublish}
          onOpen={openPostDetail}
        />
      </main>

      <Lightbox
        open={lightboxOpen}
        slides={lightboxSlides}
        index={lightboxIndex}
        cacheBust={slidesCacheBust}
        onClose={() => setLightboxOpen(false)}
        onPrev={() =>
          setLightboxIndex((prev) => (prev - 1 + lightboxSlides.length) % Math.max(1, lightboxSlides.length))
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
