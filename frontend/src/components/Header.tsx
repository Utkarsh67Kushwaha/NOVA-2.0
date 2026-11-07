import React from 'react';
import { Radio, RefreshCw, Sparkles, Minimize2, Power } from 'lucide-react';
import { HealthData } from '../types';

export interface HeaderProps {
  health: HealthData | null;
  isElectron: boolean;
  isBackendConnected: boolean;
  latencyMs: number | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  onOpenSpotlight: () => void;
  onMinimizeToTray: () => void;
  onQuit: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  isElectron,
  isBackendConnected,
  latencyMs,
  isRefreshing,
  onRefresh,
  onOpenSpotlight,
  onMinimizeToTray,
  onQuit,
}) => {
  return (
    <header className="h-12 border-b border-nova-border bg-nova-panel flex items-center justify-between px-4 z-10 shrink-0">
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-nova-cyan animate-pulse shadow-[0_0_8px_#06b6d4]" />
          <span className="font-bold tracking-wider text-sm text-white">
            {health?.app ? `${health.app} v${health.version}` : 'NOVA 2.0'}
          </span>
        </div>
        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/80 text-nova-cyan border border-cyan-800/40">
          Phase 5: Context & Intelligence
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
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
          title="Refresh Diagnostics"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-nova-cyan' : ''}`} />
        </button>

        {isElectron && (
          <>
            <button
              onClick={onOpenSpotlight}
              className="p-1.5 rounded hover:bg-cyan-950/50 text-nova-cyan hover:text-white transition flex items-center gap-1 border border-cyan-800/40 text-xs px-2"
              title="Switch to Compact Spotlight HUD (Ctrl+Shift+Space)"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span className="hidden sm:inline text-[11px] font-mono">Spotlight HUD</span>
            </button>
            <button
              onClick={onMinimizeToTray}
              className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Minimize to System Tray"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
            <button
              onClick={onQuit}
              className="p-1.5 rounded hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 transition"
              title="Quit NOVA"
            >
              <Power className="w-4 h-4" />
            </button>
          </>
        )}
      </div>
    </header>
  );
};
