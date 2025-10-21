"""
基于 Gradio 的多智能体小说创作应用
支持多部小说创作，章节知识库参考，SQLite持久化存储
包含审核循环机制：作家-评论家循环，最多修改5次
"""

import gradio as gr
from novel_writer import create_novel_writer
from database import db
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 全局状态变量
class NovelSession:
    def __init__(self):
        self.writer = None
        self.novel_id = None  # 当前小说ID
        self.state = None
        self.chapters = {}  # 保存已完成的章节
        self.topic = ""
        self.overall_outline = ""
        self.chapter_outlines = []
        self.current_chapter = 1
        self.total_chapters = 0


# 创建全局会话
session = NovelSession()


# ==================== 会话管理函数 ====================

def get_novels_list():
    """获取所有小说列表，生成HTML"""
    novels = db.get_all_novels()

    if not novels:
        return "<p style='color: #999; padding: 20px; text-align: center;'>暂无小说，请创建新小说开始创作</p>"

    html = "<div style='padding: 10px;'>"

    for novel in novels:
        # 计算进度
        progress = novel['completed_chapters']
        total = novel['total_chapters']
        progress_percent = int((progress / total * 100)) if total > 0 else 0

        # 状态颜色
        status_colors = {
            'active': '#2196F3',
            'completed': '#4CAF50',
            'archived': '#9E9E9E'
        }
        status_text = {
            'active': '进行中',
            'completed': '已完成',
            'archived': '已归档'
        }

        color = status_colors.get(novel['status'], '#9E9E9E')
        status = status_text.get(novel['status'], novel['status'])

        # 时间格式化
        updated = novel['updated_at'][:16] if novel['updated_at'] else 'N/A'

        html += f"""
        <div style='
            margin: 10px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-left: 4px solid {color};
            background: #fafafa;
            border-radius: 4px;
            cursor: pointer;
        ' onclick='alert("小说ID: {novel["id"]}，请在加载小说框中输入此ID")'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div style='flex: 1;'>
                    <div style='font-weight: bold; font-size: 1.1em; color: #333;'>
                        {novel['title']}
                    </div>
                    <div style='font-size: 0.9em; color: #666; margin-top: 4px;'>
                        ID: {novel['id']} | {status} | 更新: {updated}
                    </div>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 0.9em; color: {color}; font-weight: bold;'>
                        {progress}/{total} 章
                    </div>
                    <div style='width: 100px; height: 8px; background: #e0e0e0; border-radius: 4px; margin-top: 4px;'>
                        <div style='width: {progress_percent}%; height: 100%; background: {color}; border-radius: 4px;'></div>
                    </div>
                </div>
            </div>
        </div>
        """

    html += "</div>"
    return html


def create_new_novel_session(title: str):
    """创建新小说会话"""
    if not title or title.strip() == "":
        return get_novels_list(), "❌ 请输入小说标题"

    try:
        # 重置session
        session.novel_id = None
        session.state = None
        session.chapters = {}
        session.topic = ""
        session.overall_outline = ""
        session.chapter_outlines = []
        session.current_chapter = 1
        session.total_chapters = 0

        return get_novels_list(), f"✅ 已创建新会话「{title}」，现在可以输入主题并创建大纲"

    except Exception as e:
        return get_novels_list(), f"❌ 创建失败：{str(e)}"


