import React from 'react';
import { Sparkles, Layers, Minimize2, Mic, MicOff, Send, CheckCircle2 } from 'lucide-react';
import { CommandResult, VoiceListenResult } from '../types';

export interface SpotlightHUDProps {
  geminiModel?: string;
  commandInput: string;
  setCommandInput: (val: string) => void;
  isListening: boolean;
  isClassifying: boolean;
  commandResult: CommandResult | null;
  voiceResult: VoiceListenResult | null;
  onExecute: () => void;
  onToggleListen: () => void;
  onExpandDashboard: () => void;
  onMinimize: () => void;
  inputRef: React.RefObject<HTMLInputElement>;
}

export const SpotlightHUD: React.FC<SpotlightHUDProps> = ({
  geminiModel,
  commandInput,
  setCommandInput,
  isListening,
  isClassifying,
  commandResult,
  voiceResult,
  onExecute,
  onToggleListen,
  onExpandDashboard,
  onMinimize,
  inputRef,
}) => {
  return (
    <div className="flex flex-col h-screen w-screen bg-[#080c14]/95 backdrop-blur-xl text-slate-100 font-sans select-none overflow-hidden p-3 justify-center items-center">
      <div className="w-full max-w-2xl bg-slate-900/90 border border-cyan-500/40 rounded-2xl p-3 shadow-2xl shadow-cyan-950/60 flex flex-col gap-2.5 transition-all">
        {/* Top Bar with Status and Expand */}
        <div className="flex items-center justify-between text-xs text-slate-400 px-1">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-nova-cyan animate-pulse shadow-[0_0_8px_#06b6d4]" />
            <span className="font-bold text-white tracking-wide text-xs">NOVA 2.0</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-nova-cyan border border-cyan-800/50">
              {geminiModel ?? 'Gemini 3.8 Flash'}
            </span>
            <span className="text-[10px] text-slate-400 hidden sm:inline">
              Summon: <kbd className="bg-slate-800 px-1.5 py-0.5 rounded text-[9px] border border-slate-700 text-slate-300">Ctrl+Shift+Space</kbd>
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={onExpandDashboard}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition flex items-center gap-1 border border-slate-700"
              title="Expand to Full Dashboard"
            >
              <Layers className="w-3 h-3 text-nova-cyan" />
              <span className="text-[11px]">Dashboard</span>
            </button>
            <button
              onClick={onMinimize}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Hide / Minimize to Tray"
            >
              <Minimize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Search / Command Input with Mic */}
        <div className="flex items-center gap-2 bg-slate-950/90 border border-slate-700/80 rounded-xl px-3 py-2 focus-within:border-nova-cyan transition shadow-inner">
          <Sparkles className="w-4 h-4 text-nova-cyan shrink-0 animate-pulse" />
          <input
            ref={inputRef}
            type="text"
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onExecute();
            }}
            placeholder="Type or speak: 'chrome kholo', 'isko band karo', 'calculate 20% of 1500'..."
            className="flex-1 bg-transparent text-sm text-white focus:outline-none placeholder-slate-500 font-sans"
            autoFocus
          />
          <button
            onClick={onToggleListen}
            className={`p-1.5 rounded-lg transition ${
              isListening
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
            }`}
            title={isListening ? 'Stop Listening' : 'Voice Input'}
          >
            {isListening ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4 text-slate-400" />}
          </button>
          <button
            onClick={onExecute}
            disabled={isClassifying || !commandInput.trim()}
            className="p-1.5 rounded-lg bg-nova-cyan hover:bg-cyan-400 text-slate-950 font-semibold transition disabled:opacity-40"
            title="Execute Command"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        {/* Quick Result / Transcript feedback */}
        {(commandResult || voiceResult) && (
          <div className="text-xs bg-slate-950/80 rounded-lg p-2 border border-slate-800/80 flex items-center justify-between text-slate-300">
            <div className="flex items-center gap-2 truncate">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="truncate text-[11px]">
                {commandResult?.live_response || voiceResult?.transcript || 'Command executed.'}
              </span>
            </div>
            {commandResult?.intent && (
              <span className="text-[9px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-nova-cyan shrink-0 border border-cyan-900/60">
                {commandResult.intent}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
