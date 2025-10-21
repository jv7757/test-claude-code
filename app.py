"""
基于 Gradio 的多智能体小说创作应用
支持多章节创作，章节知识库参考
包含审核循环机制：作家-评论家循环，最多修改5次
"""

import gradio as gr
from novel_writer import create_novel_writer
import os
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 全局状态变量
class NovelSession:
    def __init__(self):
        self.writer = None
        self.state = None
        self.chapters = {}  # 保存已完成的章节
        self.topic = ""
        self.overall_outline = ""
        self.chapter_outlines = []
        self.current_chapter = 1
        self.total_chapters = 0


# 创建全局会话
session = NovelSession()


def create_outline(topic: str, api_key: str, model: str, base_url: str = None):
    """创建小说大纲（第一步）"""
    if not topic:
        return "请输入小说主题！", "", ""

    if not api_key:
        return "请输入 OpenAI API Key！", "", ""

    try:
        # 初始化writer
        session.writer = create_novel_writer(
            api_key=api_key,
            model=model,
            base_url=base_url if base_url else None
        )
        session.topic = topic
        session.chapters = {}
        session.current_chapter = 1

        # 只创建大纲
        initial_state = {
            "messages": [],
            "topic": topic,
            "overall_outline": "",
            "chapter_outlines": [],
            "chapters": {},
            "current_chapter_num": 1,
            "total_chapters": 0,
            "draft": "",
            "feedback": "",
            "all_feedbacks": "",
            "current_step": "",
            "revision_count": 0,
            "approved": False
        }

        # 调用策划者
        result = session.writer._planner_agent(initial_state)

        session.state = result
        session.overall_outline = result["overall_outline"]
        session.chapter_outlines = result["chapter_outlines"]
        session.total_chapters = result["total_chapters"]

        # 生成章节列表HTML
        chapter_list_html = generate_chapter_list_html()

        return (
            result["overall_outline"],
            chapter_list_html,
            f"✅ 成功创建包含 {session.total_chapters} 个章节的大纲！现在可以选择章节开始创作。"
        )

    except Exception as e:
        error_msg = f"创建大纲时出现错误：{str(e)}"
        return error_msg, "", error_msg


def generate_chapter_list_html():
    """生成章节列表HTML"""
    if not session.chapter_outlines:
        return "<p>暂无章节</p>"

    html = "<div style='padding: 10px;'>"
    html += f"<h3>📖 章节目录 ({len(session.chapters)}/{session.total_chapters})</h3>"
    html += "<div style='max-height: 400px; overflow-y: auto;'>"

    for outline in session.chapter_outlines:
        num = outline["number"]
        title = outline["title"]

        # 判断状态
        if num in session.chapters:
            status = "✅ 已完成"
            status_color = "#4CAF50"
        elif num == session.current_chapter:
            status = "▶️ 进行中"
            status_color = "#2196F3"
        else:
            status = "⏸️ 待创作"
            status_color = "#9E9E9E"

        html += f"""
        <div style='
            margin: 8px 0;
            padding: 12px;
            border-left: 4px solid {status_color};
            background: #f5f5f5;
            border-radius: 4px;
        '>
            <div style='font-weight: bold; color: {status_color};'>
                第{num}章: {title}
            </div>
            <div style='font-size: 0.9em; color: #666; margin-top: 4px;'>
                {status}
            </div>
        </div>
        """

    html += "</div></div>"
    return html


