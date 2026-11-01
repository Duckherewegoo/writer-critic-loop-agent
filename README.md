# 多角色写作工作流（Multi-Agent Writing Workflow）

> 一个基于 LangGraph 的 **Writer–Critic 反思循环**：研究 → 写作 → 审核 → 修订，
> 审核闸门不通过自动回炉重写，直到通过或达上限。
> 四个角色（研究/写作/审核/总编辑）串行协作，开箱即用的中文写作工具。

> **版本** `0.2.0` ｜ **Python** `3.10+` ｜ **许可证** [GPL-3.0-or-later](LICENSE)
> 四个智能体分工协作：研究 → 写作 → 审核 → 总编辑，审核不通过自动回到写作重写，最多重写次数可配置。

---

## 目录

- [功能特点](#功能特点)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用说明](#使用说明)
- [项目结构](#项目结构)
- [智能体说明](#智能体说明)
- [测试](#测试)
- [开发](#开发)
- [已知限制](#已知限制)
- [故障排查](#故障排查)
- [许可证](#许可证)

---

## 功能特点

| 特性 | 说明 |
| --- | --- |
| 四智能体协作 | 研究专家、写作专家、审核专家、总编辑各司其职 |
| 自动迭代优化 | 审核不通过自动返回修改，可配置最多重写次数（默认 3 次） |
| Web 界面 | 基于 Gradio，操作简单直观 |
| 灵活配置 | 在界面中自定义模型、温度、迭代次数 |
| 完整工作流 | 从资料收集到最终润色，全流程自动化 |
| 结果自动落盘 | 最终文章与研究状态自动保存到 `outputs/`（运行时生成） |

---

## 系统架构

```text
用户输入主题
  ↓
[研究专家] 收集信息、整理研究笔记
  ↓
[写作专家] 根据研究素材撰写文章草稿
  ↓
[审核专家] 多维度审核，输出结构化结论
  ├─ NEEDS_REVISION: YES 且未达上限？ → 返回写作专家（带审核反馈重写）
  └─ 审核通过或已达上限 →
                          ↓
                  [总编辑] 最终润色和优化
                          ↓
                    输出最终文章
```

**迭代语义**：`max_iterations` 表示**最多重写次数**（默认 3）。审核每判定一次"需要修改"并回到写作，计数 +1；达到上限后强制进入总编辑环节，避免死循环。

---

## 快速开始

### 1. 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | `3.10+` |
| LLM | 一个可用的 API Key（支持 OpenAI 兼容协议即可，如 DashScope / OpenAI） |
| 外部服务 | 无需额外部署，单机运行 |

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate   # Linux / macOS
# 或
.\venv\Scripts\activate    # Windows
```

### 3. 安装依赖

```bash
# 运行时依赖
pip install -e .

# 含开发工具（ruff / pytest）
pip install -e ".[dev]"
```

> 依赖统一由 `pyproject.toml` 管理，请勿手动维护 `requirements.txt`。

### 4. 配置环境变量

在项目根目录创建 `.env`（内容参照下方格式）：

```bash
# ── LLM（OpenAI 兼容协议）──
OPENAI_API_KEY=sk-你的密钥
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 模型、温度、迭代次数请在网页「高级设置」中选择，不要写进 .env
```

- 默认使用 DashScope 的 OpenAI 兼容端点（qwen 系列）；也可改为 OpenAI 官方 `https://api.openai.com/v1`。
- 敏感凭证（API Key）**禁止**提交到仓库。`.env`、`.env.*` 已在 `.gitignore` 中排除。

> ⚠️ 本仓库**不包含** `.env.example` 模板文件，请按上方格式自行创建 `.env`。

### 5. 启动

```bash
# 方式 A：直接运行模块
python main.py

# 方式 B：pip install -e . 后使用入口命令
writer-app
```

浏览器打开 <http://localhost:7860>。

> ⚠️ **端口说明**：Gradio 默认端口是 **7860**（不是 8050）。若端口被占用，可在启动参数或 `main.py` 中调整 `server_port`。

---

## 配置说明

| 变量 | 说明 | 默认值 / 备注 |
| --- | --- | --- |
| `OPENAI_API_KEY` | LLM API 密钥 | **必填** |
| `OPENAI_BASE_URL` | API 接入地址（OpenAI 兼容格式） | DashScope 兼容模式 |
| 模型名称 | 具体模型名（如 `qwen-plus`） | 在网页「高级设置」中配置 |
| 温度（`temperature`） | 生成随机性 | 在网页「高级设置」中配置 |
| 最大迭代次数 | 最多重写次数 | 默认 `3`，在网页中配置 |

> **配置优先级**：`.env` 提供密钥与接入地址 → 网页「高级设置」提供模型、温度、迭代次数。运行时参数覆盖静态配置。

---

## 使用说明

1. 在左侧输入写作主题；
2. （可选）展开「高级设置」，调整模型、温度、最大迭代次数，必要时填入 API Key / Base URL；
3. 点击 **🚀 开始写作**，等待任务完成；
4. 完成后右侧会显示最终文章、研究笔记、审核反馈，以及**耗时 / 字数 / 迭代次数**统计；
5. 所有生成内容自动保存到 `outputs/`（运行时生成，已在 `.gitignore` 中排除）：
   - `final_<主题>_<时间戳>.md` —— 最终文章
   - `state_<时间戳>.json` —— 完整运行状态（含研究笔记、审核反馈、元数据）

### 测试 API 连通性

```bash
# 读取 .env 中的 OPENAI_API_KEY / OPENAI_BASE_URL，发送一次最小请求验证网络与鉴权
python test.py
```

> 若 `test.py` 与 `.env` 不在同级目录，需先 `cd` 到项目根目录再运行。

---

## 项目结构

目录树严格对齐仓库实际输出（`tree .`，共 **5 个目录、21 个文件**）：

```text
.
├── agents
│   ├── base_agent.py
│   ├── editor.py
│   ├── __init__.py
│   ├── researcher.py
│   ├── reviewer.py
│   └── writer.py
├── CHANGELOG.md
├── graph
│   ├── config.py
│   ├── helper.py
│   ├── __init__.py
│   ├── nodes.py
│   ├── state.py
│   └── workflow.py
├── LICENSE
├── main.py
├── pyproject.toml
├── README.md
├── tests
│   ├── smoke_test.py
│   └── test_core.py
└── utils
    ├── helpers.py
    └── __init__.py
```

> `outputs/` 是运行时自动生成的目录，**不在源码树内**，请勿手动提交。

### 源码一览

| 层次 | 关键文件 | 职责 |
| --- | --- | --- |
| 入口 | `main.py` | Gradio Web UI 启动入口 |
| 智能体 | `agents/base_agent.py` | 基类：`prompt` 构造 + LLM 调用 |
| 智能体 | `agents/researcher.py` | 研究专家 |
| 智能体 | `agents/writer.py` | 写作专家 |
| 智能体 | `agents/reviewer.py` | 审核专家 |
| 智能体 | `agents/editor.py` | 总编辑 |
| 图编排 | `graph/state.py` | `WorkflowState` 状态定义 |
| 图编排 | `graph/config.py` | `WorkflowConfig` 配置 |
| 图编排 | `graph/nodes.py` | 节点函数 + 条件边 |
| 图编排 | `graph/helper.py` | 状态转换 + `create_initial_state` |
| 图编排 | `graph/workflow.py` | 图装配（`create_workflow`） |
| 工具 | `utils/helpers.py` | 文件保存、字数统计、标题提取 |
| 测试 | `tests/test_core.py` | 单元测试（纯函数，无需联网） |
| 测试 | `tests/smoke_test.py` | 冒烟测试（需真实 LLM，见下） |
| 构建 | `pyproject.toml` | 依赖与打包配置 |
| 变更 | `CHANGELOG.md` | 变更历史 |

---

## 智能体说明

### 研究专家（ResearchAgent）

- 对给定主题收集信息与素材
- 输出结构化的研究笔记（列表项解析）
- 确保信息的全面性与准确性

### 写作专家（WriterAgent）

- 根据研究素材撰写文章草稿
- 保证结构清晰、内容充实
- 若存在审核反馈，会携带反馈进行重写

### 审核专家（ReviewerAgent）

- 从内容、结构、语言、风格、创新性、可读性**多维度**审核
- 输出具体可操作的改进建议
- 以结构化标记（`NEEDS_REVISION: YES / NO`）给出判定，驱动迭代循环

### 总编辑（EditorAgent）

- 对文章进行最终润色与优化
- 优化标题、语言、结构
- 参考审核意见做最终收尾

---

## 测试

```bash
# 运行全部测试（单元测试秒级，冒烟测试需真实 LLM）
pytest -v

# 只跑单元测试（纯函数，不联网，秒级）
pytest tests/test_core.py -v

# 跳过冒烟测试（CI / 无 API Key 时）
WRITER_SKIP_SMOKE=1 pytest
```

| 测试文件 | 类型 | 是否需要联网 |
| --- | --- | --- |
| `tests/test_core.py` | 单元测试（纯函数） | 否，秒级 |
| `tests/smoke_test.py` | 冒烟测试（端到端链路） | 是，需真实 LLM 与 API Key |

---

## 开发

配置来自 `pyproject.toml`：行宽 120 字符，目标版本 `py310`。

```bash
# 代码风格检查
ruff check .

# 自动格式化
ruff format .

# 运行全部测试
pytest
```

### 新增一个智能体

1. 在 `agents/` 下继承 `BaseAgent`，实现 `async def run(self, state: AgentState) -> AgentState`；
2. 在 `graph/config.py` 的 `WorkflowConfig` 中按需加配置字段（可选）；
3. 在 `graph/workflow.py` 的 `create_workflow` 里实例化并 `add_node` / `add_edge`；
4. 为条件分支补 `tests/` 下的纯函数单测。

---

## 已知限制

- **审核判定依赖 LLM 结构化输出**：若模型未按约定格式输出 `NEEDS_REVISION: YES/NO`，系统会回退到保守策略（未达上限则重写），可能产生非预期迭代。
- **单进程内存态**：任务状态保存在内存与 `outputs/` 文件中，无任务队列、断点续跑或水平扩展能力。
- **单用户设计**：未做鉴权、限流与多租户隔离，**仅适合本地或可信内网使用**，请勿直接暴露到公网。
- **字数统计**：中文按字符、英文按单词粗略统计，仅用于展示参考。
- **无 `.env.example`**：仓库未提供环境变量模板，需按本文档「配置说明」自行创建。

---

## 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `AuthenticationError` / `401` | `OPENAI_API_KEY` 与 `OPENAI_BASE_URL` 不匹配 | 确认 key 属于对应服务商，且 `base_url` 路径正确（DashScope 需带 `/compatible-mode/v1`） |
| `model not found` | 模型名不在该服务商可用列表 | 在「高级设置」里换用该服务商支持的模型 |
| `PermissionError` 写 `outputs/` | 目录无写权限 | 检查目录权限，或调整 `output_dir` 配置 |
| 端口 7860 被占用 | 已有进程占用 | `lsof -i:7860` 找到并结束，或修改 `main.py` 中 `server_port` |
| `python test.py` 失败但网页可用 | 环境变量加载顺序 / 工作目录差异 | 确保在项目根目录运行，且 `.env` 与 `test.py` 同级 |
| 长时间无响应 | 模型端排队或网络慢 | 检查网络；可在 `ChatOpenAI` 初始化时设置 `timeout` |

---

## 许可证

本项目以 **GNU GPL v3.0 或更高版本（GPL-3.0-or-later）** 发布，详见 [LICENSE](LICENSE)。

- 使用、复制、修改、分发本软件均须遵守 GPL v3 条款
- 修改后的源码在分发时**必须**以相同许可证开源
- 本软件按"原样"提供，**不附带任何担保**
- 完整的权限、条件与免责声明以 [LICENSE](LICENSE) 文件为准

---

Made with ❤️ by DakeGinger