def load_novel_session(novel_id: int):
    """加载现有小说会话"""
    try:
        novel_id = int(novel_id)
        novel = db.get_novel(novel_id)

        if not novel:
            return get_novels_list(), "", "", "", f"❌ 未找到ID为 {novel_id} 的小说"

        # 加载到session
        session.novel_id = novel_id
        session.topic = novel['topic']
        session.overall_outline = novel['overall_outline']
        session.chapter_outlines = novel['chapter_outlines']
        session.total_chapters = novel['total_chapters']
        session.current_chapter = 1

        # 加载已完成的章节
        chapters = db.get_completed_chapters(novel_id)
        session.chapters = {}
        for ch_num, ch_data in chapters.items():
            session.chapters[ch_num] = {
                "chapter_number": ch_data['chapter_number'],
                "title": ch_data['title'],
                "outline": ch_data['outline'],
                "content": ch_data['content'],
                "status": ch_data['status'],
                "revision_count": ch_data['revision_count'],
                "approved": bool(ch_data['approved']),
                "feedback": ch_data['feedback'],
                "all_feedbacks": ch_data['all_feedbacks']
            }

        # 重建state（不包含writer，writer在创作章节时初始化）
        session.state = {
            "messages": [],
            "topic": novel['topic'],
            "overall_outline": novel['overall_outline'],
            "chapter_outlines": novel['chapter_outlines'],
            "chapters": session.chapters,
            "current_chapter_num": 1,
            "total_chapters": novel['total_chapters'],
            "draft": "",
            "feedback": "",
            "all_feedbacks": "",
            "current_step": "",
            "revision_count": 0,
            "approved": False
        }

        # 生成章节列表
        chapter_list_html = generate_chapter_list_html()

        return (
            get_novels_list(),
            novel['overall_outline'],
            chapter_list_html,
            "",
            f"✅ 已加载小说「{novel['title']}」（{len(session.chapters)}/{session.total_chapters}章完成）"
        )

    except ValueError:
        return get_novels_list(), "", "", "", "❌ 请输入有效的数字ID"
    except Exception as e:
        return get_novels_list(), "", "", "", f"❌ 加载失败：{str(e)}"


def delete_novel_session(novel_id: int):
    """删除小说会话"""
    try:
        novel_id = int(novel_id)
        novel = db.get_novel(novel_id)

        if not novel:
            return get_novels_list(), f"❌ 未找到ID为 {novel_id} 的小说"

        db.delete_novel(novel_id)

        # 如果删除的是当前小说，清空session
        if session.novel_id == novel_id:
            session.novel_id = None
            session.state = None
            session.chapters = {}

        return get_novels_list(), f"✅ 已删除小说「{novel['title']}」"

    except ValueError:
        return get_novels_list(), "❌ 请输入有效的数字ID"
    except Exception as e:
        return get_novels_list(), f"❌ 删除失败：{str(e)}"


# ==================== 原有创作函数（添加自动保存） ====================

def create_outline(topic: str, title: str, api_key: str, model: str, base_url: str = None):
    """创建小说大纲（第一步）- 添加数据库保存"""
    if not topic:
        return "", "", "请输入小说主题！", get_novels_list()

    if not title:
        return "", "", "请输入小说标题！", get_novels_list()

    if not api_key:
        return "", "", "请输入 OpenAI API Key！", get_novels_list()

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

        # 保存到数据库
        if session.novel_id is None:
            # 创建新小说
            session.novel_id = db.create_novel(
                title=title,
                topic=topic,
                overall_outline=result["overall_outline"],
                chapter_outlines=result["chapter_outlines"],
                total_chapters=result["total_chapters"]
            )
        else:
            # 更新现有小说
            db.update_novel(
                session.novel_id,
                topic=topic,
                overall_outline=result["overall_outline"],
                chapter_outlines=result["chapter_outlines"],
                total_chapters=result["total_chapters"]
            )

        # 生成章节列表HTML
        chapter_list_html = generate_chapter_list_html()

        return (
            result["overall_outline"],
            chapter_list_html,
            f"✅ 成功创建包含 {session.total_chapters} 个章节的大纲！（小说ID: {session.novel_id}）",
            get_novels_list()
        )

    except Exception as e:
        error_msg = f"创建大纲时出现错误：{str(e)}"
        return "", "", error_msg, get_novels_list()


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


