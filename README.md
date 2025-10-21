# 📚 AI多智能体小说创作系统

基于 **LangGraph** 和 **Gradio** 的多智能体协作小说创作应用。本系统使用四个专业AI智能体协同工作，从构思到成稿，完成高质量小说创作。

## ✨ 特性

- 🎬 **策划者智能体**：构思故事大纲和情节结构
- ✍️ **作家智能体**：根据大纲撰写生动的小说内容
- ✏️ **编辑智能体**：润色和改进文本质量
- 🎭 **评论家智能体**：评估作品并提供专业反馈
- 🌐 **友好的Web界面**：基于Gradio构建的直观用户界面
- 🔄 **完整的创作流程**：从主题输入到最终成稿的全自动化流程

## 🏗️ 系统架构

本系统采用 LangGraph 构建多智能体工作流：

```
用户输入主题
    ↓
策划者 (Planner) - 创建故事大纲
    ↓
作家 (Writer) - 撰写小说内容
    ↓
编辑 (Editor) - 润色改进文本
    ↓
评论家 (Critic) - 评估并提供反馈
    ↓
输出最终作品
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- OpenAI API Key

### 2. 安装依赖

```bash
# 克隆项目
git clone <your-repo-url>
cd test-claude-code

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 文件并重命名为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 OpenAI API Key：

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. 启动应用

```bash
python app.py
```

应用将在 `http://localhost:7860` 启动。

## 📖 使用说明

1. **输入API配置**
   - 在左侧面板输入你的 OpenAI API Key
   - 选择合适的模型（推荐 `gpt-4o-mini` 或 `gpt-4`）
   - 可选：配置自定义的 API Base URL

2. **输入小说主题**
   - 在"小说主题"文本框中描述你想要的小说
   - 可以参考示例主题获取灵感

3. **开始创作**
   - 点击"开始创作"按钮
   - 等待1-3分钟，智能体将依次完成工作

4. **查看结果**
   - 在右侧标签页中查看各个阶段的产出：
     - 📋 故事大纲
     - 📄 初稿
     - ✨ 最终作品
     - 💬 专业点评

## 💡 示例主题

- "一个关于AI觉醒的科幻故事，探讨人工智能与人类情感的关系"
- "古代武侠小说，一个少年习武复仇的故事"
- "现代都市爱情故事，两个陌生人在咖啡馆的偶遇"
- "悬疑推理小说，一起发生在孤岛上的密室谋杀案"
- "奇幻冒险故事，勇者召集伙伴拯救被黑暗笼罩的王国"

## 🔧 技术栈

- **LangGraph** (>= 0.2.0) - 多智能体编排框架
- **LangChain** (>= 0.3.0) - LLM应用开发框架
- **LangChain-OpenAI** (>= 0.2.0) - OpenAI集成
- **Gradio** (>= 4.0.0) - Web界面框架
- **Python-dotenv** (>= 1.0.0) - 环境变量管理

## 📁 项目结构

```
test-claude-code/
├── app.py              # Gradio Web应用主文件
├── novel_writer.py     # LangGraph多智能体核心逻辑
├── requirements.txt    # Python依赖包
├── .env.example        # 环境变量示例
├── .gitignore         # Git忽略文件
└── README.md          # 项目文档
```

## 🎯 核心功能

### NovelWritingAgents 类

多智能体系统的核心类，包含：

- `_planner_agent()` - 策划者智能体
- `_writer_agent()` - 作家智能体
- `_editor_agent()` - 编辑智能体
- `_critic_agent()` - 评论家智能体
- `create_novel()` - 创作小说的主函数
- `stream_create_novel()` - 流式创作（支持实时更新）

### Gradio界面

提供直观的Web界面，包括：

- API配置面板
- 主题输入框
- 分标签页的结果展示
- 示例主题快速选择

## ⚙️ 自定义配置

### 使用不同的LLM模型

在界面中选择或在代码中修改：

```python
writer = create_novel_writer(
    api_key="your-api-key",
    model="gpt-4",  # 可选：gpt-4, gpt-4o, gpt-3.5-turbo等
    base_url="https://api.openai.com/v1"  # 可选：自定义端点
)
```

### 调整智能体提示词

编辑 `novel_writer.py` 中各个智能体的 `system_prompt` 来自定义行为。

## 📊 工作流程详解

1. **策划阶段**
   - 输入：用户提供的小说主题
   - 输出：包含情节线、人物设定、故事结构的详细大纲

2. **写作阶段**
   - 输入：策划者创建的大纲
   - 输出：1000-2000字的小说初稿

3. **编辑阶段**
   - 输入：作家撰写的初稿
   - 输出：经过润色和改进的版本

4. **评论阶段**
   - 输入：编辑后的文本
   - 输出：专业的文学评论和改进建议

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📝 注意事项

- 确保有稳定的网络连接
- OpenAI API 调用会产生费用，请注意使用量
- 不同模型的效果和成本差异较大，建议先用便宜的模型测试
- 生成内容仅供参考和娱乐，请合理使用

## 📄 许可证

MIT License

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) - 强大的多智能体编排框架
- [LangChain](https://github.com/langchain-ai/langchain) - 优秀的LLM应用开发框架
- [Gradio](https://github.com/gradio-app/gradio) - 简洁易用的ML Web界面框架

---

Made with ❤️ by LangGraph & Gradio
