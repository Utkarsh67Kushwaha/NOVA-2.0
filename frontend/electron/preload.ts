import { contextBridge, ipcRenderer } from 'electron';

// Expose safe, typed APIs to renderer process
contextBridge.exposeInMainWorld('novaAPI', {
  ping: () => ipcRenderer.invoke('nova:ping'),
  getLoginItemSettings: () => ipcRenderer.invoke('nova:get-login-startup'),
  setLoginItemSettings: (enabled: boolean) => ipcRenderer.invoke('nova:set-login-startup', enabled),
  minimizeToTray: () => ipcRenderer.send('nova:minimize-to-tray'),
  quitApp: () => ipcRenderer.send('nova:quit-app'),
  platform: process.platform,
});
