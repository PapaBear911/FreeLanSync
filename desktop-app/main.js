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

function findPythonCommand() {
  if (process.env.PYTHON && fs.existsSync(process.env.PYTHON)) {
    return process.env.PYTHON;
  }
  const candidates = [
    'python',
    'python3',
    'py',
    'C:\\Python314\\python.exe',
    'C:\\Python313\\python.exe',
    'C:\\Python312\\python.exe',
    'C:\\Python311\\python.exe',
    'C:\\Python310\\python.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python314', 'python.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python313', 'python.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe')
  ];
  for (const cmd of candidates) {
    if (cmd.includes('\\') && fs.existsSync(cmd)) {
      return cmd;
    }
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function startPythonServer() {
  const rootDir = getServerRoot();
  const pythonCmd = findPythonCommand();
  const userDataDir = app.getPath('userData');
  const dataDir = path.join(userDataDir, 'data');
  const logFile = path.join(userDataDir, 'server.log');

  try {
    fs.mkdirSync(dataDir, { recursive: true });
  } catch (e) {}

  const logStream = fs.createWriteStream(logFile, { flags: 'a' });
  const startMsg = `\n[${new Date().toISOString()}] Launching FreeLanSync Server...\nRoot: ${rootDir}\nPython: ${pythonCmd}\nData: ${dataDir}\n`;
  console.log(startMsg);
  logStream.write(startMsg);

  const env = {
    ...process.env,
    FREELANSYNC_DATA_DIR: dataDir,
    PYTHONUNBUFFERED: '1',
    PYTHONIOENCODING: 'utf-8'
  };

  // TD-021: bind address comes from the same env the server defines
  // (server/config.py SERVER_HOST). Default 0.0.0.0 preserves the product
  // feature — phones on the LAN must reach the server; README documents the
  // threat model and how to restrict to 127.0.0.1.
  const serverHost = process.env.FREELANSYNC_HOST || process.env.PHOTOSYNC_HOST || '0.0.0.0';

  try {
    pyProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'server.main:app', '--host', serverHost, '--port', `${SERVER_PORT}`], {
      cwd: rootDir,
      windowsHide: true,
      env: env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    pyProcess.stdout.on('data', (data) => {
      const msg = `[Python stdout]: ${data}`;
      console.log(msg);
      logStream.write(msg);
    });

    pyProcess.stderr.on('data', (data) => {
      const msg = `[Python stderr]: ${data}`;
      console.error(msg);
      logStream.write(msg);
    });

    pyProcess.on('close', (code) => {
      const msg = `Python process exited with code ${code}\n`;
      console.log(msg);
      logStream.write(msg);
      pyProcess = null;
    });

    pyProcess.on('error', (err) => {
      const msg = `Failed to start Python process: ${err.message}\n`;
      console.error(msg);
      logStream.write(msg);
    });
  } catch (err) {
    console.error('Spawn exception:', err);
    logStream.write(`Spawn exception: ${err.message}\n`);
  }
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

function waitForServer(callback, attempts = 40) {
  if (attempts <= 0) {
    console.warn('Server start timeout, opening window...');
    callback(false);
    return;
  }

  http.get(`${SERVER_URL}/api/v1/ping`, (res) => {
    if (res.statusCode === 200) {
      callback(true);
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

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.warn(`Dashboard load pending: ${errorDescription} (${errorCode})`);
    const errorHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>FreeLanSync Connecting...</title>
  <style>
    body {
      background-color: #020617;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      text-align: center;
    }
    .box {
      background: #0f172a;
      border: 1px solid #1e293b;
      padding: 32px 40px;
      border-radius: 16px;
      max-width: 480px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }
    h2 { margin: 0 0 12px; font-size: 20px; color: #38bdf8; }
    p { color: #94a3b8; font-size: 14px; margin: 0 0 20px; line-height: 1.5; }
    button {
      background: #4f46e5;
      color: white;
      border: none;
      padding: 10px 24px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover { background: #4338ca; }
    .status { font-family: monospace; font-size: 11px; color: #64748b; margin-top: 16px; }
  </style>
</head>
<body>
  <div class="box">
    <h2>Starting FreeLanSync Engine</h2>
    <p>Connecting to background transfer engine on port ${SERVER_PORT}... If launching for the first time, this may take a few seconds.</p>
    <button onclick="location.href='${SERVER_URL}'">Retry Connection</button>
    <div class="status">${errorDescription}</div>
  </div>
  <script>
    setTimeout(() => { location.href = '${SERVER_URL}'; }, 2000);
  </script>
</body>
</html>`;
    mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(errorHtml));
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
      mainWindow.loadURL(SERVER_URL);
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
