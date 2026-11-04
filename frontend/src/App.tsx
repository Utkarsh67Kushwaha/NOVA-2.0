import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Activity,
  Cpu,
  HardDrive,
  Power,
  RefreshCw,
  Server,
  Settings,
  ShieldCheck,
  Terminal,
  Minimize2,
  CheckCircle2,
  Radio,
} from 'lucide-react';
import { HealthData, SystemStatusData } from './types';

const BACKEND_URL = 'http://127.0.0.1:8000';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

export default function App(): React.JSX.Element {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [autoStartup, setAutoStartup] = useState<boolean>(false);
  const [isElectron, setIsElectron] = useState<boolean>(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev.slice(-99), { timestamp, level, message }]);
  }, []);

  // Check Electron IPC presence
  useEffect(() => {
    if (window.novaAPI) {
      setIsElectron(true);
      addLog('Electron IPC initialized successfully.', 'success');
      window.novaAPI
        .getLoginItemSettings()
        .then((val) => setAutoStartup(val))
        .catch((err) => addLog(`Failed to query startup settings: ${err}`, 'warn'));
    } else {
      setIsElectron(false);
      addLog('Running in standalone browser mode. Electron IPC bridge unavailable.', 'info');
    }
  }, [addLog]);

  // Poll Backend Health & System Status
  const checkBackend = useCallback(async () => {
    const startTime = performance.now();
    try {
      const [healthRes, statusRes] = await Promise.all([
        fetch(`${BACKEND_URL}/health`),
        fetch(`${BACKEND_URL}/api/status`),
      ]);

      const roundTrip = Math.round(performance.now() - startTime);
      setLatencyMs(roundTrip);

      if (healthRes.ok && statusRes.ok) {
        const healthJson: HealthData = await healthRes.json();
        const statusJson: SystemStatusData = await statusRes.json();
        setHealth(healthJson);
        setSystemStatus(statusJson);

        if (!isBackendConnected) {
          setIsBackendConnected(true);
          addLog(`Connected to FastAPI backend: ${healthJson.app} (v${healthJson.version}) in ${roundTrip}ms`, 'success');
        }
      } else {
        throw new Error(`HTTP status: ${healthRes.status}/${statusRes.status}`);
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      if (isBackendConnected) {
        setIsBackendConnected(false);
        addLog(`Backend unreachable: ${errorMsg}`, 'error');
      }
      setHealth(null);
      setLatencyMs(null);
    }
  }, [isBackendConnected, addLog]);

  // Periodic polling every 3 seconds
  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 3000);
    return () => clearInterval(interval);
  }, [checkBackend]);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    addLog('Manual probe triggered...', 'info');
    await checkBackend();
    setIsRefreshing(false);
  };

  const handleToggleStartup = async () => {
    if (!window.novaAPI) {
      addLog('Startup configuration requires running within Electron desktop shell.', 'warn');
      return;
    }
    const nextVal = !autoStartup;
    try {
      const confirmed = await window.novaAPI.setLoginItemSettings(nextVal);
      setAutoStartup(confirmed);
      addLog(
        `Windows login startup ${confirmed ? 'ENABLED' : 'DISABLED'}`,
        confirmed ? 'success' : 'info'
      );
    } catch (err) {
      addLog(`Failed to change startup setting: ${err}`, 'error');
    }
  };

  const handleMinimize = () => {
    if (window.novaAPI) {
      addLog('Window minimized to system tray.', 'info');
      window.novaAPI.minimizeToTray();
    }
  };

  const handleQuit = () => {
    if (window.novaAPI) {
      addLog('Initiating graceful desktop application shutdown...', 'warn');
      window.novaAPI.quitApp();
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-nova-dark text-slate-100 overflow-hidden select-none">
      {/* Top Navigation Bar */}
      <header className="flex items-center justify-between px-6 py-3 bg-nova-panel border-b border-nova-border/70">
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-nova-cyan/20 border border-nova-cyan/40">
            <Radio className="w-5 h-5 text-nova-cyan animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-wider uppercase text-white flex items-center gap-2">
              NOVA <span className="text-xs px-2 py-0.5 rounded bg-nova-cyan/10 text-nova-cyan border border-nova-cyan/30">Phase 1</span>
            </h1>
            <p className="text-[11px] text-slate-400">Desktop Foundation & Lifecycle Shell</p>
          </div>
        </div>

        {/* Status Pill & Controls */}
        <div className="flex items-center space-x-3">
          <div
            className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${
              isBackendConnected
                ? 'bg-nova-success/10 text-emerald-400 border-nova-success/30'
                : 'bg-nova-danger/10 text-rose-400 border-nova-danger/30'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'
              }`}
            />
            {isBackendConnected ? `Backend Online (${latencyMs ?? 0}ms)` : 'Backend Offline'}
          </div>

          <button
            onClick={handleManualRefresh}
            title="Refresh status"
            className="p-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-slate-300 border border-nova-border transition"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-nova-cyan' : ''}`} />
          </button>

          {isElectron && (
            <button
              onClick={handleMinimize}
              title="Minimize to Tray"
              className="p-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-slate-300 border border-nova-border transition"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
          )}

          {isElectron && (
            <button
              onClick={handleQuit}
              title="Quit App"
              className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition"
            >
              <Power className="w-4 h-4" />
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-6 overflow-y-auto space-y-6">
        {/* System Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* 1. Backend Service Card */}
          <div className="p-5 rounded-xl bg-nova-panel border border-nova-border shadow-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">FastAPI Core</span>
                <Server className="w-4 h-4 text-nova-cyan" />
              </div>
              <div className="text-2xl font-bold tracking-tight text-white mb-1">
                {health?.status === 'healthy' ? 'Healthy' : 'Disconnected'}
              </div>
              <div className="text-xs text-slate-400 mb-4">
                Endpoint: <span className="text-slate-200 font-mono">{BACKEND_URL}/health</span>
              </div>

              <div className="space-y-2 border-t border-nova-border/60 pt-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Version:</span>
                  <span className="font-mono text-slate-200">{health?.version ?? 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Environment:</span>
                  <span className="capitalize text-slate-200">{health?.environment ?? 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Uptime:</span>
                  <span className="font-mono text-slate-200">
                    {health ? `${health.uptime_seconds}s` : '0s'}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-nova-border/60 flex items-center gap-2 text-[11px] text-slate-400">
              <ShieldCheck className="w-3.5 h-3.5 text-nova-cyan" />
              CORS & Safe Lifespan Active
            </div>
          </div>

          {/* 2. Hardware Resource Metrics Card */}
          <div className="p-5 rounded-xl bg-nova-panel border border-nova-border shadow-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Host Resources</span>
                <Cpu className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold tracking-tight text-white mb-1">
                {systemStatus ? `${systemStatus.resources.cpu_percent}% CPU` : '--'}
              </div>
              <div className="text-xs text-slate-400 mb-4">
                RAM: {systemStatus ? `${systemStatus.resources.ram_used_gb} / ${systemStatus.resources.ram_total_gb} GB (${systemStatus.resources.ram_percent}%)` : '--'}
              </div>

              {/* Progress bars */}
              <div className="space-y-3 border-t border-nova-border/60 pt-3 text-xs">
                <div>
                  <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                    <span>RAM Load</span>
                    <span>{systemStatus?.resources.ram_percent ?? 0}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-teal-500 to-emerald-400 transition-all duration-500"
                      style={{ width: `${systemStatus?.resources.ram_percent ?? 0}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                    <span>Disk Used (C:\)</span>
                    <span>{systemStatus?.resources.disk_percent ?? 0}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-cyan-500 transition-all duration-500"
                      style={{ width: `${systemStatus?.resources.disk_percent ?? 0}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-nova-border/60 flex items-center justify-between text-[11px] text-slate-400">
              <span className="truncate">{systemStatus?.system.os ?? 'Detecting OS...'}</span>
              <HardDrive className="w-3.5 h-3.5 text-slate-400" />
            </div>
          </div>

          {/* 3. Windows Lifecycle & Startup Card */}
          <div className="p-5 rounded-xl bg-nova-panel border border-nova-border shadow-lg flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">Desktop Shell</span>
                <Settings className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-2xl font-bold tracking-tight text-white mb-1">
                {isElectron ? 'Electron Active' : 'Browser Mode'}
              </div>
              <div className="text-xs text-slate-400 mb-4">
                Single Instance & Tray Enabled
              </div>

              <div className="space-y-3 border-t border-nova-border/60 pt-3 text-xs">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-200">Start with Windows</div>
                    <div className="text-[11px] text-slate-400">Launch after user login</div>
                  </div>
                  <button
                    onClick={handleToggleStartup}
                    disabled={!isElectron}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      autoStartup ? 'bg-nova-cyan' : 'bg-slate-700'
                    } ${!isElectron ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        autoStartup ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <span className="text-slate-400">System Tray:</span>
                  <span className="inline-flex items-center gap-1 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Resident
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-nova-border/60 flex items-center gap-2 text-[11px] text-slate-400">
              <Activity className="w-3.5 h-3.5 text-purple-400" />
              IPC Security: Sandboxed contextBridge
            </div>
          </div>
        </div>

        {/* Diagnostics & Logs Terminal */}
        <div className="rounded-xl bg-nova-panel border border-nova-border shadow-lg overflow-hidden flex flex-col h-64">
          <div className="flex items-center justify-between px-4 py-2.5 bg-nova-card/60 border-b border-nova-border">
            <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
              <Terminal className="w-4 h-4 text-nova-cyan" />
              <span>Event & Diagnostics Console</span>
            </div>
            <span className="text-[11px] text-slate-400">{logs.length} events logged</span>
          </div>

          <div ref={logContainerRef} className="flex-1 p-4 font-mono text-xs overflow-y-auto space-y-1 bg-nova-dark/90">
            {logs.length === 0 ? (
              <div className="text-slate-500 italic">No events recorded yet...</div>
            ) : (
              logs.map((log, index) => {
                const colorMap = {
                  info: 'text-slate-300',
                  warn: 'text-amber-400',
                  error: 'text-rose-400',
                  success: 'text-emerald-400',
                };
                return (
                  <div key={index} className="flex items-start space-x-2 leading-relaxed">
                    <span className="text-slate-500 shrink-0">[{log.timestamp}]</span>
                    <span className={`shrink-0 uppercase text-[10px] px-1 py-0.2 rounded font-semibold ${
                      log.level === 'error' ? 'bg-rose-500/20 text-rose-300' :
                      log.level === 'warn' ? 'bg-amber-500/20 text-amber-300' :
                      log.level === 'success' ? 'bg-emerald-500/20 text-emerald-300' :
                      'bg-slate-700/50 text-slate-400'
                    }`}>
                      {log.level}
                    </span>
                    <span className={colorMap[log.level]}>{log.message}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="px-6 py-2 bg-nova-panel border-t border-nova-border/70 flex items-center justify-between text-[11px] text-slate-400">
        <div>NOVA • Gemini Build Specification • Milestone 1 (Foundation)</div>
        <div className="flex items-center space-x-4">
          <span>Backend: <code className="text-slate-300">127.0.0.1:8000</code></span>
          <span>Frontend: <code className="text-slate-300">127.0.0.1:5173</code></span>
        </div>
      </footer>
    </div>
  );
}
