import { app, BrowserWindow, Notification, ipcMain } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

const isDev = !app.isPackaged;
const rendererDevUrl = process.env.BROWN_RENDERER_URL || 'http://127.0.0.1:5174';

function getPythonPath(): string {
  if (isDev) {
    return path.join(__dirname, '..', '.venv', 'bin', 'uvicorn');
  }
  // 打包后使用系统 Python 或嵌入式 Python
  // 用户需要确保系统中安装了 Python 和 uvicorn
  return 'uvicorn';
}

function startPythonBackend(): void {
  const pythonPath = getPythonPath();
  const args = ['backend.app:app', '--host', '127.0.0.1', '--port', '8765'];

  if (isDev) {
    pythonProcess = spawn(pythonPath, args, {
      cwd: path.join(__dirname, '..'),
      stdio: 'pipe',
    });
  } else {
    // 打包后的路径处理
    const appPath = app.getAppPath();
    pythonProcess = spawn(pythonPath, args, {
      cwd: appPath,
      stdio: 'pipe',
    });
  }

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`Python stdout: ${data.toString()}`);
  });

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`Python stderr: ${data.toString()}`);
  });

  pythonProcess.on('close', (code: number | null) => {
    console.log(`Python process exited with code ${code}`);
    pythonProcess = null;
  });

  pythonProcess.on('error', (err: Error) => {
    console.error('Failed to start Python process:', err);
  });
}

function stopPythonBackend(): void {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: 'Brown - 永久组合',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL(rendererDevUrl);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function registerIpcHandlers(): void {
  ipcMain.handle('get-app-version', () => app.getVersion());

  ipcMain.on('minimize-window', () => {
    mainWindow?.minimize();
  });

  ipcMain.on('maximize-window', () => {
    if (!mainWindow) return;
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  });

  ipcMain.on('close-window', () => {
    mainWindow?.close();
  });

  ipcMain.handle('notify-rebalance', (_event, payload: { title?: string; body?: string }) => {
    if (!Notification.isSupported()) {
      return false;
    }

    const notification = new Notification({
      title: payload.title || 'Brown 再平衡提醒',
      body: payload.body || '永久组合触发再平衡条件。',
    });
    notification.show();
    return true;
  });
}

app.whenReady().then(() => {
  registerIpcHandlers();
  startPythonBackend();

  // 等待 Python 后端启动
  setTimeout(() => {
    createWindow();
  }, 2000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopPythonBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonBackend();
});
