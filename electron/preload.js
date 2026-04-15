const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopAPI", {
  getApiBaseUrl: () => ipcRenderer.invoke("backend:base-url"),
  isBackendReady: () => ipcRenderer.invoke("backend:is-ready"),
  pickImagePaths: () => ipcRenderer.invoke("dialog:pick-images"),
  pickModelFile: () => ipcRenderer.invoke("dialog:pick-model"),
  openExternalUrl: (url) => ipcRenderer.invoke("shell:open-external", { url }),
  downloadBackendFile: (apiPath, defaultFileName) =>
    ipcRenderer.invoke("backend:download-file", { apiPath, defaultFileName }),
  apiGet: (apiPath) => ipcRenderer.invoke("backend:request", { method: "GET", apiPath }),
  apiPost: (apiPath, body) =>
    ipcRenderer.invoke("backend:request", { method: "POST", apiPath, body }),
  apiPatch: (apiPath, body) =>
    ipcRenderer.invoke("backend:request", { method: "PATCH", apiPath, body }),
  apiDelete: (apiPath) =>
    ipcRenderer.invoke("backend:request", { method: "DELETE", apiPath }),
});
