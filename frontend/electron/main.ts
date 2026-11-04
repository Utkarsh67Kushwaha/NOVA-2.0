import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } from 'electron';
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
    width: 1080,
    height: 740,
    minWidth: 840,
    minHeight: 560,
    backgroundColor: '#080c14',
    title: 'NOVA Desktop Assistant',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Minimize to tray on close unless quitting
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  const isDev = process.env.NODE_ENV !== 'production' && !app.isPackaged;

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // Open DevTools in dev mode
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
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

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      } else if (mainWindow) {
        mainWindow.show();
      }
    });
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
