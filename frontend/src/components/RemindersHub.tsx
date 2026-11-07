import React from 'react';
import { Bell, RotateCcw, Clock, Trash2 } from 'lucide-react';
import { ReminderItem } from '../types';

export interface RemindersHubProps {
  reminders: ReminderItem[];
  customReminderTitle: string;
  setCustomReminderTitle: (val: string) => void;
  customReminderSecs: number;
  setCustomReminderSecs: (val: number) => void;
  isCreatingReminder: boolean;
  onRefresh: () => void;
  onCreateReminder: (title: string, secs: number) => void;
  onDeleteReminder: (id: string) => void;
}

export const RemindersHub: React.FC<RemindersHubProps> = ({
  reminders,
  customReminderTitle,
  setCustomReminderTitle,
  customReminderSecs,
  setCustomReminderSecs,
  isCreatingReminder,
  onRefresh,
  onCreateReminder,
  onDeleteReminder,
}) => {
  return (
    <div className="p-5 rounded-xl bg-nova-panel border border-nova-border shadow-md space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30">
            <Bell className="w-5 h-5 text-amber-400 animate-bounce" />
          </div>
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
              Windows Toast Reminders &amp; Alarms Hub
            </h2>
            <p className="text-[11px] text-slate-400">
              Background Scheduler • Native WinRT Toast Popups • Audio Chime • Spoken Voice Alerts
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] px-2.5 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono">
            {reminders.filter((r) => r.status === 'PENDING').length} Active Scheduled
          </span>
          <button
            onClick={onRefresh}
            className="px-2.5 py-1 rounded bg-nova-card hover:bg-slate-700 text-slate-300 border border-nova-border text-xs flex items-center gap-1.5 transition"
          >
            <RotateCcw className="w-3 h-3 text-amber-400" />
            Refresh
          </button>
        </div>
      </div>

      {/* Quick One-Click Reminder Presets */}
      <div className="space-y-2">
        <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-amber-400" />
          One-Click Presets:
        </span>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onCreateReminder('💧 Drink Water & Stay Hydrated', 900)}
            disabled={isCreatingReminder}
            className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
          >
            💧 Drink Water (15m)
          </button>
          <button
            onClick={() => onCreateReminder('🧘 Stand Up & Stretch', 1800)}
            disabled={isCreatingReminder}
            className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
          >
            🧘 Posture &amp; Stretch (30m)
          </button>
          <button
            onClick={() => onCreateReminder('☕ Coffee/Tea Break', 2700)}
            disabled={isCreatingReminder}
            className="px-3 py-1.5 rounded-lg bg-nova-card hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-nova-border flex items-center gap-1.5 transition"
          >
            ☕ Tea Break (45m)
          </button>
          <button
            onClick={() => onCreateReminder('⚡ 10 Second Test Alert', 10)}
            disabled={isCreatingReminder}
            className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-xs font-bold text-amber-300 border border-amber-500/40 flex items-center gap-1.5 transition"
          >
            ⚡ Test 10s Toast Alert
          </button>
        </div>
      </div>

      {/* Custom Reminder Schedule Bar */}
      <div className="flex flex-col sm:flex-row gap-2 pt-1">
        <input
          type="text"
          value={customReminderTitle}
          onChange={(e) => setCustomReminderTitle(e.target.value)}
          placeholder="Custom reminder (e.g., 'Submit project report', 'Call doctor')..."
          className="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-nova-border text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-400"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onCreateReminder(customReminderTitle, customReminderSecs);
            }
          }}
        />
        <select
          value={customReminderSecs}
          onChange={(e) => setCustomReminderSecs(Number(e.target.value))}
          className="px-3 py-2 rounded-lg bg-slate-900 border border-nova-border text-xs text-slate-200 focus:outline-none focus:border-amber-400"
        >
          <option value={10}>in 10 seconds</option>
          <option value={60}>in 1 minute</option>
          <option value={300}>in 5 minutes</option>
          <option value={600}>in 10 minutes</option>
          <option value={900}>in 15 minutes</option>
          <option value={1800}>in 30 minutes</option>
          <option value={3600}>in 1 hour</option>
        </select>
        <button
          onClick={() => onCreateReminder(customReminderTitle, customReminderSecs)}
          disabled={isCreatingReminder || !customReminderTitle.trim()}
          className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center justify-center gap-1.5 transition"
        >
          <Bell className="w-3.5 h-3.5" />
          Schedule Reminder
        </button>
      </div>

      {/* Active Reminders List */}
      <div className="space-y-2 pt-2 border-t border-nova-border/60">
        <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
          Upcoming &amp; Recent Reminders:
        </span>
        {reminders.length === 0 ? (
          <p className="text-xs text-slate-500 italic py-2">
            No active reminders. Schedule one above or say &quot;Hey NOVA, remind me to drink water in 10 minutes&quot;.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {reminders.slice(0, 6).map((rem) => {
              const now = Date.now() / 1000;
              const diff = Math.round(rem.due_timestamp - now);
              const isPending = rem.status === 'PENDING';
              const isDue = isPending && diff <= 0;

              return (
                <div
                  key={rem.id}
                  className={`p-3 rounded-lg border flex items-center justify-between text-xs transition ${
                    isDue
                      ? 'bg-amber-950/40 border-amber-500/60 animate-pulse'
                      : isPending
                      ? 'bg-slate-900/80 border-slate-700'
                      : 'bg-slate-950/40 border-slate-800 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Clock
                      className={`w-4 h-4 shrink-0 ${
                        isPending ? 'text-amber-400' : 'text-slate-500'
                      }`}
                    />
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-200 truncate">{rem.title}</p>
                      <p className="text-[10px] text-slate-400">
                        {new Date(rem.due_timestamp * 1000).toLocaleTimeString()} •{' '}
                        {isPending
                          ? diff > 60
                            ? `in ~${Math.round(diff / 60)} min`
                            : diff > 0
                            ? `in ${diff}s`
                            : 'Triggering now!'
                          : rem.status}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                        rem.status === 'PENDING'
                          ? 'bg-amber-500/20 text-amber-300'
                          : rem.status === 'TRIGGERED'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-slate-700 text-slate-400'
                      }`}
                    >
                      {rem.status}
                    </span>
                    {isPending && (
                      <button
                        onClick={() => onDeleteReminder(rem.id)}
                        className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition"
                        title="Cancel Reminder"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
