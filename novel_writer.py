"""
多智能体小说创作系统 - 使用 LangGraph 实现
支持多章节创作，已完成章节作为知识库参考
包含三个智能体：策划者、作家、评论家
"""

from typing import TypedDict, Annotated, Sequence, Literal, List, Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
import operator
import os
import re
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 定义章节类型
class Chapter(TypedDict):
    """章节信息"""
    chapter_number: int
    title: str
    outline: str  # 章节大纲
    content: str  # 章节内容
    status: str  # pending, writing, reviewing, completed
    revision_count: int
    approved: bool
    feedback: str
    all_feedbacks: str


# 定义状态类型
class NovelState(TypedDict):
    """小说创作的状态"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    topic: str
    overall_outline: str  # 总体大纲
    chapter_outlines: List[Dict]  # 各章节大纲列表 [{"number": 1, "title": "xxx", "summary": "xxx"}]
    chapters: Dict[int, Chapter]  # 已完成的章节，key为章节号
    current_chapter_num: int  # 当前正在创作的章节号
    total_chapters: int  # 总章节数
    draft: str  # 当前章节的草稿
    feedback: str
    all_feedbacks: str
    current_step: str
    revision_count: int
    approved: bool


class NovelWritingAgents:
    """多智能体小说创作系统 - 支持多章节创作"""

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
        """策划者智能体 - 创建多章节故事大纲"""
        system_prompt = """你是一位经验丰富的小说策划专家。你的任务是创建一个详细的多章节小说大纲。

请按照以下格式创建大纲：

1. 总体概述
2. 主要人物设定
3. 核心冲突和主题
4. 章节规划（每章包含标题和内容概要）

章节规划格式示例：
【第1章：标题】
概要：本章的主要内容和情节发展...

【第2章：标题】
概要：本章的主要内容和情节发展...

请规划5-8个章节，每章概要100-200字。
请用中文回复，创建一个结构清晰、引人入胜的多章节大纲。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"小说主题：{state['topic']}\n\n请创建详细的多章节故事大纲。")
        ]

        response = self.llm.invoke(messages)
        outline = response.content

        # 解析章节大纲
        chapter_outlines = self._parse_chapter_outlines(outline)
        total_chapters = len(chapter_outlines)

        return {
            **state,
            "overall_outline": outline,
            "chapter_outlines": chapter_outlines,
            "total_chapters": total_chapters,
            "current_chapter_num": 1,
            "chapters": {},
            "current_step": "planner",
            "messages": [
                HumanMessage(content=f"[策划者] 正在创建多章节故事大纲..."),
                AIMessage(content=f"已创建包含{total_chapters}个章节的详细大纲\n\n{outline}")
            ]
        }

    def _parse_chapter_outlines(self, outline: str) -> List[Dict]:
        """解析大纲中的章节信息"""
        chapter_outlines = []

        # 使用正则表达式匹配章节
        pattern = r'【第(\d+)章[：:](.*?)】\s*\n概要[：:](.*?)(?=【第\d+章|$)'
        matches = re.findall(pattern, outline, re.DOTALL)

        for match in matches:
            chapter_num = int(match[0])
            title = match[1].strip()
            summary = match[2].strip()

            chapter_outlines.append({
                "number": chapter_num,
                "title": title,
                "summary": summary
            })

        # 如果正则匹配失败，尝试简单分割
        if not chapter_outlines:
            lines = outline.split('\n')
            chapter_num = 0
            for line in lines:
                if '第' in line and '章' in line and ('：' in line or ':' in line):
                    chapter_num += 1
                    title = line.split('：')[-1].split(':')[-1].strip('】【 ')
                    chapter_outlines.append({
                        "number": chapter_num,
                        "title": title,
                        "summary": "根据总体大纲创作"
                    })

        # 如果还是没有，创建默认章节
        if not chapter_outlines:
            for i in range(1, 6):  # 默认5章
                chapter_outlines.append({
                    "number": i,
                    "title": f"第{i}章",
                    "summary": "根据总体大纲创作"
                })

        return chapter_outlines

    def _get_previous_chapters_context(self, state: NovelState) -> str:
        """获取已完成章节作为上下文知识库"""
        current_num = state.get("current_chapter_num", 1)
        chapters = state.get("chapters", {})

        if not chapters or current_num == 1:
            return ""

        context = "\n\n=== 已完成章节（知识库参考）===\n"
        for i in range(1, current_num):
            if i in chapters:
                ch = chapters[i]
                context += f"\n【第{i}章：{ch['title']}】\n"
                context += f"{ch['content'][:500]}...\n"  # 只取前500字作为参考

        return context

    def _writer_agent(self, state: NovelState) -> NovelState:
        """作家智能体 - 撰写章节内容，参考已有章节知识库"""
        current_num = state.get("current_chapter_num", 1)
        revision_count = state.get("revision_count", 0)
        chapter_outlines = state.get("chapter_outlines", [])

        # 获取当前章节大纲
        current_outline = next((ch for ch in chapter_outlines if ch["number"] == current_num), None)
        if not current_outline:
            current_outline = {"number": current_num, "title": f"第{current_num}章", "summary": ""}

        # 获取已完成章节作为知识库
        previous_context = self._get_previous_chapters_context(state)

        if revision_count == 0:
            # 首次创作当前章节
            system_prompt = """你是一位才华横溢的小说作家兼编辑。你正在创作一部多章节小说。

创作要求：
1. 根据总体大纲和当前章节概要创作内容
2. 如果有已完成章节，请保持故事连贯性和一致性
3. 运用生动的描写和对话
4. 字数控制在800-1500字
5. 注意文学性和可读性
6. 确保与前面章节的人物、情节、风格保持一致

请用中文创作高质量的章节内容。"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"总体大纲：\n{state['overall_outline']}\n"),
                HumanMessage(content=f"当前章节：第{current_num}章 - {current_outline['title']}\n章节概要：{current_outline['summary']}\n"),
            ]

            if previous_context:
                messages.append(HumanMessage(content=previous_context))

            messages.append(HumanMessage(content=f"\n请创作第{current_num}章的内容。"))

        else:
            # 根据评论家反馈修改
            system_prompt = """你是一位才华横溢的小说作家兼编辑。你需要根据评论家的反馈修改章节内容。

