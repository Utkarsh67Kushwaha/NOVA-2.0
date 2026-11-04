import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, globalShortcut } from 'electron';
import * as path from 'path';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

// 16x16 base64 PNG icon (Cyan glowing dot/ring)
const DEFAULT_ICON_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAP0lEQVR42mNk+M9QzwABjFAaG6CSYVQDGBgY/jMwMAyicvA/McbAQD0DaIThmF4GMDAwMDDUjZpBtINoahgA2iUL2eO5kHAAAAAASUVORK5CYII=';

function createTrayIcon(): Electron.NativeImage {
  try {
    const img = nativeImage.createFromDataURL(DEFAULT_ICON_DATA_URL);
    return img;
  } catch {
    return nativeImage.createEmpty();
  }
}

function updateTrayMenu() {
  if (!tray) return;

  const loginSettings = app.getLoginItemSettings();
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open NOVA Dashboard',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: 'Start with Windows (Auto-launch)',
      type: 'checkbox',
      checked: loginSettings.openAtLogin,
      click: (item) => {
        app.setLoginItemSettings({
          openAtLogin: item.checked,
          path: process.execPath,
        });
      },
    },
    { type: 'separator' },
    {
      label: 'Quit NOVA',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
}

function setupTray() {
  const icon = createTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip('NOVA Desktop Assistant');

  updateTrayMenu();

  tray.on('double-click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus();
      } else {
        mainWindow.show();
      }
    }
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 840,
    minHeight: 560,
    backgroundColor: '#080c14',
    title: 'NOVA Desktop Assistant',
    show: false, // Show gracefully when ready
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });

  // Minimize to tray on close unless explicitly quitting
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  const distHtmlPath = path.join(__dirname, '../dist/index.html');

  if (devServerUrl) {
    mainWindow.loadURL(devServerUrl).catch(() => {
      mainWindow?.loadFile(distHtmlPath);
    });
  } else {
    mainWindow.loadFile(distHtmlPath);
  }

  // Open DevTools only if explicitly requested
  if (process.env.OPEN_DEVTOOLS === 'true') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
}

// IPC Handlers
ipcMain.handle('nova:ping', async () => {
  return 'pong';
});

ipcMain.handle('nova:get-login-startup', async () => {
  return app.getLoginItemSettings().openAtLogin;
});

ipcMain.handle('nova:set-login-startup', async (_event, enabled: boolean) => {
  app.setLoginItemSettings({
    openAtLogin: Boolean(enabled),
    path: process.execPath,
  });
  updateTrayMenu();
  return app.getLoginItemSettings().openAtLogin;
});

ipcMain.on('nova:minimize-to-tray', () => {
  mainWindow?.hide();
});

ipcMain.on('nova:quit-app', () => {
  isQuitting = true;
  app.quit();
});

// App Lifecycle
const gotSingleInstanceLock = app.requestSingleInstanceLock();

if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    createWindow();
    setupTray();

    // Toggle DevTools with F12
    globalShortcut.register('F12', () => {
      if (mainWindow) {
        mainWindow.webContents.toggleDevTools();
      }
    });

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      } else if (mainWindow) {
        mainWindow.show();
      }
    });
  });

  app.on('will-quit', () => {
    globalShortcut.unregisterAll();
  });

  app.on('before-quit', () => {
    isQuitting = true;
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      // Keep running in tray
    }
  });
}
