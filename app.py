"""
基于 Gradio 的多智能体小说创作应用
使用 LangGraph 实现多个AI智能体协作创作小说
"""

import gradio as gr
from novel_writer import create_novel_writer
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def create_novel_interface(topic: str, api_key: str, model: str, base_url: str = None):
    """
    创作小说的接口函数

    Args:
        topic: 小说主题
        api_key: OpenAI API密钥
        model: 模型名称
        base_url: API基础URL（可选）

    Returns:
        大纲、草稿、最终小说、评论反馈
    """
    if not topic:
        return "请输入小说主题！", "", "", ""

    if not api_key:
        return "请输入 OpenAI API Key！", "", "", ""

    try:
        # 创建小说写作系统
        writer = create_novel_writer(
            api_key=api_key,
            model=model,
            base_url=base_url if base_url else None
        )

        # 创作小说
        result = writer.create_novel(topic)

        return (
            result["outline"],
            result["draft"],
            result["final_novel"],
            result["feedback"]
        )

    except Exception as e:
        error_msg = f"创作过程中出现错误：{str(e)}"
        return error_msg, "", "", ""


def create_gradio_app():
    """创建 Gradio 应用界面"""

    # 自定义CSS样式
    custom_css = """
    .gradio-container {
        font-family: 'Arial', sans-serif;
    }
    .output-box {
        min-height: 300px;
    }
    """

    with gr.Blocks(css=custom_css, title="AI多智能体小说创作系统", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 📚 AI多智能体小说创作系统

            这是一个基于 **LangGraph** 的多智能体协作小说创作系统，包含四个专业AI智能体：

            - 🎬 **策划者**：构思故事大纲和情节结构
            - ✍️ **作家**：根据大纲撰写生动的小说内容
            - ✏️ **编辑**：润色和改进文本质量
            - 🎭 **评论家**：评估作品并提供专业反馈

            ---
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ 配置")

                # API配置
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
                    choices=[
                        "gpt-4",
                        "gpt-4-turbo-preview",
                        "gpt-3.5-turbo",
                        "gpt-4o",
                        "gpt-4o-mini"
                    ],
                    value="gpt-4o-mini"
                )

                gr.Markdown("### 📝 小说主题")

                topic_input = gr.Textbox(
                    label="请输入小说主题或简要描述",
                    placeholder="例如：一个关于时间旅行的科幻故事，主角试图改变过去的错误...",
                    lines=4
                )

                create_btn = gr.Button("🚀 开始创作", variant="primary", size="lg")

                gr.Markdown(
                    """
                    ---
                    ### 💡 使用提示：
                    1. 输入你的 OpenAI API Key
                    2. 选择合适的模型（推荐 gpt-4o-mini 或 gpt-4）
                    3. 描述你想要的小说主题
                    4. 点击"开始创作"，等待AI智能体协作完成

                    ⏱️ 创作过程大约需要 1-3 分钟
                    """
                )

            with gr.Column(scale=2):
                gr.Markdown("### 📖 创作结果")

                with gr.Tabs():
                    with gr.TabItem("📋 故事大纲"):
                        outline_output = gr.Textbox(
                            label="策划者创建的故事大纲",
                            lines=15,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("📄 初稿"):
                        draft_output = gr.Textbox(
                            label="作家撰写的初稿",
                            lines=15,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("✨ 最终作品"):
                        final_output = gr.Textbox(
                            label="编辑润色后的最终作品",
                            lines=15,
                            elem_classes=["output-box"]
                        )

                    with gr.TabItem("💬 专业点评"):
                        feedback_output = gr.Textbox(
                            label="评论家的专业反馈",
                            lines=15,
                            elem_classes=["output-box"]
                        )

        # 绑定事件
        create_btn.click(
            fn=create_novel_interface,
            inputs=[topic_input, api_key_input, model_input, base_url_input],
            outputs=[outline_output, draft_output, final_output, feedback_output]
        )

        # 示例
        gr.Markdown("### 📚 示例主题")
        gr.Examples(
            examples=[
                ["一个关于AI觉醒的科幻故事，探讨人工智能与人类情感的关系"],
                ["古代武侠小说，一个少年习武复仇的故事"],
                ["现代都市爱情故事，两个陌生人在咖啡馆的偶遇"],
                ["悬疑推理小说，一起发生在孤岛上的密室谋杀案"],
                ["奇幻冒险故事，勇者召集伙伴拯救被黑暗笼罩的王国"]
            ],
            inputs=topic_input
        )

        gr.Markdown(
            """
            ---

            ### 🔧 技术栈
            - **LangGraph**: 多智能体编排框架
            - **LangChain**: LLM应用开发框架
            - **Gradio**: Web界面框架
            - **OpenAI API**: 大语言模型服务

            ### 📌 注意事项
            - 确保你有有效的 OpenAI API Key
            - 不同模型的效果和成本不同，建议先用 gpt-4o-mini 测试
            - 创作时间取决于模型速度和网络状况
            - 生成的内容仅供参考和娱乐，请合理使用

            ---

            Made with ❤️ by LangGraph & Gradio
            """
        )

    return app


if __name__ == "__main__":
    # 创建并启动应用
    app = create_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