修改要求：
1. 仔细阅读评论家的反馈意见
2. 针对指出的问题进行改进
3. 保持与其他章节的连贯性
4. 提升文学性和可读性
5. 确保修改后的版本更加完善

请用中文回复，提供改进后的完整章节内容。"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"章节信息：第{current_num}章 - {current_outline['title']}\n"),
                HumanMessage(content=f"当前版本：\n{state['draft']}\n\n"),
                HumanMessage(content=f"评论家的反馈（第{revision_count}次）：\n{state['feedback']}\n\n请根据以上反馈修改章节。")
            ]

        response = self.llm.invoke(messages)

        return {
            **state,
            "draft": response.content,
            "current_step": "writer",
            "messages": [
                HumanMessage(content=f"[作家] {'正在创作' if revision_count == 0 else f'正在修改'}第{current_num}章..."),
                AIMessage(content=response.content)
            ]
        }

    def _critic_agent(self, state: NovelState) -> NovelState:
        """评论家智能体 - 评估章节质量并判断是否通过"""
        current_num = state.get("current_chapter_num", 1)
        revision_count = state.get("revision_count", 0)
        chapter_outlines = state.get("chapter_outlines", [])
        current_outline = next((ch for ch in chapter_outlines if ch["number"] == current_num), {})

        system_prompt = """你是一位严格但公正的文学评论家。你正在评审一部多章节小说的某一章。

评审要点：
1. 评估章节的整体质量
2. 检查与前面章节的连贯性（如适用）
3. 分析人物塑造、情节发展、语言表达
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
            HumanMessage(content=f"章节内容（第{current_num}章，第{revision_count + 1}版）：\n{state['draft']}\n\n请对这一章进行专业评论并给出审核结果。")
        ]

        response = self.llm.invoke(messages)
        feedback = response.content

        # 判断是否通过
        approved = False
        if "【审核结果：通过】" in feedback or "审核结果：通过" in feedback:
            approved = True
        elif "【审核结果：不通过】" in feedback or "审核结果：不通过" in feedback:
            approved = False
        else:
            score_match = re.search(r'评分[：:]\s*(\d+)', feedback)
            if score_match:
                score = int(score_match.group(1))
                approved = score >= 7
            else:
                approved = any(word in feedback for word in ["优秀", "通过", "很好", "出色"])

        # 累积反馈历史
        all_feedbacks = state.get("all_feedbacks", "")
        all_feedbacks += f"\n\n=== 第{current_num}章 第{revision_count + 1}次评审 ===\n{feedback}"

        new_revision_count = revision_count + 1

        return {
            **state,
            "feedback": feedback,
            "all_feedbacks": all_feedbacks,
            "current_step": "critic",
            "revision_count": new_revision_count,
            "approved": approved,
            "messages": [
                HumanMessage(content=f"[评论家] 正在评估第{current_num}章（第{new_revision_count}次评审）..."),
                AIMessage(content=feedback)
            ]
        }

    def _should_continue(self, state: NovelState) -> Literal["writer", "end"]:
        """决定工作流下一步：继续修改或结束当前章节"""
        if state.get("approved", False):
            return "end"

        if state.get("revision_count", 0) >= 5:
            return "end"

        return "writer"

    def _create_workflow(self) -> StateGraph:
        """创建 LangGraph 工作流"""
        workflow = StateGraph(NovelState)

        workflow.add_node("planner", self._planner_agent)
        workflow.add_node("writer", self._writer_agent)
        workflow.add_node("critic", self._critic_agent)

        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "writer")
        workflow.add_edge("writer", "critic")

        workflow.add_conditional_edges(
            "critic",
            self._should_continue,
            {
                "writer": "writer",
                "end": END
            }
        )

        return workflow.compile()

    def create_chapter(self, topic: str, chapter_num: int = 1, previous_chapters: Dict[int, Chapter] = None) -> dict:
        """
        创作单个章节

        Args:
            topic: 小说主题（首次调用时使用）
            chapter_num: 要创作的章节号
            previous_chapters: 已完成的章节（作为知识库）

        Returns:
            章节创作结果
        """
        # 初始化状态
        initial_state = {
            "messages": [],
            "topic": topic,
            "overall_outline": "",
            "chapter_outlines": [],
            "chapters": previous_chapters or {},
            "current_chapter_num": chapter_num,
            "total_chapters": 0,
            "draft": "",
            "feedback": "",
            "all_feedbacks": "",
            "current_step": "",
            "revision_count": 0,
            "approved": False
        }

        # 执行工作流
        result = self.workflow.invoke(initial_state)

        return result

    def get_chapter_list(self, state: dict) -> List[Dict]:
        """获取章节列表信息"""
        chapter_outlines = state.get("chapter_outlines", [])
        chapters = state.get("chapters", {})

        chapter_list = []
        for outline in chapter_outlines:
            num = outline["number"]
            chapter_info = {
                "number": num,
                "title": outline["title"],
                "status": "completed" if num in chapters and chapters[num].get("approved") else "pending"
            }
            chapter_list.append(chapter_info)

        return chapter_list


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
