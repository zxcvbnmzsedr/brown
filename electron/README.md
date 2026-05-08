# Electron

MVP 暂不实现 Electron 打包。当前目录用于保留后续桌面壳接入位置。

后续接入时需要补齐：

- 主进程启动 FastAPI 子进程
- renderer 窗口加载 Vite 构建产物
- 后端端口探活和异常退出处理
- 应用退出时清理 Python 子进程
- 打包后的 Python 运行环境和数据库路径
