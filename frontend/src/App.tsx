import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Activity,
  Cpu,
  HardDrive,
  Power,
  RefreshCw,
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
  Mic,
  MicOff,
  Volume2,
  Square,
  AudioWaveform as Waveform,
  Wrench,
  AlertTriangle,
  XCircle,
  RotateCcw,
  Camera,
} from 'lucide-react';
import {
  HealthData,
  SystemStatusData,
  CommandResult,
  VoiceStatus,
  VoiceListenResult,
  ToolDefinition,
  ToolExecutionResult,
  AuditRecord,
} from './types';

const BACKEND_URL = 'http://127.0.0.1:8000';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

const SAMPLE_COMMANDS = [
  'sc le lo',
  'take screenshot',
  'spotify kholo please',
  'battery kitne percent bachi hai',
  'play lofi beats for focus',
  'volume 50 percent karo',
  'brightness 70 kar do',
  'pc lock karo',
  'downloads me resume.pdf dhoondo',
  'remind me to drink water at 5pm',
  'summarize this uploaded pdf report',
  'is python function me bug dhoond kar fix karo',
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

  // Phase 2: ML Command State
  const [commandInput, setCommandInput] = useState<string>('');
  const [isClassifying, setIsClassifying] = useState<boolean>(false);
  const [commandResult, setCommandResult] = useState<CommandResult | null>(null);

  // Phase 3: Voice Engine State
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>(null);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number>(0);
  const [voiceResult, setVoiceResult] = useState<VoiceListenResult | null>(null);
  const [isTogglingHandsFree, setIsTogglingHandsFree] = useState<boolean>(false);
  const lastEventTsRef = useRef<number>(0);

  // Phase 4: Safe Tools State
  const [toolsList, setToolsList] = useState<ToolDefinition[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditRecord[]>([]);
  const [lastToolResult, setLastToolResult] = useState<ToolExecutionResult | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<{
    token: string;
    prompt: string;
    toolName: string;
  } | null>(null);
  const [isExecutingTool, setIsExecutingTool] = useState<boolean>(false);

  const logContainerRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev.slice(-99), { timestamp, level, message }]);
  }, []);

  const openExternalUrl = useCallback(
    (url: string) => {
      if (!url) return;
      addLog(`Redirecting to Google Chrome: ${url}`, 'info');
      if (window.novaAPI?.openExternal) {
        window.novaAPI.openExternal(url).catch((err) => {
          console.warn('Electron openExternal error, falling back to window.open:', err);
          window.open(url, '_blank');
        });
      } else {
        window.open(url, '_blank');
      }
    },
    [addLog]
  );

  // Check Electron IPC presence
  useEffect(() => {
    if (window.novaAPI) {
      setIsElectron(true);
      addLog(`Initialized under Electron runtime (${window.novaAPI.platform})`, 'info');
      window.novaAPI
        .getLoginItemSettings()
        .then((enabled) => setAutoStartup(enabled))
        .catch(() => addLog('Failed to query auto-startup configuration.', 'warn'));
    } else {
      setIsElectron(false);
      addLog('Running in standard browser mode (Electron IPC disabled).', 'info');
    }
  }, [addLog]);

  // Fetch Safe Tools Catalog
  const fetchTools = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/tools`);
      if (res.ok) {
        const data = await res.json();
        setToolsList(data.tools || []);
      }
    } catch {
      // Backend not yet reachable
    }
  }, []);

  // Fetch Tool Audit History
  const fetchAuditLog = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/tools/audit?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setAuditEntries(data.entries || []);
      }
    } catch {
      // Ignore
    }
  }, []);

  // Fetch backend status
  const fetchStatus = useCallback(async () => {
    const start = performance.now();
    try {
      const [healthRes, statusRes, voiceRes] = await Promise.all([
        fetch(`${BACKEND_URL}/health`),
        fetch(`${BACKEND_URL}/api/status`),
        fetch(`${BACKEND_URL}/api/voice/status`).catch(() => null),
      ]);

      const roundtrip = Math.round(performance.now() - start);
      setLatencyMs(roundtrip);

      if (healthRes.ok && statusRes.ok) {
        const healthData: HealthData = await healthRes.json();
        const statusData: SystemStatusData = await statusRes.json();

        setHealth(healthData);
        setSystemStatus(statusData);
        setIsBackendConnected(true);

        if (voiceRes && voiceRes.ok) {
          const vData: VoiceStatus = await voiceRes.json();
          setVoiceStatus(vData);

          // Real-time reaction to hands-free background wake word triggers
          if (
            vData.last_event &&
            vData.last_event.timestamp &&
            vData.last_event.timestamp > lastEventTsRef.current
          ) {
            lastEventTsRef.current = vData.last_event.timestamp;
            setVoiceResult(vData.last_event);
            if (vData.last_event.transcript) {
              addLog(`🎙️ Wake Word Activated: "${vData.last_event.transcript}"`, 'success');
            }
            if ((vData.last_event as any).media_paused) {
              addLog('⏸️ Active media paused to hear your command clearly.', 'info');
            }
            if (vData.last_event.prediction) {
              setCommandResult(vData.last_event.prediction);
              addLog(
                `ML Intent Identified: ${vData.last_event.prediction.intent} (${vData.last_event.prediction.confidence_percent}%)`,
                'info'
              );
              const redirectUrl =
                vData.last_event.prediction.tool_result?.data?.url ||
                vData.last_event.prediction.tool_result?.data?.search_url;
              if (redirectUrl) {
                openExternalUrl(redirectUrl);
              }
            }
            if (vData.last_event.spoken_response) {
              addLog(`NOVA Spoke: "${vData.last_event.spoken_response}"`, 'info');
            }
          }
        }
      } else {
        setIsBackendConnected(false);
      }
    } catch {
      setIsBackendConnected(false);
    }
  }, []);

  // Initial data bootstrap
  useEffect(() => {
    fetchStatus();
    fetchTools();
    fetchAuditLog();
  }, [fetchStatus, fetchTools, fetchAuditLog]);

  // Low-latency polling for voice status & wake-word events (snappy 1000ms when hands-free is active)
  useEffect(() => {
    const pollInterval = voiceStatus?.hands_free_active ? 1000 : 3500;
    const interval = setInterval(() => {
      fetchStatus();
    }, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, voiceStatus?.hands_free_active]);

  // Periodic audit log polling
  useEffect(() => {
    const interval = setInterval(() => {
      fetchAuditLog();
    }, 4000);
    return () => clearInterval(interval);
  }, [fetchAuditLog]);

  // Execute Safe Tool
  const handleExecuteTool = async (toolName: string, args: Record<string, any> = {}) => {
    setIsExecutingTool(true);
    addLog(`Executing safe tool '${toolName}'...`, 'info');
    try {
      const res = await fetch(`${BACKEND_URL}/api/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName, args }),
      });
      const data = await res.json();
      const result: ToolExecutionResult = data.result;
      setLastToolResult(result);

      if (result.requires_confirmation && result.confirmation_token) {
        setPendingConfirmation({
          token: result.confirmation_token,
          prompt: result.confirmation_prompt || 'Are you sure you want to proceed?',
          toolName: result.tool_name,
        });
        addLog(`⚠️ Confirmation required for '${toolName}': ${result.confirmation_prompt}`, 'warn');
      } else if (result.success) {
        addLog(`Tool '${toolName}' executed successfully. Verification: ${result.verification?.method ?? 'Checked'}`, 'success');
      } else {
        addLog(`Tool '${toolName}' failed: ${result.error || result.output}`, 'error');
      }
      fetchAuditLog();
    } catch (err) {
      addLog(`Tool execution network error: ${err}`, 'error');
    } finally {
      setIsExecutingTool(false);
    }
  };

  // Confirm sensitive action
  const handleConfirmAction = async (token: string) => {
    try {
      addLog(`Sending explicit user confirmation for token ${token}...`, 'info');
      const res = await fetch(`${BACKEND_URL}/api/tools/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      setLastToolResult(data.result);
      setPendingConfirmation(null);
      addLog(`Confirmed action executed: ${data.result?.output}`, 'success');
      fetchAuditLog();
    } catch (err) {
      addLog(`Confirmation error: ${err}`, 'error');
    }
  };

  // Reject sensitive action
  const handleRejectAction = async (token: string) => {
    try {
      addLog(`User rejected confirmation for token ${token}.`, 'warn');
      await fetch(`${BACKEND_URL}/api/tools/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      setPendingConfirmation(null);
      addLog(`Action successfully cancelled.`, 'info');
      fetchAuditLog();
    } catch (err) {
      addLog(`Rejection error: ${err}`, 'error');
    }
  };

  // Phase 3: Voice Listen Once with live countdown timer
  const handleListenOnce = async () => {
    if (isListening) return;
    setIsListening(true);
    setCountdown(4);
    addLog('Mic activated: Listening for speech input (4.5s window)...', 'info');

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    try {
      const res = await fetch(`${BACKEND_URL}/api/voice/listen-once`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_seconds: 4.5 }),
      });

      clearInterval(timer);
      setCountdown(0);

      if (res.ok) {
        const data: VoiceListenResult = await res.json();
        setVoiceResult(data);

        if (data.status === 'success' && data.transcript) {
          addLog(`Voice Transcription: "${data.transcript}"`, 'success');
          if (data.prediction) {
            setCommandResult(data.prediction);
            addLog(
              `ML Intent Identified: ${data.prediction.intent} (${data.prediction.confidence_percent}%)`,
              'info'
            );
            const redirectUrl =
              data.prediction.tool_result?.data?.url ||
              data.prediction.tool_result?.data?.search_url;
            if (redirectUrl) {
              openExternalUrl(redirectUrl);
            }
          }
          if (data.spoken_response) {
            addLog(`NOVA Spoke: "${data.spoken_response}"`, 'info');
          }
        } else if (data.status === 'no_speech' || !data.transcript) {
          addLog('Koi speech detect nahi hui. Kripya thoda paas aakar bolein.', 'warn');
        } else if (data.status === 'muted') {
          addLog('Microphone is currently muted.', 'warn');
        }
      } else {
        addLog('Voice listen endpoint returned non-200 status.', 'error');
      }
    } catch (err) {
      clearInterval(timer);
      setCountdown(0);
      addLog(`Voice error: ${err}`, 'error');
    } finally {
      setIsListening(false);
      fetchStatus();
      fetchAuditLog();
    }
  };

  // Test Speech Synthesis
  const handleTestTTS = async () => {
    addLog('Testing local speech synthesis (SAPI5)...', 'info');
    try {
      const res = await fetch(`${BACKEND_URL}/api/voice/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'Hello, I am NOVA. Local speech synthesis is active and running.' }),
      });
      if (res.ok) {
        addLog('TTS speech synthesis played successfully.', 'success');
      }
    } catch (err) {
      addLog(`TTS failed: ${err}`, 'error');
    }
  };

  // Interrupt Speech
  const handleInterrupt = async () => {
    addLog('Interrupt signal sent to NOVA Voice Engine.', 'warn');
    try {
      await fetch(`${BACKEND_URL}/api/voice/interrupt`, { method: 'POST' });
    } catch (err) {
      addLog(`Interrupt error: ${err}`, 'error');
    }
  };

  // Toggle Mute
  const handleToggleMute = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/voice/toggle-mute`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        addLog(`Microphone is now ${data.is_muted ? 'MUTED' : 'UNMUTED'}`, data.is_muted ? 'warn' : 'info');
        setVoiceStatus((prev) => (prev ? { ...prev, is_muted: data.is_muted } : null));
      }
    } catch (err) {
      addLog(`Toggle mute failed: ${err}`, 'error');
    }
  };

  // Toggle Continuous Hands-Free Wake Word Mode
  const handleToggleHandsFree = async () => {
    setIsTogglingHandsFree(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/voice/hands-free/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setVoiceStatus((prev) => (prev ? { ...prev, hands_free_active: data.hands_free_active } : null));
        addLog(
          `Hands-Free 'Hey NOVA' wake-word mode ${data.hands_free_active ? 'ACTIVATED' : 'DEACTIVATED'}`,
          data.hands_free_active ? 'success' : 'warn'
        );
      }
    } catch (err) {
      addLog(`Failed to toggle hands-free mode: ${err}`, 'error');
    } finally {
      setIsTogglingHandsFree(false);
    }
  };

  // Classify command
  const handleClassifyCommand = async (textToClassify?: string) => {
    const text = textToClassify ?? commandInput;
    if (!text.trim()) return;

    setIsClassifying(true);
    addLog(`Sending command: "${text}"`, 'info');

    try {
      const res = await fetch(`${BACKEND_URL}/api/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (res.ok) {
        const result: CommandResult = await res.json();
        setCommandResult(result);

        if (result.needs_clarification) {
          addLog(
            `Unknown/Low-confidence command: "${text}" (Score: ${result.confidence_percent}%). Clarification requested.`,
            'warn'
          );
        } else {
          addLog(
            `Intent: ${result.intent} | Confidence: ${result.confidence_percent}% | Latency: ${result.latency_ms}ms`,
            'success'
          );
          if (result.executed_tool) {
            addLog(`Dispatched safe tool: '${result.executed_tool}'`, 'info');
          }
          const redirectUrl =
            result.tool_result?.data?.url || result.tool_result?.data?.search_url;
          if (redirectUrl) {
            openExternalUrl(redirectUrl);
          }
        }
        fetchAuditLog();
      } else {
        addLog(`ML classification failed with status ${res.status}`, 'error');
      }
    } catch (err) {
      addLog(`Classification error: ${err}`, 'error');
    } finally {
      setIsClassifying(false);
    }
  };

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    addLog('Manual diagnostic refresh requested.', 'info');
    await Promise.all([fetchStatus(), fetchTools(), fetchAuditLog()]);
    setIsRefreshing(false);
    addLog('Diagnostic metrics refreshed.', 'success');
  };

  const toggleAutoStartup = async () => {
    if (!window.novaAPI) {
      addLog('Auto-startup toggle is only available in Electron desktop shell.', 'warn');
      return;
    }
    const nextState = !autoStartup;
    try {
      const success = await window.novaAPI.setLoginItemSettings(nextState);
      if (success) {
        setAutoStartup(nextState);
        addLog(`Windows auto-startup changed to: ${nextState ? 'ENABLED' : 'DISABLED'}`, 'success');
      }
    } catch {
      addLog('Failed to update Windows login settings.', 'error');
    }
  };

  const handleMinimizeToTray = () => {
    if (window.novaAPI) {
      addLog('Minimizing to system tray resident state.', 'info');
      window.novaAPI.minimizeToTray();
    }
  };

  const handleQuit = () => {
    if (window.novaAPI) {
      addLog('Terminating application.', 'warn');
      window.novaAPI.quitApp();
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-nova-dark text-slate-100 font-sans select-none overflow-hidden">
      {/* Top Navigation Bar */}
      <header className="h-12 border-b border-nova-border bg-nova-panel flex items-center justify-between px-4 z-10 shrink-0">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-nova-cyan animate-pulse shadow-[0_0_8px_#06b6d4]" />
            <span className="font-bold tracking-wider text-sm text-white">
              {health?.app ? `${health.app} v${health.version}` : 'NOVA 2.0'}
            </span>
          </div>
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/80 text-nova-cyan border border-cyan-800/40">
            Phase 4: Safe Tools & Execution
          </span>
          {isElectron && (
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800/40">
              Desktop Shell (Sandboxed)
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {/* Connection Status Indicator */}
          <div className="flex items-center space-x-2 px-2.5 py-1 rounded bg-nova-card border border-nova-border text-xs">
            <Radio
              className={`w-3.5 h-3.5 ${
                isBackendConnected ? 'text-emerald-400 animate-pulse' : 'text-rose-500'
              }`}
            />
            <span className="font-medium text-[11px]">
              {isBackendConnected
                ? `FastAPI: Connected (${latencyMs ?? 0}ms)`
                : 'FastAPI: Disconnected'}
            </span>
          </div>

          <button
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
            title="Refresh Diagnostics"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-nova-cyan' : ''}`} />
          </button>

          {isElectron && (
            <>
              <button
                onClick={handleMinimizeToTray}
                className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
                title="Minimize to System Tray"
              >
                <Minimize2 className="w-4 h-4" />
              </button>
              <button
                onClick={handleQuit}
                className="p-1.5 rounded hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 transition"
                title="Quit NOVA"
              >
                <Power className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </header>

      {/* Main Scrollable Dashboard Content */}
      <main className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Hardware & System Resource Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* CPU Card */}
          <div className="p-4 rounded-xl bg-nova-panel border border-nova-border shadow-md space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span className="font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-nova-cyan" /> CPU Load
              </span>
              <span className="font-mono text-nova-cyan">
                {systemStatus?.resources.cpu_percent ?? 0}%
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-nova-cyan transition-all duration-300"
                style={{ width: `${systemStatus?.resources.cpu_percent ?? 0}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-500 truncate">
              {systemStatus?.system.processor ?? 'AMD Ryzen 5 5600H'}
            </p>
          </div>

          {/* RAM Card */}
          <div className="p-4 rounded-xl bg-nova-panel border border-nova-border shadow-md space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span className="font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-purple-400" /> Memory (RAM)
              </span>
              <span className="font-mono text-purple-400">
                {systemStatus?.resources.ram_percent ?? 0}%
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-purple-500 transition-all duration-300"
                style={{ width: `${systemStatus?.resources.ram_percent ?? 0}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-500">
              {systemStatus
                ? `${systemStatus.resources.ram_used_gb} GB used of ${systemStatus.resources.ram_total_gb} GB`
                : '16.0 GB total'}
            </p>
          </div>

          {/* Storage Card */}
          <div className="p-4 rounded-xl bg-nova-panel border border-nova-border shadow-md space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span className="font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <HardDrive className="w-4 h-4 text-emerald-400" /> SSD Storage (C:)
              </span>
              <span className="font-mono text-emerald-400">
                {systemStatus?.resources.disk_percent ?? 0}%
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${systemStatus?.resources.disk_percent ?? 0}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-500">
              {systemStatus
                ? `${systemStatus.resources.disk_free_gb} GB free of ${systemStatus.resources.disk_total_gb} GB`
                : 'Storage ready'}
            </p>
          </div>

          {/* Foundation & Settings Card */}
          <div className="p-4 rounded-xl bg-nova-panel border border-nova-border shadow-md flex flex-col justify-between">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span className="font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Settings className="w-4 h-4 text-amber-400" /> Startup & Tray
              </span>
              <span className="text-emerald-400 flex items-center gap-1 text-[11px]">
                <CheckCircle2 className="w-3 h-3" /> Ready
              </span>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-300">Run at Windows Login:</span>
              <button
                onClick={toggleAutoStartup}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  autoStartup ? 'bg-nova-cyan' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                    autoStartup ? 'translate-x-4' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="pt-2 border-t border-nova-border/60 flex items-center gap-2 text-[11px] text-slate-400">
              <Activity className="w-3.5 h-3.5 text-purple-400" />
              IPC Security: Sandboxed contextBridge
            </div>
          </div>
        </div>

        {/* Phase 4: SAFE TOOLS & PERMISSION-CONTROLLED EXECUTION MODULE */}
        <div className="rounded-xl bg-gradient-to-r from-slate-900 to-nova-panel border border-emerald-500/30 shadow-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                  Safe Tools & Execution Engine (Allowlisted & Sandboxed)
                </h2>
                <p className="text-[11px] text-slate-400">
                  Strict process bounds • Zero arbitrary shell execution • Path sandboxing • Post-action verification
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 font-mono">
                {toolsList.length} Allowlisted Tools
              </span>
              <button
                onClick={fetchAuditLog}
                className="px-2.5 py-1 rounded bg-nova-card hover:bg-slate-700 text-slate-300 border border-nova-border text-xs flex items-center gap-1.5 transition"
              >
                <RotateCcw className="w-3 h-3 text-emerald-400" />
                Audit Logs
              </button>
            </div>
          </div>

          {/* Quick Tool Execution Buttons */}
          <div className="space-y-2">
            <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
              <Wrench className="w-3.5 h-3.5 text-emerald-400" />
              Instant Tool Testers:
            </span>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleExecuteTool('launch_app', { app_name: 'notepad' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                📝 Launch Notepad
              </button>

              <button
                onClick={() => handleExecuteTool('launch_app', { app_name: 'calc' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                🧮 Launch Calculator
              </button>

              <button
                onClick={() => handleExecuteTool('take_screenshot', {})}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-xs font-semibold text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5 transition"
              >
                <Camera className="w-3.5 h-3.5 text-cyan-400" />
                📸 Take Screenshot (SC)
              </button>

              <button
                onClick={() => handleExecuteTool('system_control', { action: 'set_volume', value: 50 })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                🔊 Volume 50%
              </button>

              <button
                onClick={() => handleExecuteTool('system_control', { action: 'set_brightness', value: 70 })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                🔆 Brightness 70%
              </button>

              <button
                onClick={() => handleExecuteTool('system_control', { action: 'lock_workstation' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-xs font-semibold text-amber-300 border border-amber-500/30 flex items-center gap-1.5 transition"
              >
                🔒 Lock PC
              </button>

              <button
                onClick={() => handleExecuteTool('system_status', { metric_filter: 'battery' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                🔋 Read Battery
              </button>

              <button
                onClick={() => handleExecuteTool('media_control', { action: 'play_pause' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                ⏯️ Media Play/Pause
              </button>

              <button
                onClick={() => handleExecuteTool('web_search', { query: 'FastAPI Python desktop AI' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                🌐 Safe Web Search
              </button>

              <button
                onClick={() => handleExecuteTool('list_files', { directory_path: '.' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                📁 List Workspace Files
              </button>

              <button
                onClick={() => handleExecuteTool('search_files', { query: '*.py', root_dir: '.' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
              >
                🔍 Search *.py Files
              </button>

              <button
                onClick={() => handleExecuteTool('create_file', { file_path: 'backend/tests/_test_scratch.txt', content: 'Testing safe create tool!' })}
                disabled={isExecutingTool}
                className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-xs font-semibold text-rose-300 border border-rose-500/30 flex items-center gap-1.5 transition"
              >
                ⚠️ Test High-Risk Overwrite
              </button>
            </div>
          </div>

          {/* Pending User Confirmation Dialog / Banner */}
          {pendingConfirmation && (
            <div className="p-4 rounded-xl bg-amber-950/60 border border-amber-500/50 space-y-3 animate-pulse">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-200">
                      User Permission Confirmation Required
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300">
                      Token: {pendingConfirmation.token.substring(0, 8)}...
                    </span>
                  </div>
                  <p className="text-xs text-amber-100">{pendingConfirmation.prompt}</p>
                </div>
              </div>

              <div className="flex items-center gap-3 justify-end pt-1">
                <button
                  onClick={() => handleRejectAction(pendingConfirmation.token)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 border border-slate-700 flex items-center gap-1.5 transition"
                >
                  <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  Reject / Cancel
                </button>
                <button
                  onClick={() => handleConfirmAction(pendingConfirmation.token)}
                  className="px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold flex items-center gap-1.5 transition shadow-lg shadow-amber-500/30"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Approve Execution
                </button>
              </div>
            </div>
          )}

          {/* Last Execution Outcome Card */}
          {lastToolResult && (
            <div className="p-4 rounded-xl bg-nova-dark/90 border border-emerald-500/30 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-400">Tool Executed:</span>
                  <span className="font-mono text-emerald-300 text-sm font-bold">
                    {lastToolResult.tool_name}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                      lastToolResult.success
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                    }`}
                  >
                    {lastToolResult.success ? 'Success' : 'Failed'}
                  </span>
                </div>

                {lastToolResult.verification && (
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-300 font-mono">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>
                      Verified ({lastToolResult.verification.method})
                    </span>
                  </div>
                )}
              </div>

              <div className="p-3 rounded-lg bg-slate-900 border border-nova-border font-mono text-xs text-slate-200">
                {lastToolResult.output}
              </div>
            </div>
          )}

          {/* Tool Audit Log Strip */}
          <div className="space-y-1.5 pt-1">
            <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
              Recent Tool Audit Trail:
            </span>
            <div className="max-h-36 overflow-y-auto rounded-lg bg-nova-dark/80 border border-nova-border text-xs divide-y divide-nova-border/50">
              {auditEntries.length === 0 ? (
                <div className="p-3 text-slate-500 italic">No tool calls recorded yet.</div>
              ) : (
                auditEntries.slice(0, 5).map((entry) => (
                  <div key={entry.id} className="p-2.5 flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-slate-400 text-[10px]">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </span>
                      <span className="font-semibold text-white">{entry.tool_name}</span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold ${
                          entry.status === 'SUCCESS'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : entry.status === 'BLOCKED'
                            ? 'bg-rose-500/20 text-rose-300'
                            : 'bg-amber-500/20 text-amber-300'
                        }`}
                      >
                        {entry.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-slate-400 font-mono">
                      <span>{entry.duration_ms}ms</span>
                      <span className="text-emerald-400">{entry.verification_status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Phase 3: Voice Engine & Interaction Module */}
        <div className="rounded-xl bg-gradient-to-r from-slate-900 to-nova-panel border border-cyan-500/30 shadow-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
                <Waveform className="w-5 h-5 text-nova-cyan animate-pulse" />
              </div>
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                  Voice Engine • Local Wake Word & Faster-Whisper
                </h2>
                <p className="text-[11px] text-slate-400">
                  Wake phrase: &quot;Hey NOVA&quot; • Local Speech Synthesis (SAPI5)
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleToggleMute}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition ${
                  voiceStatus?.is_muted
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                    : 'bg-nova-card hover:bg-slate-700 text-slate-300 border-nova-border'
                }`}
              >
                {voiceStatus?.is_muted ? <MicOff className="w-3.5 h-3.5 text-rose-400" /> : <Mic className="w-3.5 h-3.5 text-nova-cyan" />}
                {voiceStatus?.is_muted ? 'Muted' : 'Mic Active'}
              </button>

              <button
                onClick={handleTestTTS}
                className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-slate-300 border border-nova-border text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <Volume2 className="w-3.5 h-3.5 text-purple-400" />
                Test Voice
              </button>

              <button
                onClick={handleToggleHandsFree}
                disabled={isTogglingHandsFree}
                title="Continuous background wake-word activation (Hey NOVA)"
                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition ${
                  voiceStatus?.hands_free_active
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30 shadow-lg shadow-emerald-500/10'
                    : 'bg-nova-card hover:bg-slate-700 text-slate-400 border-nova-border hover:text-slate-200'
                }`}
              >
                <Radio className={`w-3.5 h-3.5 ${voiceStatus?.hands_free_active ? 'animate-pulse text-emerald-400' : ''}`} />
                <span>Hands-Free {voiceStatus?.hands_free_active ? 'ON' : 'OFF'}</span>
              </button>

              <button
                onClick={handleInterrupt}
                title="Stop / Interrupt Voice"
                className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <Square className="w-3.5 h-3.5" />
                Interrupt
              </button>
            </div>
          </div>

          {/* Voice Action Hero Bar */}
          <div className="flex flex-col sm:flex-row items-center gap-4 p-4 rounded-xl bg-nova-dark/90 border border-nova-border">
            <button
              onClick={handleListenOnce}
              disabled={isListening || voiceStatus?.is_muted}
              className={`relative flex items-center justify-center w-16 h-16 rounded-full transition-all duration-300 ${
                isListening
                  ? 'bg-rose-500 text-white animate-pulse shadow-lg shadow-rose-500/50'
                  : 'bg-nova-cyan hover:bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/30'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <Mic className="w-7 h-7" />
              {isListening && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-400 animate-ping" />
              )}
            </button>

            <div className="flex-1 space-y-1.5 w-full">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-white">
                  {isListening
                    ? `🎙️ Recording... Speak your command now! (${countdown > 0 ? countdown + 's' : 'Transcribing...'})`
                    : 'Click microphone or say "Hey NOVA" to give a voice command'}
                </span>
                <span className="font-mono text-slate-400">
                  State: <strong className="text-nova-cyan">{isListening ? 'LISTENING' : voiceStatus?.state ?? 'IDLE'}</strong>
                </span>
              </div>

              {/* Volume / Audio Waveform Meter */}
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-150 ${
                    isListening ? 'bg-gradient-to-r from-cyan-400 to-rose-400 animate-pulse' : 'bg-cyan-500'
                  }`}
                  style={{ width: `${Math.max(10, Math.min(100, (voiceStatus?.volume_level ?? 0) * 100))}%` }}
                />
              </div>

              <div className="text-[11px] text-slate-400 flex items-center gap-3">
                {voiceStatus?.hands_free_active ? (
                  <span className="text-emerald-400 font-medium flex items-center gap-1 animate-pulse">
                    🟢 Hands-Free Wake Word Active: Say &quot;Hey NOVA&quot; anytime
                  </span>
                ) : (
                  <span>Wake phrase: &quot;Hey NOVA&quot; (Click Hands-Free to listen continuously)</span>
                )}
                <span>•</span>
                <span>Speech Model: Faster-Whisper (Quantized int8)</span>
                <span>•</span>
                <span>VAD: Sensitive Human Voice Threshold Active</span>
              </div>
            </div>
          </div>

          {/* Voice Response Output Card */}
          {voiceResult && (
            <div className="p-4 rounded-lg bg-nova-dark/95 border border-cyan-500/30 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-400">You Said:</span>
                  <span className="font-mono text-white text-sm">
                    &quot;{voiceResult.transcript || 'Koi aawaz sunayi nahi di'}&quot;
                  </span>
                </div>
                {voiceResult.wake_word_detected && (
                  <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-nova-cyan border border-cyan-500/40 text-[10px] font-bold uppercase tracking-wider">
                    Wake Word Detected
                  </span>
                )}
              </div>

              {voiceResult.spoken_response && (
                <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-xs text-cyan-200 flex items-center gap-2">
                  <Volume2 className="w-4 h-4 text-nova-cyan shrink-0" />
                  <div>
                    <strong className="text-white">NOVA: </strong>
                    <span>{voiceResult.spoken_response}</span>
                  </div>
                </div>
              )}

              {voiceResult.prediction?.tool_result?.data?.url && (
                <div className="mt-2 p-3 rounded-lg bg-red-950/40 border border-red-500/40 flex items-center justify-between text-xs text-red-200">
                  <div className="flex items-center gap-2">
                    <span className="text-base">▶️</span>
                    <div>
                      <strong className="text-white">Google Chrome: </strong>
                      <span>Playing &quot;{voiceResult.prediction.tool_result.data.track || 'Song'}&quot; in Google Chrome...</span>
                    </div>
                  </div>
                  <a
                    href={voiceResult.prediction.tool_result.data.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => {
                      e.preventDefault();
                      openExternalUrl(voiceResult.prediction!.tool_result!.data!.url);
                    }}
                    className="px-3 py-1 rounded bg-red-600 hover:bg-red-500 text-white font-medium text-[11px] transition-colors"
                  >
                    ▶ Play in Chrome
                  </a>
                </div>
              )}
            </div>
          )}
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
              placeholder="Type any desktop command in English or Hinglish (e.g. 'sc le lo', 'spotify kholo', 'battery kitne percent hai')..."
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

              {/* YouTube Media Redirect Banner */}
              {commandResult.tool_result?.data?.url && (
                <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 flex items-center justify-between text-xs text-red-200">
                  <div className="flex items-center gap-2">
                    <span className="text-base">▶️</span>
                    <div>
                      <strong className="text-white">Google Chrome: </strong>
                      <span>Playing &quot;{commandResult.tool_result.data.track || 'Song'}&quot; in Google Chrome...</span>
                    </div>
                  </div>
                  <a
                    href={commandResult.tool_result.data.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => {
                      e.preventDefault();
                      openExternalUrl(commandResult.tool_result!.data!.url);
                    }}
                    className="px-3 py-1 rounded bg-red-600 hover:bg-red-500 text-white font-medium text-[11px] transition-colors"
                  >
                    ▶ Play in Chrome
                  </a>
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
        <div>NOVA • Gemini Build Specification • Phase 4 (Safe Tools & SC / Voice Engine Active)</div>
        <div className="flex items-center space-x-4">
          <span>Backend: <code className="text-slate-300">127.0.0.1:8000</code></span>
          <span>Frontend: <code className="text-slate-300">127.0.0.1:5173</code></span>
        </div>
      </footer>
    </div>
  );
}
