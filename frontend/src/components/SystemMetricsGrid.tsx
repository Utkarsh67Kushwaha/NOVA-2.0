import React from 'react';
import { Cpu, Activity, HardDrive, Settings, CheckCircle2 } from 'lucide-react';
import { SystemStatusData } from '../types';

export interface SystemMetricsGridProps {
  systemStatus: SystemStatusData | null;
  autoStartup: boolean;
  onToggleAutoStartup: () => void;
}

export const SystemMetricsGrid: React.FC<SystemMetricsGridProps> = ({
  systemStatus,
  autoStartup,
  onToggleAutoStartup,
}) => {
  return (
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
            onClick={onToggleAutoStartup}
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
  );
};
