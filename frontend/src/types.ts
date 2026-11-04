export interface HealthData {
  status: string;
  app: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  ml_ready?: boolean;
}

export interface SystemStatusData {
  status: string;
  uptime_seconds: number;
  system: {
    os: string;
    os_version: string;
    architecture: string;
    processor: string;
  };
  resources: {
    cpu_percent: number;
    ram_total_gb: number;
    ram_used_gb: number;
    ram_percent: number;
    disk_free_gb: number;
    disk_total_gb: number;
    disk_percent: number;
  };
  app: {
    name: string;
    version: string;
    environment: string;
    port: number;
    ml_model?: string;
  };
}

export interface CommandResult {
  query: string;
  intent: string;
  raw_intent: string;
  confidence: number;
  confidence_percent: number;
  threshold: number;
  needs_clarification: boolean;
  clarification_message?: string;
  entities: Record<string, any>;
  latency_ms: number;
  live_response?: string;
  executed_tool?: string;
  tool_result?: Record<string, any>;
  model_name: string;
  top_probabilities: Record<string, number>;
}

export interface VoiceStatus {
  state: 'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING' | 'MUTED';
  is_muted: boolean;
  is_audio_running: boolean;
  last_transcript: string;
  volume_level: number;
}

export interface VoiceListenResult {
  transcript?: string;
  clean_command?: string;
  wake_word_detected?: boolean;
  prediction?: CommandResult;
  spoken_response?: string;
  status: string;
  error?: string;
  message?: string;
}

export interface ToolParam {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: any;
  choices?: string[];
}

export interface ToolDefinition {
  name: string;
  description: string;
  category: 'desktop' | 'browser' | 'file';
  risk_level: 'READ_ONLY' | 'LOW_RISK' | 'HIGH_RISK_CONFIRMATION';
  parameters: ToolParam[];
}

export interface ToolVerification {
  verified: boolean;
  method: string;
  details: string;
  metrics?: Record<string, any>;
}

export interface ToolExecutionResult {
  tool_name: string;
  success: boolean;
  output: string;
  data?: Record<string, any>;
  error?: string;
  verification?: ToolVerification;
  requires_confirmation?: boolean;
  confirmation_token?: string;
  confirmation_prompt?: string;
}

export interface AuditRecord {
  id: string;
  tool_name: string;
  category: string;
  risk_level: string;
  args: Record<string, any>;
  status: string;
  duration_ms: number;
  output: string;
  verification_status: string;
  timestamp: string;
}

export interface NovaIPCBridge {
  ping: () => Promise<string>;
  getLoginItemSettings: () => Promise<boolean>;
  setLoginItemSettings: (enabled: boolean) => Promise<boolean>;
  minimizeToTray: () => void;
  quitApp: () => void;
  openExternal: (url: string) => Promise<boolean>;
  platform: string;
}

declare global {
  interface Window {
    novaAPI?: NovaIPCBridge;
  }
}
