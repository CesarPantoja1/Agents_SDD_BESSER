/**
 * SDDPanel — Main left-side panel for Spec-Driven Development.
 * Contains: Config, Phase tracker, Chat, File explorer.
 * File viewing is delegated to SDDFileViewer (opens to the right).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  X, Settings2, MessageSquare, FolderOpen,
  Send, Loader2, FileText, RefreshCw, Trash2,
  CheckCircle2, Circle, Zap, Key, FolderInput,
  Lightbulb, Search, ClipboardList, Hammer, GitBranch,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSDDSession } from '../hooks/useSDDSession';
import type { SDDPhase, SDDFileEntry, SDDMessage, SDDPhasesStatus } from '../services/sdd-types';
import { PHASE_ORDER, PHASE_LABELS, PHASE_EMOJI } from '../services/sdd-types';

/* ------------------------------------------------------------------ */
/*  Simple markdown for chat bubbles (lightweight)                     */
/* ------------------------------------------------------------------ */
function simpleMarkdown(md: string): string {
  let html = md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) => {
      const cls = lang ? ` class="language-${lang}"` : '';
      return `<pre><code${cls}>${code.trim()}</code></pre>`;
    })
    .replace(/`([^`]+)`/g, '<code class="sdd-inline-code">$1</code>')
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^[\-\*•] (.+)$/gm, '<li>$1</li>')
    .replace(/^---$/gm, '<hr/>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');
  return `<p>${html}</p>`;
}

const MarkdownBlock: React.FC<{ content: string }> = ({ content }) => (
  <div
    className="sdd-markdown prose prose-sm prose-invert max-w-none"
    dangerouslySetInnerHTML={{ __html: simpleMarkdown(content) }}
  />
);

/* ------------------------------------------------------------------ */
/*  Phase icons mapping                                                */
/* ------------------------------------------------------------------ */
const PHASE_ICONS: Record<SDDPhase, React.FC<{ className?: string }>> = {
  product: Lightbulb,
  discovery: Search,
  requirements: ClipboardList,
  design: Hammer,
  diagram: GitBranch,
};

/* ------------------------------------------------------------------ */
/*  Phase tracker bar (scrollable)                                     */
/* ------------------------------------------------------------------ */
const PhaseTracker: React.FC<{
  phasesStatus: SDDPhasesStatus | null;
  currentPhase?: string | null;
  isDark: boolean;
}> = ({ phasesStatus, currentPhase, isDark }) => (
  <div
    className={cn(
      'overflow-x-auto border-b shrink-0',
      isDark ? 'border-white/5' : 'border-gray-200',
    )}
    style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
  >
    <div className="flex items-center gap-1.5 px-3 py-2 min-w-max">
      {PHASE_ORDER.map((phase, i) => {
        const done = phasesStatus?.[phase]?.completed;
        const active = currentPhase === phase;
        const Icon = PHASE_ICONS[phase];
        return (
          <React.Fragment key={phase}>
            {i > 0 && (
              <div className={cn(
                'h-px w-4 shrink-0 transition-colors',
                done ? 'bg-emerald-500/60' : (isDark ? 'bg-white/10' : 'bg-gray-200'),
              )} />
            )}
            <div
              className={cn(
                'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold transition-all shrink-0 whitespace-nowrap',
                done && 'bg-emerald-500/15 text-emerald-400',
                active && !done && 'bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30',
                !done && !active && (isDark ? 'text-white/30' : 'text-gray-400'),
              )}
              title={PHASE_LABELS[phase]}
            >
              {done
                ? <CheckCircle2 className="size-3.5" />
                : active
                  ? <Loader2 className="size-3.5 animate-spin" />
                  : <Icon className="size-3.5" />
              }
              <span>{PHASE_LABELS[phase]}</span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  </div>
);

/* ------------------------------------------------------------------ */
/*  Chat bubble                                                        */
/* ------------------------------------------------------------------ */
const ChatBubble: React.FC<{ msg: SDDMessage; isDark: boolean }> = ({ msg, isDark }) => {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[90%] rounded-xl px-3 py-2 text-xs leading-relaxed',
          isUser && 'bg-blue-600 text-white',
          !isUser && !isSystem && (isDark ? 'bg-white/[0.06] text-white/90' : 'bg-gray-100 text-gray-800'),
          isSystem && (isDark ? 'bg-red-500/10 text-red-300 border border-red-500/20' : 'bg-red-50 text-red-700 border border-red-200'),
        )}
      >
        {msg.artifactName && (
          <div className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider opacity-60">
            {PHASE_EMOJI[msg.artifactName as SDDPhase] || '📄'} {msg.artifactName}
          </div>
        )}
        <MarkdownBlock content={msg.content} />
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  File explorer                                                      */
/* ------------------------------------------------------------------ */
const FileExplorer: React.FC<{
  files: SDDFileEntry[];
  onFileSelect: (path: string) => void;
  onRefresh: () => void;
  selectedFile: string | null;
  isDark: boolean;
}> = ({ files, onFileSelect, onRefresh, selectedFile, isDark }) => (
  <div className="flex flex-col gap-0.5 overflow-y-auto">
    <div className="flex items-center justify-between px-3 py-1.5">
      <span className={cn('text-[10px] font-semibold uppercase tracking-wider', isDark ? 'text-white/40' : 'text-gray-500')}>
        Archivos ({files.length})
      </span>
      <button onClick={onRefresh} className={cn('transition-colors', isDark ? 'text-white/30 hover:text-white/60' : 'text-gray-400 hover:text-gray-600')} title="Refrescar">
        <RefreshCw className="size-3" />
      </button>
    </div>
    {files.length === 0 ? (
      <p className={cn('px-3 text-[10px] italic', isDark ? 'text-white/20' : 'text-gray-400')}>Sin archivos generados aún</p>
    ) : (
      files.map((f) => (
        <button
          key={f.path}
          onClick={() => onFileSelect(f.path)}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 text-left text-[11px] transition-colors rounded-md mx-1',
            selectedFile === f.path
              ? (isDark ? 'bg-blue-500/15 text-blue-300' : 'bg-blue-50 text-blue-700')
              : (isDark ? 'text-white/60 hover:bg-white/[0.04] hover:text-white/80' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800'),
          )}
        >
          <FileText className="size-3 shrink-0" />
          <span className="truncate">{f.name}</span>
          <span className={cn('ml-auto text-[9px]', isDark ? 'text-white/20' : 'text-gray-400')}>
            {(f.size / 1024).toFixed(1)}k
          </span>
        </button>
      ))
    )}
  </div>
);

/* ------------------------------------------------------------------ */
/*  Main Panel                                                         */
/* ------------------------------------------------------------------ */

interface SDDPanelProps {
  open: boolean;
  onClose: () => void;
  isDarkTheme?: boolean;
  onImportDiagram?: (diagramJson: Record<string, unknown>) => void | Promise<void>;
  onFileOpen?: (path: string, content: string | null) => void;
}

export const SDDPanel: React.FC<SDDPanelProps> = ({ open, onClose, isDarkTheme = true, onImportDiagram, onFileOpen }) => {
  const {
    connectionStatus, messages, config, files, phasesStatus,
    isProcessing, statusMessage, pendingValidation, lastDiagramJson,
    sendMessage, updateConfig, readFile, writeFile, refreshFiles, clearMessages, clearDiagramJson,
  } = useSDDSession(open);

  const [activeTab, setActiveTab] = useState<'chat' | 'files'>('chat');
  const [inputValue, setInputValue] = useState('');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const prevOutputDirRef = useRef(config.outputDir);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Show config on first open if no API key
  useEffect(() => {
    if (open && !config.apiKey && !config.outputDir) {
      setShowConfig(true);
    }
  }, [open, config.apiKey, config.outputDir]);

  // Refresh files when output directory changes (FIX #2)
  useEffect(() => {
    if (config.outputDir && config.outputDir !== prevOutputDirRef.current) {
      prevOutputDirRef.current = config.outputDir;
      // Clear old file selection and refresh list
      setSelectedFile(null);
      if (onFileOpen) onFileOpen(null as any, null);
      // Small delay to let the server process the config
      const timer = setTimeout(() => refreshFiles(), 500);
      return () => clearTimeout(timer);
    }
  }, [config.outputDir, refreshFiles, onFileOpen]);

  // Listen for file content events → open in the right-side viewer
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.path && detail?.content !== undefined && onFileOpen) {
        onFileOpen(detail.path, detail.content);
      }
    };
    window.addEventListener('sdd:file-content', handler);
    return () => window.removeEventListener('sdd:file-content', handler);
  }, [onFileOpen]);

  // Auto-import diagram when generated (FIX #4)
  useEffect(() => {
    if (lastDiagramJson && onImportDiagram) {
      console.log('[SDD] Auto-importing diagram:', lastDiagramJson);
      onImportDiagram(lastDiagramJson);
      clearDiagramJson();
    }
  }, [lastDiagramJson, onImportDiagram, clearDiagramJson]);

  const handleSubmit = useCallback(() => {
    const text = inputValue.trim();
    if (!text || isProcessing) return;
    sendMessage(text);
    setInputValue('');
  }, [inputValue, isProcessing, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleFileSelect = useCallback(
    (path: string) => {
      setSelectedFile(path);
      readFile(path);
      setActiveTab('files');
    },
    [readFile],
  );

  // Determine connection dot color
  const connDot = connectionStatus === 'connected' ? 'bg-emerald-500' :
    connectionStatus === 'connecting' || connectionStatus === 'reconnecting' ? 'bg-amber-500 animate-pulse' : 'bg-red-500';

  if (!open) return null;

  // Theme tokens
  const t = {
    panel: isDarkTheme
      ? 'border-white/[0.06] bg-[#0d1117] text-white'
      : 'border-gray-200 bg-white text-gray-900',
    border: isDarkTheme ? 'border-white/[0.06]' : 'border-gray-200',
    configBg: isDarkTheme ? 'bg-white/[0.02]' : 'bg-gray-50',
    label: isDarkTheme ? 'text-white/40' : 'text-gray-500',
    input: isDarkTheme
      ? 'border-white/10 bg-white/[0.04] text-white placeholder:text-white/20 focus:border-blue-500/50'
      : 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:border-blue-500',
    select: isDarkTheme
      ? 'border-white/10 bg-white/[0.04] text-white focus:border-blue-500/50'
      : 'border-gray-300 bg-white text-gray-900 focus:border-blue-500',
    tabActive: isDarkTheme ? 'border-blue-500 text-blue-400' : 'border-blue-600 text-blue-600',
    tabInactive: isDarkTheme ? 'text-white/30 hover:text-white/50' : 'text-gray-400 hover:text-gray-600',
    badge: isDarkTheme ? 'bg-white/10' : 'bg-gray-200',
    emptyText: isDarkTheme ? 'text-white/40' : 'text-gray-500',
    emptySubtext: isDarkTheme ? 'text-white/20' : 'text-gray-400',
    promptBtn: isDarkTheme
      ? 'border-white/[0.06] bg-white/[0.02] text-white/40 hover:border-white/10 hover:bg-white/[0.04] hover:text-white/60'
      : 'border-gray-200 bg-gray-50 text-gray-500 hover:border-gray-300 hover:bg-gray-100 hover:text-gray-700',
    processing: isDarkTheme ? 'text-white/30' : 'text-gray-400',
    clearBtn: isDarkTheme ? 'text-white/20 hover:text-red-400' : 'text-gray-400 hover:text-red-500',
    textarea: isDarkTheme
      ? 'border-white/10 bg-white/[0.04] text-white placeholder:text-white/20 focus:border-blue-500/40'
      : 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 focus:border-blue-500',
    recentDir: isDarkTheme
      ? 'bg-white/[0.04] text-white/40 hover:bg-white/[0.08] hover:text-white/60'
      : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700',
    headerBtn: isDarkTheme
      ? 'text-white/40 hover:bg-white/[0.06] hover:text-white/70'
      : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600',
  };

  return (
    <div className={cn('flex h-full w-[380px] shrink-0 flex-col border-r animate-in slide-in-from-left-4 duration-200', t.panel)}>
      {/* ---- Header ---- */}
      <div className={cn('flex items-center justify-between border-b px-3 py-2', t.border)}>
        <div className="flex items-center gap-2">
          <Zap className="size-4 text-amber-400" />
          <span className="text-sm font-bold tracking-tight">SDD Studio</span>
          <span className={cn('size-1.5 rounded-full', connDot)} />
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setShowConfig((p) => !p)} className={cn('rounded p-1', t.headerBtn)} title="Configuración">
            <Settings2 className="size-3.5" />
          </button>
          <button onClick={onClose} className={cn('rounded p-1', t.headerBtn)}>
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {/* ---- Config Drawer ---- */}
      {showConfig && (
        <div className={cn('border-b px-3 py-3 space-y-2.5 animate-in slide-in-from-top-2 duration-150', t.border, t.configBg)}>
          <div>
            <label className={cn('text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1', t.label)}>
              <Key className="size-3" /> API Key
            </label>
            <input
              type="password"
              value={config.apiKey}
              onChange={(e) => updateConfig({ apiKey: e.target.value })}
              placeholder="AIzaSy..."
              className={cn('mt-1 w-full rounded-md border px-2.5 py-1.5 text-xs focus:outline-none', t.input)}
            />
          </div>
          <div>
            <label className={cn('text-[10px] font-semibold uppercase tracking-wider', t.label)}>Modelo</label>
            <select
              value={config.model}
              onChange={(e) => updateConfig({ model: e.target.value })}
              className={cn('mt-1 w-full rounded-md border px-2.5 py-1.5 text-xs focus:outline-none', t.select)}
            >
              <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
              <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
              <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
            </select>
          </div>
          <div>
            <label className={cn('text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1', t.label)}>
              <FolderInput className="size-3" /> Carpeta de Salida
            </label>
            <input
              type="text"
              value={config.outputDir}
              onChange={(e) => updateConfig({ outputDir: e.target.value })}
              placeholder="C:\Users\...\mi-proyecto\output"
              className={cn('mt-1 w-full rounded-md border px-2.5 py-1.5 text-xs font-mono focus:outline-none', t.input)}
            />
            {config.recentDirs.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {config.recentDirs.map((d) => (
                  <button
                    key={d}
                    onClick={() => updateConfig({ outputDir: d })}
                    className={cn('rounded px-2 py-0.5 text-[9px] truncate max-w-[180px]', t.recentDir)}
                    title={d}
                  >
                    {d.split(/[\\/]/).pop()}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => setShowConfig(false)}
            className="w-full rounded-md bg-blue-600/80 py-1.5 text-[11px] font-semibold hover:bg-blue-600 transition-colors text-white"
          >
            Guardar configuración
          </button>
        </div>
      )}

      {/* ---- Phase Tracker (scrollable, with icons) ---- */}
      <PhaseTracker
        phasesStatus={phasesStatus}
        isDark={isDarkTheme}
        currentPhase={isProcessing ? undefined : phasesStatus ? PHASE_ORDER.find((p) => !phasesStatus[p]?.completed) : undefined}
      />

      {/* ---- Tab bar ---- */}
      <div className={cn('flex border-b', t.border)}>
        {([['chat', MessageSquare, 'Chat'], ['files', FolderOpen, 'Archivos']] as const).map(([key, Icon, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-semibold transition-colors',
              activeTab === key ? cn('border-b-2', t.tabActive) : t.tabInactive,
            )}
          >
            <Icon className="size-3.5" />
            {label}
            {key === 'files' && files.length > 0 && (
              <span className={cn('rounded-full px-1.5 text-[9px]', t.badge)}>{files.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ---- Chat Tab ---- */}
      {activeTab === 'chat' && (
        <div className="flex min-h-0 flex-1 flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                <Zap className="size-10 text-amber-400/30" />
                <p className={cn('text-sm font-semibold', t.emptyText)}>SDD Studio</p>
                <p className={cn('text-[11px] leading-relaxed max-w-[260px]', t.emptySubtext)}>
                  Describe tu sistema y generaré las especificaciones paso a paso:
                  Product → Discovery → Requirements → Design → Diagram
                </p>
                <div className="flex flex-col gap-1.5 mt-2 w-full max-w-[260px]">
                  {['Quiero una app de gestión de tareas', 'Sistema de e-commerce con catálogo', 'Plataforma educativa online'].map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => { setInputValue(prompt); inputRef.current?.focus(); }}
                      className={cn('rounded-lg border px-3 py-2 text-left text-[11px] transition-colors', t.promptBtn)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <ChatBubble key={msg.id} msg={msg} isDark={isDarkTheme} />
                ))}
                {isProcessing && statusMessage && (
                  <div className={cn('flex items-center gap-2 text-[11px]', t.processing)}>
                    <Loader2 className="size-3 animate-spin" />
                    {statusMessage}
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className={cn('border-t px-3 py-2.5', t.border)}>
            {messages.length > 0 && (
              <div className="flex justify-end mb-1.5">
                <button onClick={clearMessages} className={cn('text-[9px] transition-colors flex items-center gap-1', t.clearBtn)}>
                  <Trash2 className="size-2.5" /> Limpiar chat
                </button>
              </div>
            )}
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={connectionStatus === 'connected' ? 'Describe tu sistema...' : 'Conectando al servidor...'}
                disabled={connectionStatus !== 'connected' || isProcessing}
                rows={1}
                className={cn('flex-1 resize-none rounded-lg border px-3 py-2 text-xs focus:outline-none disabled:opacity-40', t.textarea)}
              />
              <button
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isProcessing || connectionStatus !== 'connected'}
                className="rounded-lg bg-blue-600 p-2 text-white transition-colors hover:bg-blue-500 disabled:opacity-30 disabled:hover:bg-blue-600"
              >
                {isProcessing ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Files Tab (list only — viewing happens in SDDFileViewer) ---- */}
      {activeTab === 'files' && (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <FileExplorer
            files={files}
            onFileSelect={handleFileSelect}
            onRefresh={refreshFiles}
            selectedFile={selectedFile}
            isDark={isDarkTheme}
          />
        </div>
      )}
    </div>
  );
};