def create_current_chapter(chapter_num: int):
    """创作指定章节"""
    if not session.writer or not session.state:
        return "请先创建大纲！", "", "", "", generate_chapter_list_html()

    try:
        # 更新当前章节号
        session.current_chapter = chapter_num

        # 准备状态（包含已完成章节作为知识库）
        state = {
            **session.state,
            "current_chapter_num": chapter_num,
            "chapters": session.chapters,
            "revision_count": 0,
            "approved": False,
            "draft": "",
            "feedback": "",
            "all_feedbacks": "",
            "messages": []
        }

        # 执行作家 -> 评论家循环
        state = session.writer._writer_agent(state)
        state = session.writer._critic_agent(state)

        # 如果需要修改，继续循环
        while not state["approved"] and state["revision_count"] < 5:
            state = session.writer._writer_agent(state)
            state = session.writer._critic_agent(state)

        # 保存章节
        current_outline = next((ch for ch in session.chapter_outlines if ch["number"] == chapter_num), {})
        session.chapters[chapter_num] = {
            "chapter_number": chapter_num,
            "title": current_outline.get("title", f"第{chapter_num}章"),
            "outline": current_outline.get("summary", ""),
            "content": state["draft"],
            "status": "completed",
            "revision_count": state["revision_count"],
            "approved": state["approved"],
            "feedback": state["feedback"],
            "all_feedbacks": state["all_feedbacks"]
        }

        # 更新session状态
        session.state = state

        # 生成状态信息
        status_info = f"""## 第{chapter_num}章创作完成

- **章节标题**: {current_outline.get("title", f"第{chapter_num}章")}
- **修改次数**: {state['revision_count']} 次
- **审核结果**: {'✅ 通过' if state['approved'] else '⚠️ 未通过（已达最大修改次数）'}
- **最终版本**: 第 {state['revision_count']} 版

---
"""

        # 更新章节列表
        chapter_list_html = generate_chapter_list_html()

        # 当前章节内容
        current_content = state["draft"]

        # 最新反馈
        current_feedback = state["feedback"]

        # 所有反馈历史
        all_feedbacks = state["all_feedbacks"]

        return (
            status_info,
            current_content,
            current_feedback,
            all_feedbacks,
            chapter_list_html
        )

    except Exception as e:
        error_msg = f"创作第{chapter_num}章时出现错误：{str(e)}"
        return error_msg, "", "", "", generate_chapter_list_html()


def get_chapter_content(chapter_num: int):
    """获取指定章节的内容"""
    if chapter_num not in session.chapters:
        return f"第{chapter_num}章尚未创作", ""

    chapter = session.chapters[chapter_num]
    content = chapter["content"]
    feedback = chapter.get("all_feedbacks", chapter.get("feedback", ""))

    return content, feedback


def export_novel():
    """导出完整小说"""
    if not session.chapters:
        return "暂无内容可导出"

    novel_text = f"# {session.topic}\n\n"
    novel_text += f"## 总体大纲\n\n{session.overall_outline}\n\n"
    novel_text += "---\n\n"

    # 按章节号排序
    sorted_chapters = sorted(session.chapters.items(), key=lambda x: x[0])

    for num, chapter in sorted_chapters:
        novel_text += f"## 第{num}章：{chapter['title']}\n\n"
        novel_text += f"{chapter['content']}\n\n"
        novel_text += "---\n\n"

    return novel_text


