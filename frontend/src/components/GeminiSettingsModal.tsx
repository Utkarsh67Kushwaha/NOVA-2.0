import React from 'react';
import { Brain, Key, Sparkles } from 'lucide-react';

export interface GeminiSettingsProps {
  geminiStatus: { is_configured: boolean; model: string; has_key: boolean } | null;
  apiKeyInput: string;
  setApiKeyInput: (val: string) => void;
  isSavingKey: boolean;
  onSaveApiKey: () => void;
  onSelectPrompt: (prompt: string) => void;
}

const SAMPLE_AI_PROMPTS = [
  'tum kaun ho',
  'kaise ho bhai',
  'kya kar sakte ho',
  'ek mast chutkula sunao',
  'aaj kya date hai',
  'bhai zara screen ka photo le le',
  'bhai thoda volume badha de yaar',
  'bhai gaana band kar do bohot shor hai',
  'screen capture karo',
];

export const GeminiSettingsModal: React.FC<GeminiSettingsProps> = ({
  geminiStatus,
  apiKeyInput,
  setApiKeyInput,
  isSavingKey,
  onSaveApiKey,
  onSelectPrompt,
}) => {
  return (
    <div className="p-5 rounded-xl bg-nova-panel border border-nova-border shadow-md space-y-4">
      <div className="flex items-center justify-between border-b border-nova-border pb-3">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-purple-400" />
          <h2 className="font-semibold text-sm tracking-wide text-white">
            Conversational AI Brain &amp; Gemini Intelligence
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[11px] px-2.5 py-0.5 rounded-full border flex items-center gap-1.5 ${
              geminiStatus?.is_configured
                ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                geminiStatus?.is_configured ? 'bg-purple-400' : 'bg-emerald-400'
              }`}
            />
            {geminiStatus?.is_configured
              ? `${geminiStatus?.model ?? 'Gemini 3.8 Flash'} Online`
              : 'Smart Offline Brain Active'}
          </span>
        </div>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed">
        NOVA is equipped with universal voice &amp; conversational intelligence. It effortlessly handles broken Hindi, pure English, casual Hinglish with slang words (&quot;bhai&quot;, &quot;yaar&quot;, &quot;zara&quot;), system controls, and open-domain chat without ever throwing confusion errors.
      </p>

      {/* Gemini API Key Configuration Row */}
      <div className="p-3.5 rounded-lg bg-nova-dark/70 border border-nova-border flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-300 shrink-0">
          <Key className="w-4 h-4 text-purple-400" />
          <span>Google Gemini API Key:</span>
        </div>
        <input
          type="password"
          value={apiKeyInput}
          onChange={(e) => setApiKeyInput(e.target.value)}
          placeholder={
            geminiStatus?.has_key
              ? '•••••••••••••••••••••••••••••••• (Configured)'
              : 'Enter your free Google Gemini API key...'
          }
          className="flex-1 px-3 py-1.5 rounded-md bg-nova-card border border-nova-border focus:border-purple-400 focus:outline-none text-xs text-white placeholder-slate-500 font-mono"
        />
        <button
          onClick={onSaveApiKey}
          disabled={isSavingKey || !apiKeyInput.trim()}
          className="px-4 py-1.5 rounded-md bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold text-xs transition shrink-0"
        >
          {isSavingKey ? 'Saving...' : 'Save API Key'}
        </button>
      </div>

      {/* Conversational & Casual Voice Quick Testers */}
      <div className="space-y-1.5">
        <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
          Casual Voice &amp; Conversational AI Prompts:
        </span>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_AI_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => onSelectPrompt(prompt)}
              className="text-[11px] px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 border border-slate-700/80 text-slate-300 hover:text-white transition"
            >
              &quot;{prompt}&quot;
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
