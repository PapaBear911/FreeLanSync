const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let tray = null;
let pyProcess = null;
let isQuitting = false;

const SERVER_PORT = 8080;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;

function createTrayIcon() {
  // 16x16 fallback bitmap (camera-like pixel pattern)
  const size = 16;
  const buffer = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      if (y >= 4 && y <= 13 && x >= 2 && x <= 13) {
        // Body (indigo / blue)
        buffer[idx] = 99;     // R
        buffer[idx + 1] = 102; // G
        buffer[idx + 2] = 241; // B
        buffer[idx + 3] = 255; // Alpha
      } else if (y >= 2 && y <= 3 && x >= 5 && x <= 10) {
        // Flash top
        buffer[idx] = 129;
        buffer[idx + 1] = 140;
        buffer[idx + 2] = 248;
        buffer[idx + 3] = 255;
      } else {
        buffer[idx + 3] = 0; // Transparent
      }
    }
  }
  return nativeImage.createFromBuffer(buffer, { width: size, height: size });
}

function startPythonServer() {
  const rootDir = path.resolve(__dirname, '..');
  console.log(`Starting Python Server in ${rootDir}...`);

  pyProcess = spawn('python', ['-m', 'uvicorn', 'server.main:app', '--host', '0.0.0.0', '--port', `${SERVER_PORT}`], {
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
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 820,
    minWidth: 800,
    minHeight: 600,
    title: 'FreeLanSync Continuity & Gigabit Hub',
    backgroundColor: '#020617',
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
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
