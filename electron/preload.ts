import { contextBridge, ipcRenderer } from 'electron';

// 暴露安全的 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取应用版本
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),

  // 获取平台信息
  getPlatform: () => process.platform,

  // 最小化窗口
  minimizeWindow: () => ipcRenderer.send('minimize-window'),

  // 最大化窗口
  maximizeWindow: () => ipcRenderer.send('maximize-window'),

  // 关闭窗口
  closeWindow: () => ipcRenderer.send('close-window'),

  // 发送再平衡系统通知
  notifyRebalance: (title: string, body: string) =>
    ipcRenderer.invoke('notify-rebalance', { title, body }),

  // 检查是否为 Electron 环境
  isElectron: true,
});