def create_gradio_app():
    """创建 Gradio 应用界面"""

    custom_css = """
    .gradio-container {
        font-family: 'Arial', sans-serif;
    }
    .output-box {
        min-height: 300px;
    }
    .sidebar {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
    }
    """

    with gr.Blocks(css=custom_css, title="AI多智能体小说创作系统", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 📚 AI多智能体小说创作系统（多章节版）

            这是一个基于 **LangGraph** 的多智能体协作小说创作系统，支持多章节创作：

            - 🎬 **策划者**：创建包含多个章节的详细大纲
            - ✍️ **作家**：逐章创作，参考已完成章节（知识库）
            - 🎭 **评论家**：严格评审每章质量

            ## 🔄 工作流程

            1. **创建大纲** → 策划者生成多章节详细大纲
            2. **选择章节** → 从目录中选择要创作的章节
            3. **智能创作** → 作家创作，评论家审核（最多修改5次）
            4. **知识库参考** → 后续章节自动参考已完成章节，保持连贯性

            ---
            """
        )

        with gr.Row():
            # 左侧：配置和控制面板
            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ 配置")

                api_key_input = gr.Textbox(
                    label="OpenAI API Key",
                    type="password",
                    placeholder="sk-...",
                    value=os.getenv("OPENAI_API_KEY", "")
                )

                base_url_input = gr.Textbox(
                    label="API Base URL (可选)",
                    placeholder="https://api.openai.com/v1",
                    value=os.getenv("OPENAI_BASE_URL", "")
                )

                model_input = gr.Dropdown(
                    label="选择模型",
                    choices=["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
                    value="gpt-4o-mini"
                )

                gr.Markdown("### 📝 小说主题")

                topic_input = gr.Textbox(
                    label="请输入小说主题或简要描述",
                    placeholder="例如：一个关于时间旅行的科幻故事...",
                    lines=4
                )

                create_outline_btn = gr.Button("📋 创建大纲", variant="primary", size="lg")

                gr.Markdown("### 📖 章节创作")

                chapter_selector = gr.Number(
                    label="选择要创作的章节号",
                    value=1,
                    minimum=1,
                    maximum=20,
                    step=1,
                    precision=0
                )

                create_chapter_btn = gr.Button("✍️ 创作该章节", variant="secondary", size="lg")

                gr.Markdown("---")

                export_btn = gr.Button("💾 导出完整小说", variant="secondary")

                gr.Markdown(
                    """
                    ### 💡 使用提示：
                    1. 输入主题，点击"创建大纲"
                    2. 查看右侧章节目录
                    3. 选择章节号，点击"创作该章节"
                    4. 可按任意顺序创作章节
                    5. 后续章节会参考已完成章节
                    6. 全部完成后可导出小说

                    ⏱️ 每章创作约2-5分钟
                    """
                )

            # 中间：主要内容区
            with gr.Column(scale=2):
                gr.Markdown("### 📖 创作内容")

                with gr.Tabs():
                    with gr.TabItem("📋 总体大纲"):
                        outline_output = gr.Textbox(
                            label="策划者创建的多章节大纲",
                            lines=20,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("📊 创作状态"):
                        status_output = gr.Markdown(label="当前章节状态")

                    with gr.TabItem("✨ 当前章节"):
                        current_chapter_output = gr.Textbox(
                            label="当前章节内容",
                            lines=20,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("💬 当前评审"):
                        current_feedback_output = gr.Textbox(
                            label="当前章节最新评审",
                            lines=15,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("📜 评审历史"):
                        all_feedback_output = gr.Textbox(
                            label="所有评审记录",
                            lines=15,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("📖 完整小说"):
                        full_novel_output = gr.Textbox(
                            label="完整小说（所有已完成章节）",
                            lines=25,
                            elem_classes=["output-box"]
                        )

            # 右侧：章节目录侧边栏
            with gr.Column(scale=1, elem_classes=["sidebar"]):
                gr.Markdown("### 📑 章节目录")
                chapter_list_display = gr.HTML(
                    value="<p>请先创建大纲</p>",
                    label="章节列表"
                )

                outline_status = gr.Textbox(
                    label="操作提示",
                    lines=3,
                    interactive=False
                )

        # 示例
        gr.Markdown("### 📚 示例主题")
        gr.Examples(
            examples=[
                ["一个关于AI觉醒的科幻故事，探讨人工智能与人类情感的关系，包含多个场景转换"],
                ["古代武侠小说，一个少年从习武到复仇的成长历程"],
                ["现代都市爱情故事，两个陌生人从相遇到相爱的过程"],
                ["悬疑推理小说，侦探在孤岛上调查连环谋杀案"],
                ["奇幻冒险故事，勇者召集伙伴、收集神器、最终拯救王国"]
            ],
            inputs=topic_input
        )

        # 事件绑定
        create_outline_btn.click(
            fn=create_outline,
            inputs=[topic_input, api_key_input, model_input, base_url_input],
            outputs=[outline_output, chapter_list_display, outline_status]
        )

        create_chapter_btn.click(
            fn=create_current_chapter,
            inputs=[chapter_selector],
            outputs=[status_output, current_chapter_output, current_feedback_output, all_feedback_output, chapter_list_display]
        )

        export_btn.click(
            fn=export_novel,
            outputs=[full_novel_output]
        )

        gr.Markdown(
            """
            ---

            ### 🔧 技术栈
            - **LangGraph**: 多智能体编排框架（支持条件分支和循环）
            - **LangChain**: LLM应用开发框架
            - **Gradio**: Web界面框架
            - **OpenAI API**: 大语言模型服务

            ### ✨ 核心特性
            - **多章节创作**：支持创建和管理多个章节
            - **知识库参考**：已完成章节作为知识库，供后续创作参考
            - **智能审核循环**：每章独立审核，最多5次修改机会
            - **章节目录**：实时显示创作进度和章节状态
            - **灵活创作**：支持任意顺序创作章节
            - **完整导出**：一键导出包含所有章节的完整小说

            ### 📌 注意事项
            - 确保有有效的 OpenAI API Key
            - 建议先用 gpt-4o-mini 测试
            - 每章创作时间2-5分钟（取决于修改次数）
            - 后续章节会参考前面章节，确保连贯性
            - 可以随时查看和导出已完成章节

            ---

            Made with ❤️ by LangGraph & Gradio
            """
        )

    return app


if __name__ == "__main__":
    app = create_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