def create_current_chapter(chapter_num: int, api_key: str, model: str, base_url: str = None):
    """创作指定章节 - 添加数据库保存"""
    if not session.state:
        return "请先创建大纲！", "", "", "", generate_chapter_list_html(), get_novels_list()

    if session.novel_id is None:
        return "请先保存小说（创建大纲时会自动保存）", "", "", "", generate_chapter_list_html(), get_novels_list()

    if not api_key:
        return "请输入 OpenAI API Key！", "", "", "", generate_chapter_list_html(), get_novels_list()

    # 如果session.writer不存在，重新初始化（用于加载已有小说后继续创作）
    if not session.writer:
        try:
            session.writer = create_novel_writer(
                api_key=api_key,
                model=model,
                base_url=base_url if base_url else None
            )
        except Exception as e:
            return f"初始化AI失败：{str(e)}", "", "", "", generate_chapter_list_html(), get_novels_list()

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

        # 保存章节到内存
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

        # 保存章节到数据库
        db.create_or_update_chapter(
            novel_id=session.novel_id,
            chapter_number=chapter_num,
            title=current_outline.get("title", f"第{chapter_num}章"),
            outline=current_outline.get("summary", ""),
            content=state["draft"],
            status="completed",
            revision_count=state["revision_count"],
            approved=state["approved"],
            feedback=state["feedback"],
            all_feedbacks=state["all_feedbacks"]
        )

        # 更新session状态
        session.state = state

        # 生成状态信息
        status_info = f"""## 第{chapter_num}章创作完成

- **章节标题**: {current_outline.get("title", f"第{chapter_num}章")}
- **修改次数**: {state['revision_count']} 次
- **审核结果**: {'✅ 通过' if state['approved'] else '⚠️ 未通过（已达最大修改次数）'}
- **最终版本**: 第 {state['revision_count']} 版
- **已保存到数据库**: 小说ID {session.novel_id}

---
"""

        # 更新章节列表
        chapter_list_html = generate_chapter_list_html()

        return (
            status_info,
            state["draft"],
            state["feedback"],
            state["all_feedbacks"],
            chapter_list_html,
            get_novels_list()
        )

    except Exception as e:
        error_msg = f"创作第{chapter_num}章时出现错误：{str(e)}"
        return error_msg, "", "", "", generate_chapter_list_html(), get_novels_list()


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


def get_statistics():
    """获取统计信息"""
    stats = db.get_statistics()

    stats_html = f"""
    <div style='padding: 15px; background: #f5f5f5; border-radius: 8px;'>
        <h3 style='margin-top: 0;'>📊 统计信息</h3>
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px;'>
            <div style='padding: 10px; background: white; border-radius: 4px;'>
                <div style='font-size: 0.9em; color: #666;'>总小说数</div>
                <div style='font-size: 1.5em; font-weight: bold; color: #2196F3;'>{stats['total_novels']}</div>
            </div>
            <div style='padding: 10px; background: white; border-radius: 4px;'>
                <div style='font-size: 0.9em; color: #666;'>活跃小说</div>
                <div style='font-size: 1.5em; font-weight: bold; color: #4CAF50;'>{stats['active_novels']}</div>
            </div>
            <div style='padding: 10px; background: white; border-radius: 4px;'>
                <div style='font-size: 0.9em; color: #666;'>总章节数</div>
                <div style='font-size: 1.5em; font-weight: bold; color: #FF9800;'>{stats['total_chapters']}</div>
            </div>
            <div style='padding: 10px; background: white; border-radius: 4px;'>
                <div style='font-size: 0.9em; color: #666;'>已完成章节</div>
                <div style='font-size: 1.5em; font-weight: bold; color: #9C27B0;'>{stats['completed_chapters']}</div>
            </div>
        </div>
    </div>
    """

    return stats_html


