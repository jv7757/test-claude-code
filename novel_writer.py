"""
多智能体小说创作系统 - 使用 LangGraph 实现
包含四个智能体：策划者、作家、编辑、评论家
"""

from typing import TypedDict, Annotated, Sequence
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import Graph, StateGraph, END
from langgraph.prebuilt import ToolExecutor
import operator
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 定义状态类型
class NovelState(TypedDict):
    """小说创作的状态"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    topic: str
    outline: str
    draft: str
    edited_draft: str
    feedback: str
    final_novel: str
    current_step: str


class NovelWritingAgents:
    """多智能体小说创作系统"""

    def __init__(self, api_key: str = None, model: str = "gpt-4", base_url: str = None):
        """
        初始化多智能体系统

        Args:
            api_key: OpenAI API密钥
            model: 使用的模型名称
            base_url: API基础URL（可选，用于自定义端点）
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model

        # 创建LLM实例
        llm_config = {"api_key": self.api_key, "model": self.model}
        if self.base_url:
            llm_config["base_url"] = self.base_url

        self.llm = ChatOpenAI(**llm_config)

        # 创建工作流图
        self.workflow = self._create_workflow()

    def _planner_agent(self, state: NovelState) -> NovelState:
        """策划者智能体 - 创建故事大纲"""
        system_prompt = """你是一位经验丰富的小说策划专家。你的任务是：
1. 理解用户提供的小说主题和要求
2. 创建一个详细的故事大纲，包括：
   - 主要情节线
   - 主要人物设定
   - 故事结构（起承转合）
   - 核心冲突和高潮
   - 结局设定
3. 大纲应该清晰、有逻辑、引人入胜

请用中文回复，创建一个结构清晰的故事大纲。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"小说主题：{state['topic']}\n\n请创建详细的故事大纲。")
        ]

        response = self.llm.invoke(messages)

        state["outline"] = response.content
        state["current_step"] = "planner"
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=f"[策划者] 正在创建故事大纲..."),
            AIMessage(content=response.content)
        ]

        return state

    def _writer_agent(self, state: NovelState) -> NovelState:
        """作家智能体 - 撰写小说内容"""
        system_prompt = """你是一位才华横溢的小说作家。你的任务是：
1. 根据提供的故事大纲创作小说内容
2. 运用生动的描写和对话
3. 保持情节连贯性和可读性
4. 创造引人入胜的场景和人物
5. 注意文学性和艺术性

请用中文撰写，字数在1000-2000字左右，创作高质量的小说内容。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"故事大纲：\n{state['outline']}\n\n请根据以上大纲创作小说内容。")
        ]

        response = self.llm.invoke(messages)

        state["draft"] = response.content
        state["current_step"] = "writer"
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=f"[作家] 正在撰写小说内容..."),
            AIMessage(content=response.content)
        ]

        return state

    def _editor_agent(self, state: NovelState) -> NovelState:
        """编辑智能体 - 改进和润色文本"""
        system_prompt = """你是一位专业的文学编辑。你的任务是：
1. 检查并改进文本的语言表达
2. 优化句子结构和段落布局
3. 增强故事的可读性和吸引力
4. 修正语法错误和不通顺的地方
5. 保持作者的原创风格，但使其更加精炼

请用中文回复，提供修改后的优化版本。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"原始草稿：\n{state['draft']}\n\n请对以上内容进行编辑和润色。")
        ]

        response = self.llm.invoke(messages)

        state["edited_draft"] = response.content
        state["current_step"] = "editor"
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=f"[编辑] 正在润色和改进文本..."),
            AIMessage(content=response.content)
        ]

        return state

    def _critic_agent(self, state: NovelState) -> NovelState:
        """评论家智能体 - 评估质量并提供最终反馈"""
        system_prompt = """你是一位资深的文学评论家。你的任务是：
1. 评估小说的整体质量
2. 分析故事结构、人物塑造、情节发展
3. 指出优点和可以进一步改进的地方
4. 提供建设性的反馈意见
5. 给出总体评分（1-10分）

请用中文回复，提供专业的文学评论。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"编辑后的小说：\n{state['edited_draft']}\n\n请对这篇小说进行专业评论。")
        ]

        response = self.llm.invoke(messages)

        state["feedback"] = response.content
        state["final_novel"] = state["edited_draft"]
        state["current_step"] = "critic"
        state["messages"] = state.get("messages", []) + [
            HumanMessage(content=f"[评论家] 正在评估作品质量..."),
            AIMessage(content=response.content)
        ]

        return state

    def _create_workflow(self) -> StateGraph:
        """创建 LangGraph 工作流"""
        # 创建状态图
        workflow = StateGraph(NovelState)

        # 添加节点（各个智能体）
        workflow.add_node("planner", self._planner_agent)
        workflow.add_node("writer", self._writer_agent)
        workflow.add_node("editor", self._editor_agent)
        workflow.add_node("critic", self._critic_agent)

        # 定义工作流顺序
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "writer")
        workflow.add_edge("writer", "editor")
        workflow.add_edge("editor", "critic")
        workflow.add_edge("critic", END)

        # 编译工作流
        return workflow.compile()

    def create_novel(self, topic: str) -> dict:
        """
        创作小说的主函数

        Args:
            topic: 小说主题

        Returns:
            包含完整创作过程的结果字典
        """
        # 初始化状态
        initial_state = {
            "messages": [],
            "topic": topic,
            "outline": "",
            "draft": "",
            "edited_draft": "",
            "feedback": "",
            "final_novel": "",
            "current_step": ""
        }

        # 执行工作流
        result = self.workflow.invoke(initial_state)

        return {
            "topic": result["topic"],
            "outline": result["outline"],
            "draft": result["draft"],
            "final_novel": result["final_novel"],
            "feedback": result["feedback"]
        }

    def stream_create_novel(self, topic: str):
        """
        流式创作小说（支持实时更新）

        Args:
            topic: 小说主题

        Yields:
            每个步骤的状态更新
        """
        # 初始化状态
        initial_state = {
            "messages": [],
            "topic": topic,
            "outline": "",
            "draft": "",
            "edited_draft": "",
            "feedback": "",
            "final_novel": "",
            "current_step": ""
        }

        # 流式执行工作流
        for state in self.workflow.stream(initial_state):
            yield state


# 便捷函数
def create_novel_writer(api_key: str = None, model: str = "gpt-4", base_url: str = None):
    """
    创建小说创作系统实例

    Args:
        api_key: OpenAI API密钥
        model: 使用的模型名称
        base_url: API基础URL

    Returns:
        NovelWritingAgents 实例
    """
    return NovelWritingAgents(api_key=api_key, model=model, base_url=base_url)
