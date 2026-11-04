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
  Send,
  Sparkles,
  HelpCircle,
  Clock,
  Layers,
} from 'lucide-react';
import { HealthData, SystemStatusData, CommandResult } from './types';

const BACKEND_URL = 'http://127.0.0.1:8000';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

const SAMPLE_COMMANDS = [
  'spotify kholo please',
  'play lofi beats for focus',
  'downloads me resume.pdf dhoondo',
  'battery kitne percent bachi hai',
  'remind me to drink water at 5pm',
  'summarize this uploaded pdf report',
  'is python function me bug dhoond kar fix karo',
  'quantum mechanics photon entanglement',
];

export default function App(): React.JSX.Element {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [autoStartup, setAutoStartup] = useState<boolean>(false);
  const [isElectron, setIsElectron] = useState<boolean>(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [commandInput, setCommandInput] = useState<string>('');
  const [isClassifying, setIsClassifying] = useState<boolean>(false);
  const [commandResult, setCommandResult] = useState<CommandResult | null>(null);

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
          addLog(
            `Connected to FastAPI backend: ${healthJson.app} (v${healthJson.version}) in ${roundTrip}ms`,
            'success'
          );
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

  const handleClassifyCommand = async (textToClassify?: string) => {
    const text = (textToClassify ?? commandInput).trim();
    if (!text) return;

    setIsClassifying(true);
    addLog(`Classifying command: "${text}"`, 'info');

    try {
      const res = await fetch(`${BACKEND_URL}/api/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const result: CommandResult = await res.json();
      setCommandResult(result);

      if (result.needs_clarification) {
        addLog(
          `Command flagged UNKNOWN_INTENT (Confidence: ${result.confidence_percent}% < 65% threshold)`,
          'warn'
        );
      } else {
        addLog(
          `Classified as ${result.intent} (${result.confidence_percent}% confidence in ${result.latency_ms}ms)`,
          'success'
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog(`Classification failed: ${msg}`, 'error');
    } finally {
      setIsClassifying(false);
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
              NOVA{' '}
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Phase 2: ML Brain
              </span>
            </h1>
            <p className="text-[11px] text-slate-400">Desktop AI Assistant • Local ML Intent Classifier</p>
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
                ML Model: <span className="text-emerald-400 font-mono font-medium">{systemStatus?.app.ml_model ?? 'Multinomial Naive Bayes'}</span>
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
                  <span className="font-mono text-slate-200">{health ? `${health.uptime_seconds}s` : '0s'}</span>
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
              <div className="text-xs text-slate-400 mb-4">Single Instance & Tray Resident</div>

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

        {/* Phase 2: Live ML Intent Classifier Testing Module */}
        <div className="rounded-xl bg-nova-panel border border-nova-border shadow-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-nova-cyan" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Live Intent Classification Engine (English & Hinglish)
              </h2>
            </div>
            <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-nova-cyan/10 text-nova-cyan border border-nova-cyan/30">
              Trained Model: {systemStatus?.app.ml_model ?? 'MultinomialNB'}
            </span>
          </div>

          {/* Command Input Box */}
          <div className="flex gap-2">
            <input
              type="text"
              value={commandInput}
              onChange={(e) => setCommandInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleClassifyCommand()}
              placeholder="Type any desktop command in English or Hinglish (e.g. 'spotify kholo', 'find resume.pdf in downloads', 'ram kitna bacha hai')..."
              className="flex-1 px-4 py-2.5 rounded-lg bg-nova-dark border border-nova-border focus:border-nova-cyan focus:outline-none text-sm text-white placeholder-slate-500 font-mono"
            />
            <button
              onClick={() => handleClassifyCommand()}
              disabled={isClassifying || !commandInput.trim()}
              className="px-5 py-2.5 rounded-lg bg-nova-cyan hover:bg-cyan-400 text-slate-950 font-semibold text-sm flex items-center gap-2 disabled:opacity-50 transition"
            >
              <Send className="w-4 h-4" />
              {isClassifying ? 'Classifying...' : 'Classify'}
            </button>
          </div>

          {/* Sample Command Chips */}
          <div className="space-y-1.5">
            <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
              Quick Test Prompts:
            </span>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_COMMANDS.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setCommandInput(sample);
                    handleClassifyCommand(sample);
                  }}
                  className="text-xs px-2.5 py-1 rounded-md bg-nova-card hover:bg-slate-700 text-slate-300 border border-nova-border/80 transition font-mono"
                >
                  {sample}
                </button>
              ))}
            </div>
          </div>

          {/* Classification Results Card */}
          {commandResult && (
            <div className="p-4 rounded-lg bg-nova-dark/80 border border-nova-border space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider ${
                      commandResult.needs_clarification
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    }`}
                  >
                    {commandResult.intent}
                  </span>
                  <span className="text-xs text-slate-400">
                    Confidence:{' '}
                    <strong className="text-white font-mono">{commandResult.confidence_percent}%</strong>
                  </span>
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-nova-cyan" />
                    Latency: <strong className="text-nova-cyan font-mono">{commandResult.latency_ms}ms</strong>
                  </span>
                </div>

                {commandResult.entities && Object.keys(commandResult.entities).length > 0 && (
                  <div className="flex items-center gap-1.5 text-xs">
                    <Layers className="w-3.5 h-3.5 text-purple-400" />
                    <span className="text-slate-400">Entities:</span>
                    {Object.entries(commandResult.entities).map(([k, v]) => (
                      <span key={k} className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono text-[11px]">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Real-time Answer / Execution Preview */}
              {commandResult.live_response && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 flex items-center gap-2">
                  <span className="font-bold text-white text-[11px] uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/20">Answer</span>
                  <span className="font-medium text-emerald-200 text-sm">{commandResult.live_response}</span>
                </div>
              )}

              {/* Confidence Progress Bar */}
              <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    commandResult.needs_clarification
                      ? 'bg-amber-400'
                      : 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  }`}
                  style={{ width: `${commandResult.confidence_percent}%` }}
                />
              </div>

              {/* Clarification Box if Low Confidence */}
              {commandResult.needs_clarification && (
                <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5 text-xs text-amber-300">
                  <HelpCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <strong>Low Confidence Safety Threshold Active:</strong> {commandResult.clarification_message}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Diagnostics & Logs Terminal */}
        <div className="rounded-xl bg-nova-panel border border-nova-border shadow-lg overflow-hidden flex flex-col h-56">
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
                    <span
                      className={`shrink-0 uppercase text-[10px] px-1 py-0.2 rounded font-semibold ${
                        log.level === 'error'
                          ? 'bg-rose-500/20 text-rose-300'
                          : log.level === 'warn'
                          ? 'bg-amber-500/20 text-amber-300'
                          : log.level === 'success'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-slate-700/50 text-slate-400'
                      }`}
                    >
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
        <div>NOVA • Gemini Build Specification • Phase 2 (ML Brain Verified)</div>
        <div className="flex items-center space-x-4">
          <span>Backend: <code className="text-slate-300">127.0.0.1:8000</code></span>
          <span>Frontend: <code className="text-slate-300">127.0.0.1:5173</code></span>
        </div>
      </footer>
    </div>
  );
}
