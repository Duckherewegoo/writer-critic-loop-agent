# 多智能体协作写作系统

基于 LangGraph + LangChain + Gradio 构建的多智能体协作写作平台。

## 功能特点

- 🤖 **四个智能体协作**：研究专家、写作专家、审核专家、总编辑
- 🔄 **自动迭代优化**：审核不通过自动返回修改，最多迭代指定次数
- 🎨 **美观的Web界面**：基于Gradio构建，操作简单直观
- ⚙️ **灵活配置**：支持自定义模型、温度、迭代次数等参数
- 📝 **完整的工作流**：从资料收集到最终润色，全流程自动化

## 系统架构

```
用户输入主题
    ↓
[研究专家] 收集信息、整理研究笔记
    ↓
[写作专家] 根据研究素材撰写文章草稿
    ↓
[审核专家] 多维度审核，提供修改建议
    ↓
    ├─ 需要修改？ → 返回写作专家（最多N次迭代）
    └─ 审核通过 →
              ↓
        [总编辑] 最终润色和优化
              ↓
        输出最终文章
```

## 安装

### 1. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件(注意：具体使用的模型和温度请在网页界面中选择)：

```
OPENAI_API_KEY=你的OpenAI API密钥
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，自定义API地址
MODEL_NAME=gpt-3.5-turbo # 模型示例
TEMPERATURE=0.7
MAX_ITERATIONS=3
```

## 使用

### 启动Web界面

```bash
python main.py
```

然后在浏览器中打开 `http://localhost:7860`

### 使用说明

1. 在左侧输入写作主题
2. （可选）在高级设置中调整模型、温度、迭代次数等参数
3. 点击「开始写作」按钮(按钮会转圈，结束后会显示耗时)
4. 等待系统完成写作流程
5. 在右侧查看最终文章、研究笔记和审核反馈,所有生成内容会自动保存到 outputs/ 目录

(你可以通过运行 python test.py 来快速测试你的 API Key 是否连通)

## 项目结构

```
langgraph-multi-agent/
├── agents              # 智能体定义 (研究、写作、审核、编辑)
│   ├── base_agent.py
│   ├── editor.py
│   ├── __init__.py
│   ├── researcher.py
│   ├── reviewer.py
│   └── writer.py
├── graph               # LangGraph 核心 (状态、节点、工作流构建)
│   ├── config.py
│   ├── helper.py
│   ├── __init__.py
│   ├── nodes.py
│   ├── state.py
│   └── workflow.py
├── LICENSE
├── main.py             # Gradio Web UI 入口
├── outputs             # 运行结果自动保存目录
├── pyproject.toml      # 项目配置与依赖管理
├── README.md
├── test.py             # 独立的 API 连通性测试脚本
└── utils               # 辅助工具 (文件保存、字数统计等)
    ├── helpers.py
    └── __init__.py
```

## 技术栈

- **LangGraph**：多智能体工作流编排
- **LangChain**：大语言模型应用框架
- **Gradio**：Web界面框架
- **Pydantic**：数据验证
- **Python 3.10+**

## 智能体说明

### 研究专家（ResearchAgent）
- 负责收集主题相关的信息和素材
- 输出结构化的研究笔记
- 确保信息的全面性和准确性

### 写作专家（WriterAgent）
- 根据研究素材撰写文章草稿
- 确保文章结构清晰、内容充实
- 支持根据审核反馈进行修改

### 审核专家（ReviewerAgent）
- 从多个维度审核文章质量
- 提供具体的修改建议
- 判断是否需要继续修改

### 总编辑（EditorAgent）
- 对文章进行最终润色和优化
- 优化标题、语言、结构等
- 确保文章达到出版级别

## 许可证
GPL-3.0
