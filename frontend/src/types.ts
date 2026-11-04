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
  model_name: string;
  top_probabilities: Record<string, number>;
}

export interface NovaIPCBridge {
  ping: () => Promise<string>;
  getLoginItemSettings: () => Promise<boolean>;
  setLoginItemSettings: (enabled: boolean) => Promise<boolean>;
  minimizeToTray: () => void;
  quitApp: () => void;
  platform: string;
}

declare global {
  interface Window {
    novaAPI?: NovaIPCBridge;
  }
}
