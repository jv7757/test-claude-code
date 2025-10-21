"""
多智能体小说创作系统 - 使用 LangGraph 实现
包含三个智能体：策划者、作家、评论家
作家和评论家形成审核循环，最多修改5次
"""

from typing import TypedDict, Annotated, Sequence, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
import operator
import os
import re
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
    feedback: str
    all_feedbacks: str  # 所有历史反馈
    final_novel: str
    current_step: str
    revision_count: int  # 修改次数
    approved: bool  # 是否通过审核


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

        return {
            **state,
            "outline": response.content,
            "current_step": "planner",
            "messages": [
                HumanMessage(content=f"[策划者] 正在创建故事大纲..."),
                AIMessage(content=response.content)
            ]
        }

    def _writer_agent(self, state: NovelState) -> NovelState:
        """作家智能体 - 撰写并润色小说内容"""
        revision_count = state.get("revision_count", 0)

        if revision_count == 0:
            # 首次创作
            system_prompt = """你是一位才华横溢的小说作家兼编辑。你的任务是：
1. 根据提供的故事大纲创作小说内容
2. 运用生动的描写和对话
3. 保持情节连贯性和可读性
4. 创造引人入胜的场景和人物
5. 注意文学性和艺术性
6. 自我润色，确保语言流畅、结构完整

请用中文撰写，字数在1000-2000字左右，创作高质量的小说内容。"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"故事大纲：\n{state['outline']}\n\n请根据以上大纲创作小说内容。")
            ]
        else:
            # 根据评论家的反馈修改
            system_prompt = """你是一位才华横溢的小说作家兼编辑。你需要根据评论家的反馈修改你的作品。

修改要求：
1. 仔细阅读评论家的反馈意见
2. 针对指出的问题进行改进
3. 保持故事的核心内容和风格
4. 提升文学性和可读性
5. 确保修改后的版本更加完善

请用中文回复，提供改进后的完整小说内容。"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"故事大纲：\n{state['outline']}\n\n"),
                HumanMessage(content=f"当前版本：\n{state['draft']}\n\n"),
                HumanMessage(content=f"评论家的反馈（第{revision_count}次）：\n{state['feedback']}\n\n请根据以上反馈修改小说。")
            ]

        response = self.llm.invoke(messages)

        feedback_history = state.get("all_feedbacks", "")

        return {
            **state,
            "draft": response.content,
            "current_step": "writer",
            "messages": [
                HumanMessage(content=f"[作家] {'正在撰写小说内容' if revision_count == 0 else f'正在根据反馈进行第{revision_count}次修改'}..."),
                AIMessage(content=response.content)
            ]
        }

    def _critic_agent(self, state: NovelState) -> NovelState:
        """评论家智能体 - 评估质量并判断是否通过"""
        revision_count = state.get("revision_count", 0)

        system_prompt = """你是一位严格但公正的文学评论家。你的任务是：
1. 评估小说的整体质量
2. 分析故事结构、人物塑造、情节发展、语言表达
3. 指出优点和需要改进的地方
4. 给出总体评分（1-10分）
5. 明确说明是否通过审核

评分标准：
- 8-10分：优秀，通过审核
- 6-7分：良好，可以通过
- 4-5分：一般，需要改进
- 1-3分：较差，必须修改

请在评论的最后一行明确写出：
- 如果通过：【审核结果：通过】
- 如果不通过：【审核结果：不通过】

请用中文回复，提供专业的文学评论。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"小说内容（第{revision_count + 1}版）：\n{state['draft']}\n\n请对这篇小说进行专业评论并给出审核结果。")
        ]

        response = self.llm.invoke(messages)
        feedback = response.content

        # 判断是否通过 - 检查评论中的关键词和评分
        approved = False
        if "【审核结果：通过】" in feedback or "审核结果：通过" in feedback:
            approved = True
        elif "【审核结果：不通过】" in feedback or "审核结果：不通过" in feedback:
            approved = False
        else:
            # 如果没有明确说明，尝试从评分判断（7分及以上通过）
            score_match = re.search(r'评分[：:]\s*(\d+)', feedback)
            if score_match:
                score = int(score_match.group(1))
                approved = score >= 7
            else:
                # 默认看是否包含积极词汇
                approved = any(word in feedback for word in ["优秀", "通过", "很好", "出色"])

        # 累积所有反馈历史
        all_feedbacks = state.get("all_feedbacks", "")
        all_feedbacks += f"\n\n=== 第{revision_count + 1}次评审 ===\n{feedback}"

        new_revision_count = revision_count + 1

        return {
            **state,
            "feedback": feedback,
            "all_feedbacks": all_feedbacks,
            "current_step": "critic",
            "revision_count": new_revision_count,
            "approved": approved,
            "final_novel": state["draft"] if approved else state.get("final_novel", state["draft"]),
            "messages": [
                HumanMessage(content=f"[评论家] 正在评估作品质量（第{new_revision_count}次评审）..."),
                AIMessage(content=feedback)
            ]
        }

    def _should_continue(self, state: NovelState) -> Literal["writer", "end"]:
        """
        决定工作流下一步：继续修改或结束

        条件：
        1. 如果评论家批准，结束
        2. 如果修改次数达到5次，结束（使用最后一版）
        3. 否则，继续让作家修改
        """
        if state.get("approved", False):
            # 通过审核，结束
            return "end"

        if state.get("revision_count", 0) >= 5:
            # 达到最大修改次数，结束
            return "end"

        # 继续修改
        return "writer"

    def _create_workflow(self) -> StateGraph:
        """创建 LangGraph 工作流"""
        # 创建状态图
        workflow = StateGraph(NovelState)

        # 添加节点（各个智能体）
        workflow.add_node("planner", self._planner_agent)
        workflow.add_node("writer", self._writer_agent)
        workflow.add_node("critic", self._critic_agent)

        # 定义工作流
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "writer")
        workflow.add_edge("writer", "critic")

        # 添加条件边：根据评审结果决定是继续修改还是结束
        workflow.add_conditional_edges(
            "critic",
            self._should_continue,
            {
                "writer": "writer",  # 继续修改
                "end": END  # 结束工作流
            }
        )

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
            "feedback": "",
            "all_feedbacks": "",
            "final_novel": "",
            "current_step": "",
            "revision_count": 0,
            "approved": False
        }

        # 执行工作流
        result = self.workflow.invoke(initial_state)

        return {
            "topic": result["topic"],
            "outline": result["outline"],
            "draft": result["draft"],
            "final_novel": result["final_novel"],
            "feedback": result["feedback"],
            "all_feedbacks": result["all_feedbacks"],
            "revision_count": result["revision_count"],
            "approved": result["approved"]
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
            "feedback": "",
            "all_feedbacks": "",
            "final_novel": "",
            "current_step": "",
            "revision_count": 0,
            "approved": False
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
