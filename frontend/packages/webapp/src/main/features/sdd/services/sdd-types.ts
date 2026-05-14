/**
 * SDD Types — mirrors the Python LangGraph state and server messages.
 */

export type SDDPhase = 'product' | 'discovery' | 'requirements' | 'design' | 'diagram';
export type SDDFase = SDDPhase | 'next' | 'sync' | 'error' | 'validation_reject' | 'validation_apply' | 'validation_sync';

export interface SDDPhaseStatus {
  completed: boolean;
  contentLength: number;
}

export interface SDDPhasesStatus {
  product: SDDPhaseStatus;
  discovery: SDDPhaseStatus;
  requirements: SDDPhaseStatus;
  design: SDDPhaseStatus;
  diagram: SDDPhaseStatus;
}

export interface SDDMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  fase?: SDDFase;
  artifactName?: string;
}

export interface SDDFileEntry {
  path: string;
  name: string;
  ext: string;
  size: number;
}

export interface SDDConfig {
  apiKey: string;
  model: string;
  outputDir: string;
  recentDirs: string[];
}

export interface SDDValidation {
  es_valido: boolean;
  inconsistencias: string[];
  sugerencias: string[];
  resumen: string;
  requiere_rollback?: boolean;
}

export interface SDDImpacto {
  impacta_discovery: boolean;
  razon_discovery: string;
  impacta_requirements: boolean;
  razon_requirements: string;
  impacta_design: boolean;
  razon_design: string;
  impacta_diagram: boolean;
  razon_diagram: string;
  alertas_upstream: string;
}

/** Server → Client messages */
export type SDDServerMessage =
  | { type: 'config_ack'; config: { api_key: string; model: string }; outputDir: string }
  | { type: 'reset_ack' }
  | { type: 'files'; files: SDDFileEntry[] }
  | { type: 'file_content'; path: string; content: string }
  | { type: 'file_saved'; path: string }
  | { type: 'status'; status: string; message: string }
  | {
      type: 'response';
      fase: SDDFase;
      lastActivePhase: SDDPhase | null;
      blockedReason: string | null;
      pendingValidation: SDDValidation | null;
      impactoAnalysis: SDDImpacto | null;
      phasesStatus: SDDPhasesStatus;
      artifactContent?: string;
      artifactName?: string;
      assistantMessage?: string;
      diagramJson?: Record<string, unknown>;
      files?: SDDFileEntry[];
    }
  | { type: 'error'; message: string; traceback?: string };

/** Client → Server messages */
export type SDDClientMessage =
  | { type: 'message'; content: string }
  | { type: 'config'; apiKey?: string; model?: string; outputDir?: string }
  | { type: 'reset' }
  | { type: 'list_files' }
  | { type: 'read_file'; path: string }
  | { type: 'write_file'; path: string; content: string };

export const PHASE_ORDER: SDDPhase[] = ['product', 'discovery', 'requirements', 'design', 'diagram'];

export const PHASE_LABELS: Record<SDDPhase, string> = {
  product: 'Product',
  discovery: 'Discovery',
  requirements: 'Requirements',
  design: 'Design',
  diagram: 'Diagram',
};

export const PHASE_EMOJI: Record<SDDPhase, string> = {
  product: '💡',
  discovery: '🔍',
  requirements: '📋',
  design: '🏗️',
  diagram: '📐',
};

export const DEFAULT_SDD_CONFIG: SDDConfig = {
  apiKey: '',
  model: 'gemini-2.5-flash',
  outputDir: '',
  recentDirs: [],
};
