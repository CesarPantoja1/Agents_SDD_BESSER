/**
 * useSDDSession — Main hook for managing the SDD panel state:
 * - WebSocket connection to the Python backend
 * - Messages / conversation history
 * - Config (apiKey, model, outputDir) persisted in localStorage
 * - Files list from the output directory
 * - Phase completion status
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { SDDClient, type SDDConnectionStatus } from '../services/sdd-client';
import type {
  SDDConfig,
  SDDFileEntry,
  SDDMessage,
  SDDPhasesStatus,
  SDDServerMessage,
  SDDValidation,
  SDDImpacto,
} from '../services/sdd-types';

const LS_CONFIG_KEY = 'besser-sdd-config';
const LS_MESSAGES_KEY = 'besser-sdd-messages';
const SDD_WS_URL = 'ws://localhost:8765/ws/sdd';

function loadConfig(): SDDConfig {
  try {
    const raw = localStorage.getItem(LS_CONFIG_KEY);
    if (raw) return { ...getDefaultConfig(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return getDefaultConfig();
}

function getDefaultConfig(): SDDConfig {
  return { apiKey: '', model: 'gemini-2.5-flash', outputDir: '', recentDirs: [] };
}

function saveConfig(config: SDDConfig): void {
  localStorage.setItem(LS_CONFIG_KEY, JSON.stringify(config));
}

function loadMessages(): SDDMessage[] {
  try {
    const raw = localStorage.getItem(LS_MESSAGES_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return [];
}

function saveMessages(messages: SDDMessage[]): void {
  localStorage.setItem(LS_MESSAGES_KEY, JSON.stringify(messages));
}

let msgCounter = 0;
function makeId(): string {
  msgCounter++;
  return `sdd-${Date.now()}-${msgCounter}`;
}

export function useSDDSession(isActive: boolean) {
  const [connectionStatus, setConnectionStatus] = useState<SDDConnectionStatus>('disconnected');
  const [messages, setMessages] = useState<SDDMessage[]>(() => loadMessages());
  const [config, setConfig] = useState<SDDConfig>(() => loadConfig());
  const [files, setFiles] = useState<SDDFileEntry[]>([]);
  const [phasesStatus, setPhasesStatus] = useState<SDDPhasesStatus | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [pendingValidation, setPendingValidation] = useState<SDDValidation | null>(null);
  const [impactoAnalysis, setImpactoAnalysis] = useState<SDDImpacto | null>(null);
  const [lastDiagramJson, setLastDiagramJson] = useState<Record<string, unknown> | null>(null);

  const clientRef = useRef<SDDClient | null>(null);
  const configRef = useRef(config);
  configRef.current = config;

  // Persist messages
  useEffect(() => { saveMessages(messages); }, [messages]);
  // Persist config
  useEffect(() => { saveConfig(config); }, [config]);

  const handleServerMessage = useCallback((msg: SDDServerMessage) => {
    switch (msg.type) {
      case 'config_ack':
        break;

      case 'status':
        setStatusMessage(msg.message);
        break;

      case 'files':
        setFiles(msg.files);
        break;

      case 'file_content':
        // Handled by specific file viewer callbacks — dispatch custom event
        window.dispatchEvent(new CustomEvent('sdd:file-content', { detail: msg }));
        break;

      case 'file_saved':
        // Refresh file list
        clientRef.current?.send({ type: 'list_files' });
        break;

      case 'response': {
        setIsProcessing(false);
        setStatusMessage(null);

        if (msg.phasesStatus) {
          setPhasesStatus(msg.phasesStatus);
        }

        if (msg.pendingValidation) {
          setPendingValidation(msg.pendingValidation);
        } else {
          setPendingValidation(null);
        }

        if (msg.impactoAnalysis) {
          setImpactoAnalysis(msg.impactoAnalysis);
        }

        if (msg.assistantMessage) {
          setMessages((prev) => [
            ...prev,
            {
              id: makeId(),
              role: 'assistant',
              content: msg.assistantMessage!,
              timestamp: Date.now(),
              fase: msg.fase,
              artifactName: msg.artifactName,
            },
          ]);
        }

        if (msg.diagramJson) {
          setLastDiagramJson(msg.diagramJson);
        }

        if (msg.files) {
          setFiles(msg.files);
        }

        break;
      }

      case 'error':
        setIsProcessing(false);
        setStatusMessage(null);
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: 'system',
            content: `❌ ${msg.message}`,
            timestamp: Date.now(),
          },
        ]);
        break;

      default:
        break;
    }
  }, []);

  // Connect / disconnect based on panel visibility
  useEffect(() => {
    if (!isActive) return;

    const client = new SDDClient({
      url: SDD_WS_URL,
      onMessage: handleServerMessage,
      onStatusChange: setConnectionStatus,
    });
    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [isActive, handleServerMessage]);

  // Once connected, send config and request file list
  useEffect(() => {
    if (connectionStatus !== 'connected' || !clientRef.current) return;
    const cfg = configRef.current;
    if (cfg.apiKey || cfg.outputDir) {
      clientRef.current.send({
        type: 'config',
        apiKey: cfg.apiKey || undefined,
        model: cfg.model || undefined,
        outputDir: cfg.outputDir || undefined,
      });
    }
    clientRef.current.send({ type: 'list_files' });
  }, [connectionStatus]);

  const sendMessage = useCallback((text: string) => {
    if (!clientRef.current?.isConnected()) return;

    setMessages((prev) => [
      ...prev,
      { id: makeId(), role: 'user', content: text, timestamp: Date.now() },
    ]);
    setIsProcessing(true);
    setStatusMessage('Procesando...');

    clientRef.current.send({ type: 'message', content: text });
  }, []);

  const updateConfig = useCallback((partial: Partial<SDDConfig>) => {
    setConfig((prev) => {
      const next = { ...prev, ...partial };
      // Track recent dirs
      if (partial.outputDir && partial.outputDir !== prev.outputDir) {
        const dirs = [partial.outputDir, ...prev.recentDirs.filter((d) => d !== partial.outputDir)].slice(0, 5);
        next.recentDirs = dirs;
      }
      // Send to server
      if (clientRef.current?.isConnected()) {
        clientRef.current.send({
          type: 'config',
          apiKey: next.apiKey || undefined,
          model: next.model || undefined,
          outputDir: next.outputDir || undefined,
        });
      }
      return next;
    });
  }, []);

  const readFile = useCallback((path: string) => {
    clientRef.current?.send({ type: 'read_file', path });
  }, []);

  const writeFile = useCallback((path: string, content: string) => {
    clientRef.current?.send({ type: 'write_file', path, content });
  }, []);

  const refreshFiles = useCallback(() => {
    clientRef.current?.send({ type: 'list_files' });
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setPhasesStatus(null);
    setPendingValidation(null);
    setImpactoAnalysis(null);
    setLastDiagramJson(null);
    clientRef.current?.send({ type: 'reset' });
  }, []);

  const clearDiagramJson = useCallback(() => {
    setLastDiagramJson(null);
  }, []);

  return {
    connectionStatus,
    messages,
    config,
    files,
    phasesStatus,
    isProcessing,
    statusMessage,
    pendingValidation,
    impactoAnalysis,
    lastDiagramJson,
    sendMessage,
    updateConfig,
    readFile,
    writeFile,
    refreshFiles,
    clearMessages,
    clearDiagramJson,
  };
}
