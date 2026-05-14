/**
 * SDDFileViewer — Separate right-side panel for viewing/editing SDD files.
 * Opens to the right of the SDD panel (like VSCode split view).
 * Renders markdown with proper formatting, code blocks, and mermaid diagrams.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { X, Save, Edit3, Eye, Maximize2, Minimize2 } from 'lucide-react';
import { cn } from '@/lib/utils';

/* ------------------------------------------------------------------ */
/*  Markdown renderer (full featured)                                   */
/* ------------------------------------------------------------------ */

function renderMarkdown(md: string): string {
  // Escape HTML entities first
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks with language (preserve content as-is)
  html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) => {
    const cls = lang ? ` class="language-${lang}"` : '';
    return `<pre class="sdd-code-block"><code${cls}>${code.trimEnd()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="sdd-inline-code">$1</code>');

  // Headers (must be at start of line)
  html = html.replace(/^##### (.+)$/gm, '<h5>$1</h5>');
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold + italic combinations
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr/>');

  // Ordered lists: "1. text", "2. text", etc.
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="sdd-ol-item" data-n="$1">$2</li>');

  // Unordered lists: "- text", "* text", "• text"
  html = html.replace(/^[\-\*•] (.+)$/gm, '<li>$1</li>');

  // Wrap consecutive <li> in <ul> or <ol>
  html = html.replace(/((?:<li class="sdd-ol-item"[^>]*>.*?<\/li>\s*)+)/g, '<ol>$1</ol>');
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');

  // Paragraphs: double newline = new paragraph
  html = html.replace(/\n\n/g, '</p><p>');
  // Single newline = line break (but not inside pre/code)
  html = html.replace(/\n/g, '<br/>');

  return `<p>${html}</p>`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface SDDFileViewerProps {
  filePath: string | null;
  fileContent: string | null;
  isDarkTheme: boolean;
  onClose: () => void;
  onSave: (path: string, content: string) => void;
}

export const SDDFileViewer: React.FC<SDDFileViewerProps> = ({
  filePath,
  fileContent,
  isDarkTheme,
  onClose,
  onSave,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editBuffer, setEditBuffer] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  // Reset edit state when file changes
  useEffect(() => {
    setIsEditing(false);
    setEditBuffer(fileContent || '');
  }, [filePath, fileContent]);

  // Mermaid rendering
  useEffect(() => {
    if (fileContent && !isEditing && contentRef.current) {
      const mermaidBlocks = contentRef.current.querySelectorAll('.language-mermaid');
      if (mermaidBlocks.length > 0) {
        // @ts-ignore
        import('mermaid').then((m) => {
          m.default.initialize({ startOnLoad: false, theme: isDarkTheme ? 'dark' : 'default' });
          mermaidBlocks.forEach((block, index) => {
            const code = block.textContent || '';
            const id = `mermaid-${Date.now()}-${index}`;
            const pre = block.parentElement;
            if (pre && pre.tagName.toLowerCase() === 'pre') {
              const div = document.createElement('div');
              div.className = 'flex justify-center my-4 p-4 bg-white/5 rounded-lg';
              div.id = id;
              pre.replaceWith(div);
              m.default.render(`${id}-svg`, code).then((result: any) => {
                div.innerHTML = result.svg;
              }).catch((e: Error) => {
                div.innerHTML = `<pre class="text-red-500 text-xs p-4 bg-red-500/10 rounded">Mermaid Error:\n${e.message}</pre>`;
              });
            }
          });
        });
      }
    }
  }, [fileContent, isEditing, isDarkTheme]);

  const handleSave = useCallback(() => {
    if (filePath && editBuffer !== null) {
      onSave(filePath, editBuffer);
      setIsEditing(false);
    }
  }, [filePath, editBuffer, onSave]);

  if (!filePath) return null;

  const t = {
    panel: isDarkTheme
      ? 'bg-[#0d1117] text-white/90 border-white/[0.06]'
      : 'bg-white text-gray-900 border-gray-200',
    header: isDarkTheme
      ? 'bg-[#161b22] border-white/[0.06]'
      : 'bg-gray-50 border-gray-200',
    headerBtn: isDarkTheme
      ? 'text-white/40 hover:bg-white/[0.06] hover:text-white/70'
      : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600',
    content: isDarkTheme ? 'text-white/85' : 'text-gray-800',
    editArea: isDarkTheme
      ? 'bg-[#0d1117] text-white/80 border-white/[0.06]'
      : 'bg-white text-gray-800 border-gray-200',
    // Markdown-specific styles
    heading: isDarkTheme ? 'text-white' : 'text-gray-900',
    paragraph: isDarkTheme ? 'text-white/80' : 'text-gray-700',
    code: isDarkTheme
      ? 'bg-white/[0.06] text-emerald-300 border-white/10'
      : 'bg-gray-100 text-emerald-700 border-gray-200',
    codeBlock: isDarkTheme
      ? 'bg-[#161b22] border-white/10 text-gray-300'
      : 'bg-gray-50 border-gray-200 text-gray-800',
    listMarker: isDarkTheme ? 'text-blue-400' : 'text-blue-600',
    hr: isDarkTheme ? 'border-white/10' : 'border-gray-200',
    strong: isDarkTheme ? 'text-white' : 'text-gray-900',
  };

  return (
    <div className={cn(
      'flex h-full w-full flex-col bg-card animate-in fade-in-50 duration-200',
    )}>
      {/* Header */}
      <div className={cn('flex items-center justify-between px-3 py-2 border-b shrink-0', t.header)}>
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-[11px] font-semibold truncate">{filePath}</span>
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          {/* Removed Maximize/Minimize button as it's full screen now */}
          {isEditing ? (
            <>
              <button onClick={handleSave} className="rounded p-1 text-emerald-400 hover:bg-emerald-500/10" title="Guardar">
                <Save className="size-3.5" />
              </button>
              <button onClick={() => { setIsEditing(false); setEditBuffer(fileContent || ''); }} className={cn('rounded p-1', t.headerBtn)} title="Cancelar">
                <Eye className="size-3.5" />
              </button>
            </>
          ) : (
            <button onClick={() => { setIsEditing(true); setEditBuffer(fileContent || ''); }} className={cn('rounded p-1', t.headerBtn)} title="Editar">
              <Edit3 className="size-3.5" />
            </button>
          )}
          <button onClick={onClose} className={cn('rounded p-1', t.headerBtn)}>
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {fileContent === null ? (
          <div className="flex items-center justify-center h-full">
            <div className={cn('size-5 border-2 border-current border-t-transparent rounded-full animate-spin', isDarkTheme ? 'text-white/20' : 'text-gray-300')} />
          </div>
        ) : isEditing ? (
          <textarea
            value={editBuffer}
            onChange={(e) => setEditBuffer(e.target.value)}
            className={cn(
              'w-full h-full resize-none p-4 text-xs font-mono leading-relaxed focus:outline-none',
              t.editArea,
            )}
            spellCheck={false}
          />
        ) : (
          <div ref={contentRef} className="p-4">
            <style>{`
              .sdd-viewer h1 { font-size: 1.5rem; font-weight: 700; margin: 1.25rem 0 0.75rem; line-height: 1.3; color: ${isDarkTheme ? '#fff' : '#111827'}; }
              .sdd-viewer h2 { font-size: 1.25rem; font-weight: 700; margin: 1.1rem 0 0.6rem; line-height: 1.3; color: ${isDarkTheme ? '#fff' : '#111827'}; border-bottom: 1px solid ${isDarkTheme ? 'rgba(255,255,255,0.08)' : '#e5e7eb'}; padding-bottom: 0.35rem; }
              .sdd-viewer h3 { font-size: 1.05rem; font-weight: 600; margin: 1rem 0 0.5rem; color: ${isDarkTheme ? '#e2e8f0' : '#1f2937'}; }
              .sdd-viewer h4 { font-size: 0.95rem; font-weight: 600; margin: 0.8rem 0 0.4rem; color: ${isDarkTheme ? '#cbd5e1' : '#374151'}; }
              .sdd-viewer h5 { font-size: 0.875rem; font-weight: 600; margin: 0.6rem 0 0.3rem; color: ${isDarkTheme ? '#94a3b8' : '#4b5563'}; }
              .sdd-viewer p { margin: 0.5rem 0; font-size: 0.8125rem; line-height: 1.7; color: ${isDarkTheme ? 'rgba(255,255,255,0.8)' : '#374151'}; }
              .sdd-viewer strong { font-weight: 700; color: ${isDarkTheme ? '#fff' : '#111827'}; }
              .sdd-viewer em { font-style: italic; }
              .sdd-viewer ul { margin: 0.4rem 0; padding-left: 1.25rem; list-style: disc; }
              .sdd-viewer ol { margin: 0.4rem 0; padding-left: 1.25rem; list-style: decimal; }
              .sdd-viewer li { font-size: 0.8125rem; line-height: 1.7; margin: 0.15rem 0; color: ${isDarkTheme ? 'rgba(255,255,255,0.8)' : '#374151'}; }
              .sdd-viewer li::marker { color: ${isDarkTheme ? '#60a5fa' : '#2563eb'}; }
              .sdd-viewer hr { border: none; border-top: 1px solid ${isDarkTheme ? 'rgba(255,255,255,0.08)' : '#e5e7eb'}; margin: 1rem 0; }
              .sdd-viewer .sdd-code-block { background: ${isDarkTheme ? '#161b22' : '#f3f4f6'}; border: 1px solid ${isDarkTheme ? 'rgba(255,255,255,0.08)' : '#e5e7eb'}; border-radius: 0.5rem; padding: 0.75rem 1rem; margin: 0.6rem 0; overflow-x: auto; }
              .sdd-viewer .sdd-code-block code { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.75rem; line-height: 1.6; color: ${isDarkTheme ? '#e2e8f0' : '#1f2937'}; white-space: pre; }
              .sdd-viewer .sdd-inline-code { background: ${isDarkTheme ? 'rgba(255,255,255,0.06)' : '#f3f4f6'}; border: 1px solid ${isDarkTheme ? 'rgba(255,255,255,0.1)' : '#e5e7eb'}; border-radius: 0.25rem; padding: 0.1rem 0.35rem; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; color: ${isDarkTheme ? '#6ee7b7' : '#059669'}; }
            `}</style>
            <div
              className="sdd-viewer"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(fileContent) }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
