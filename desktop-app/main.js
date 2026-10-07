const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let tray = null;
let pyProcess = null;
let isQuitting = false;

const SERVER_PORT = 8080;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;

function getServerRoot() {
  if (process.resourcesPath) {
    const packagedServer = path.join(process.resourcesPath, 'server');
    if (fs.existsSync(packagedServer)) {
      return process.resourcesPath;
    }
  }
  const parentDir = path.resolve(__dirname, '..');
  if (fs.existsSync(path.join(parentDir, 'server'))) {
    return parentDir;
  }
  return process.cwd();
}

function createTrayIcon() {
  // 16x16 bitmap representing radiant AI Agent diamond core
  const size = 16;
  const buffer = Buffer.alloc(size * size * 4);
  const cx = 7.5, cy = 7.5;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      // Manhattan distance for diamond shape
      const dist = Math.abs(x - cx) + Math.abs(y - cy);
      if (dist <= 6) {
        if (dist <= 2) {
          // Brilliant white-cyan center glint
          buffer[idx] = 255;
          buffer[idx + 1] = 255;
          buffer[idx + 2] = 255;
          buffer[idx + 3] = 255;
        } else if (dist <= 4) {
          // Electric cyan-indigo gradient core
          buffer[idx] = 56;
          buffer[idx + 1] = 189;
          buffer[idx + 2] = 248;
          buffer[idx + 3] = 240;
        } else {
          // Deep violet-indigo rim
          buffer[idx] = 129;
          buffer[idx + 1] = 140;
          buffer[idx + 2] = 248;
          buffer[idx + 3] = 200;
        }
      } else {
        buffer[idx + 3] = 0; // Transparent
      }
    }
  }
  return nativeImage.createFromBuffer(buffer, { width: size, height: size });
}

function startPythonServer() {
  const rootDir = getServerRoot();
  console.log(`Starting Python Server in ${rootDir}...`);
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

  pyProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'server.main:app', '--host', '0.0.0.0', '--port', `${SERVER_PORT}`], {
    cwd: rootDir,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  pyProcess.stdout.on('data', (data) => {
    console.log(`[Python stdout]: ${data}`);
  });

  pyProcess.stderr.on('data', (data) => {
    console.log(`[Python stderr]: ${data}`);
  });

  pyProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

function stopPythonServer() {
  if (pyProcess) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', pyProcess.pid, '/f', '/t']);
      } else {
        pyProcess.kill();
      }
    } catch (e) {
      console.error('Error stopping server process:', e);
    }
    pyProcess = null;
  }
}

function waitForServer(callback, attempts = 30) {
  if (attempts <= 0) {
    console.warn('Server start timeout, attempting to open window anyway...');
    callback();
    return;
  }

  http.get(`${SERVER_URL}/api/v1/ping`, (res) => {
    if (res.statusCode === 200) {
      callback();
    } else {
      setTimeout(() => waitForServer(callback, attempts - 1), 500);
    }
  }).on('error', () => {
    setTimeout(() => waitForServer(callback, attempts - 1), 500);
  });
}

function createWindow() {
  const iconPath = path.join(__dirname, 'build', 'icon.png');
  mainWindow = new BrowserWindow({
    width: 1240,
    height: 840,
    minWidth: 840,
    minHeight: 620,
    title: 'FreeLanSync Continuity & Gigabit Hub',
    backgroundColor: '#020617',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadURL(SERVER_URL);

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      if (tray) {
        tray.displayBalloon({
          title: 'FreeLanSync is running',
          content: 'Running in your system tray with active gigabit transfer and continuity mirroring.'
        });
      }
    }
  });
}

function setupTray() {
  const icon = createTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip('FreeLanSync Continuity & Gigabit Hub (Active)');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open Dashboard',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: 'Open Web Browser',
      click: () => {
        shell.openExternal(SERVER_URL);
      }
    },
    { type: 'separator' },
    {
      label: 'Quit FreeLanSync Server',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);

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

function setupIpcHandlers() {
  ipcMain.handle('select-storage-folder', async (event, currentPath) => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        title: 'Select FreeLanSync Storage Folder',
        defaultPath: currentPath || undefined,
        properties: ['openDirectory', 'createDirectory', 'promptToCreate']
      });
      return result;
    } catch (err) {
      console.error('Error in select-storage-folder dialog:', err);
      return { canceled: true, filePaths: [] };
    }
  });

  ipcMain.handle('open-storage-folder', async (event, folderPath) => {
    try {
      if (folderPath) {
        return await shell.openPath(folderPath);
      }
    } catch (err) {
      console.error('Error in open-storage-folder:', err);
    }
    return '';
  });

  ipcMain.handle('get-app-version', () => app.getVersion());
}

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
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
    setupIpcHandlers();
    startPythonServer();
    setupTray();

    waitForServer(() => {
      createWindow();
    });
  });

  app.on('before-quit', () => {
    isQuitting = true;
    stopPythonServer();
  });

  app.on('window-all-closed', () => {
    // Keep app running in tray even when windows close
  });
}