# ==================== Gradio界面 ====================

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
    .session-panel {
        background-color: #fff;
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    """

    with gr.Blocks(css=custom_css, title="AI多智能体小说创作系统", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 📚 AI多智能体小说创作系统（会话管理版）

            支持多部小说创作、章节知识库参考、SQLite持久化存储

            - 🎬 **策划者**：创建包含多个章节的详细大纲
            - ✍️ **作家**：逐章创作，参考已完成章节
            - 🎭 **评论家**：严格评审每章质量
            - 💾 **持久化**：所有小说和章节自动保存到数据库

            ---
            """
        )

        with gr.Row():
            # 左侧：会话管理和配置
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["session-panel"]):
                    gr.Markdown("### 📂 会话管理")

                    with gr.Tab("新建小说"):
                        new_title_input = gr.Textbox(
                            label="小说标题",
                            placeholder="输入小说标题...",
                            lines=1
                        )
                        create_session_btn = gr.Button("➕ 创建新小说", variant="primary")

                    with gr.Tab("加载小说"):
                        load_id_input = gr.Number(
                            label="小说ID",
                            value=1,
                            minimum=1,
                            precision=0
                        )
                        load_session_btn = gr.Button("📂 加载小说", variant="secondary")

                    with gr.Tab("删除小说"):
                        delete_id_input = gr.Number(
                            label="小说ID",
                            value=1,
                            minimum=1,
                            precision=0
                        )
                        delete_session_btn = gr.Button("🗑️ 删除小说", variant="stop")

                    session_status = gr.Textbox(
                        label="操作提示",
                        lines=2,
                        interactive=False
                    )

                gr.Markdown("### ⚙️ API配置")

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

                gr.Markdown("### 📝 创作")

                novel_title_input = gr.Textbox(
                    label="小说标题",
                    placeholder="为当前小说输入标题...",
                    lines=1
                )

                topic_input = gr.Textbox(
                    label="小说主题或简要描述",
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

            # 右侧：章节目录和小说列表
            with gr.Column(scale=1, elem_classes=["sidebar"]):
                with gr.Tabs():
                    with gr.TabItem("📑 章节目录"):
                        chapter_list_display = gr.HTML(
                            value="<p>请先创建大纲</p>",
                            label="章节列表"
                        )

                    with gr.TabItem("📚 小说列表"):
                        novels_list_display = gr.HTML(
                            value=get_novels_list(),
                            label="所有小说"
                        )

                        refresh_list_btn = gr.Button("🔄 刷新列表", size="sm")

                    with gr.TabItem("📊 统计"):
                        statistics_display = gr.HTML(
                            value=get_statistics(),
                            label="统计信息"
                        )

                        refresh_stats_btn = gr.Button("🔄 刷新统计", size="sm")

        # 事件绑定
        create_session_btn.click(
            fn=create_new_novel_session,
            inputs=[new_title_input],
            outputs=[novels_list_display, session_status]
        )

        load_session_btn.click(
            fn=load_novel_session,
            inputs=[load_id_input],
            outputs=[novels_list_display, outline_output, chapter_list_display, outline_output, session_status]
        )

        delete_session_btn.click(
            fn=delete_novel_session,
            inputs=[delete_id_input],
            outputs=[novels_list_display, session_status]
        )

        create_outline_btn.click(
            fn=create_outline,
            inputs=[topic_input, novel_title_input, api_key_input, model_input, base_url_input],
            outputs=[outline_output, chapter_list_display, session_status, novels_list_display]
        )

        create_chapter_btn.click(
            fn=create_current_chapter,
            inputs=[chapter_selector, api_key_input, model_input, base_url_input],
            outputs=[status_output, current_chapter_output, current_feedback_output, all_feedback_output, chapter_list_display, novels_list_display]
        )

        export_btn.click(
            fn=export_novel,
            outputs=[full_novel_output]
        )

        refresh_list_btn.click(
            fn=get_novels_list,
            outputs=[novels_list_display]
        )

        refresh_stats_btn.click(
            fn=get_statistics,
            outputs=[statistics_display]
        )

        gr.Markdown(
            """
            ---

            ### 🔧 技术栈
            - **LangGraph**: 多智能体编排框架
            - **Gradio**: Web界面框架
            - **SQLite**: 持久化存储
            - **OpenAI API**: 大语言模型服务

            ### ✨ 核心特性
            - **多小说管理**：支持创建和管理多部小说
            - **持久化存储**：所有数据自动保存到SQLite数据库
            - **会话切换**：随时加载和切换不同小说
            - **章节知识库**：已完成章节作为知识库参考
            - **智能审核**：每章独立审核，最多5次修改

            ### 📌 使用说明
            1. 创建新小说或加载现有小说
            2. 输入主题并创建大纲
            3. 选择章节号并创作
            4. 所有内容自动保存到数据库
            5. 可随时切换到其他小说继续创作

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
