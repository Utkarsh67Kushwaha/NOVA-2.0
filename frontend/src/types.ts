export interface HealthData {
  status: string;
  app: string;
  version: string;
  environment: string;
  uptime_seconds: number;
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
  };
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
