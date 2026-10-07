const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isDesktop: true,
  selectStorageFolder: (currentPath) => ipcRenderer.invoke('select-storage-folder', currentPath),
  openStorageFolder: (folderPath) => ipcRenderer.invoke('open-storage-folder', folderPath),
  getAppVersion: () => ipcRenderer.invoke('get-app-version')
});
