# E_listening 英语精听训练工具

上传音频后自动识别分割成句子，支持逐句播放、按需显示原文和翻译，适合英语听力精听训练。

## 功能

- 上传音频文件，自动语音识别并分割成句子
- 逐句播放：点击播放按钮只播放该句的音频区间
- 原文隐藏：默认不显示英文原文，点击按钮才显示
- 翻译隐藏：默认不显示中文翻译，点击按钮才显示
- 多设备访问：同一局域网下手机/平板可通过浏览器访问
- VAD 过滤静音段，自动跳过纯音乐和无声片段

## 技术栈

| 组件 | 说明 |
|------|------|
| FastAPI | 后端框架，处理上传和 API |
| faster-whisper | 语音识别，基于 CTranslate2 加速 |
| DeepSeek API | 批量翻译 |
| 原生 HTML/JS | 前端页面，无框架依赖 |

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置翻译 API Key

在项目根目录创建 `.env` 文件：

```
DEEPSEEK_API_KEY=你的key
```

不配置也能用，只是翻译功能不可用。

### 3. 启动

```bash
python app.py
```

浏览器打开 `http://localhost:8000`。

### 4. 多设备访问

同一 WiFi 下的设备访问 `http://你电脑的局域网IP:8000`。

Windows 需要放行 8000 端口（管理员 PowerShell）：

```powershell
New-NetFirewallRule -DisplayName "ListeningApp 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

## 使用流程

1. 上传一段英语音频（mp3/wav/m4a）
2. 等待自动识别和翻译完成
3. 点击句子旁的播放按钮听该句
4. 点击"显示原文"查看英文
5. 点击"显示翻译"查看中文
6. 可删除不需要的音频

## 项目结构

```
├── app.py              # 后端主程序
├── requirements.txt    # 依赖
├── .env                # API Key 配置（不入库）
├── .gitignore
├── uploads/            # 上传的音频文件（不入库）
├── data/               # 解析结果 JSON（不入库）
└── static/             # 前端
    ├── index.html
    ├── style.css
    └── app.js
```
