# 文档智能治理中台 - 前端实现

基于AG-UI协议规范的智能文档处理系统前端实现。

## 项目结构

```
document intelligent process agent for OpenClaw/
├── index.html          # 主页面
├── styles.css          # 自定义样式
├── agui-handler.js     # AG-UI协议处理器
├── tailwind.config.js  # Tailwind CSS配置
├── postcss.config.js   # PostCSS配置
├── package.json       # 项目依赖
└── README.md          # 项目说明
```

## 功能特性

### 📄 文档上传
- 支持拖拽上传和点击上传
- 实时进度显示
- 文件类型验证
- 多文件上传支持

### 🔄 实时处理反馈
- 基于AG-UI协议的事件驱动架构
- SSE（Server-Sent Events）连接
- WebSocket双向通信
- 流式文本输出支持

### 📊 智能处理结果展示
- 字段提取结果展示
- 合规检查结果
- 置信度显示
- 错误处理和恢复

### 🎨 用户界面
- 响应式设计
- 现代化UI组件
- 加载状态指示器
- Toast通知系统

## 技术栈

### 前端技术
- HTML5/CSS3/JavaScript (ES6+)
- Tailwind CSS - 快速样式开发
- EventSource API - SSE连接
- WebSocket API - 双向通信

### AG-UI协议支持
- 16种标准事件类型
- 生命周期事件管理
- 状态快照和增量更新
- 文本流式传输

## 安装和运行

### 1. 安装依赖
```bash
npm install
```

### 2. 启动开发服务器
```bash
npx live-server
```

### 3. 构建生产版本
```bash
# 需要配置构建脚本
npm run build
```

## AG-UI协议集成

### 事件处理流程
1. **连接建立**: 通过SSE连接到智能体
2. **文件上传**: 发送`user.uploadFile`事件
3. **进度跟踪**: 监听`agent.processProgress`事件
4. **结果展示**: 处理`agent.fieldExtracted`和`agent.complianceChecked`事件
5. **完成通知**: 接收`agent.processCompleted`事件

### 核心事件类型
- `agent.ready`: 智能体就绪
- `user.uploadFile`: 用户上传文件
- `agent.uploadConfirm`: 文件接收确认
- `agent.processProgress`: 处理进度
- `agent.fieldExtracted`: 字段提取结果
- `agent.complianceChecked`: 合规检查结果
- `agent.processCompleted`: 处理完成
- `agent.error`: 错误处理

## 开发指南

### 添加新功能
1. 在`agui-handler.js`中添加相应的事件处理函数
2. 更新UI组件以显示新功能
3. 确保符合AG-UI协议规范
4. 添加必要的样式

### 调试
- 使用浏览器开发者工具查看控制台日志
- 检查SSE和WebSocket连接状态
- 监控事件流和数据处理

## 注意事项

- 确保后端API支持AG-UI协议事件
- 处理网络连接问题（自动重连）
- 优化性能（减少不必要的状态更新）
- 确保响应式设计兼容各种设备

## 贡献

请遵循AG-UI协议规范进行开发，确保：
- 事件类型正确
- 数据格式符合规范
- 错误处理完善
- 用户体验流畅

## 许可证

本项目遵循AG-UI协议规范开发。