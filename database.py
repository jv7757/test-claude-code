"""
数据库管理模块 - SQLite持久化存储
支持多部小说的会话管理
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os


class Database:
    """SQLite数据库管理类"""

    def __init__(self, db_path: str = "novels.db"):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
        return conn

    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 创建小说表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS novels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                overall_outline TEXT,
                chapter_outlines TEXT,  -- JSON格式存储章节大纲列表
                total_chapters INTEGER DEFAULT 0,
                completed_chapters INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'  -- active, completed, archived
            )
        """)

        # 创建章节表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                novel_id INTEGER NOT NULL,
                chapter_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                outline TEXT,
                content TEXT,
                status TEXT DEFAULT 'pending',  -- pending, writing, completed
                revision_count INTEGER DEFAULT 0,
                approved BOOLEAN DEFAULT 0,
                feedback TEXT,
                all_feedbacks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
                UNIQUE(novel_id, chapter_number)
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_novel_status
            ON novels(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chapter_novel
            ON chapters(novel_id, chapter_number)
        """)

        conn.commit()
        conn.close()

    # ==================== 小说相关操作 ====================

    def create_novel(self, title: str, topic: str, overall_outline: str = "",
                     chapter_outlines: List[Dict] = None, total_chapters: int = 0) -> int:
        """
        创建新小说

        Args:
            title: 小说标题
            topic: 小说主题
            overall_outline: 总体大纲
            chapter_outlines: 章节大纲列表
            total_chapters: 总章节数

        Returns:
            新创建小说的ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        chapter_outlines_json = json.dumps(chapter_outlines or [], ensure_ascii=False)

        cursor.execute("""
            INSERT INTO novels (title, topic, overall_outline, chapter_outlines, total_chapters)
            VALUES (?, ?, ?, ?, ?)
        """, (title, topic, overall_outline, chapter_outlines_json, total_chapters))

        novel_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return novel_id

    def get_novel(self, novel_id: int) -> Optional[Dict]:
        """
        获取小说信息

        Args:
            novel_id: 小说ID

        Returns:
            小说信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM novels WHERE id = ?
        """, (novel_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            novel = dict(row)
            # 解析JSON字段
            novel['chapter_outlines'] = json.loads(novel['chapter_outlines'])
            return novel
        return None

    def get_all_novels(self, status: str = None) -> List[Dict]:
        """
        获取所有小说列表

        Args:
            status: 筛选状态（active, completed, archived）

        Returns:
            小说列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM novels
                WHERE status = ?
                ORDER BY updated_at DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT * FROM novels
                ORDER BY updated_at DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        novels = []
        for row in rows:
            novel = dict(row)
            novel['chapter_outlines'] = json.loads(novel['chapter_outlines'])
            novels.append(novel)

        return novels

    def update_novel(self, novel_id: int, **kwargs):
        """
        更新小说信息

        Args:
            novel_id: 小说ID
            **kwargs: 要更新的字段
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 特殊处理JSON字段
        if 'chapter_outlines' in kwargs:
            kwargs['chapter_outlines'] = json.dumps(kwargs['chapter_outlines'], ensure_ascii=False)

        # 构建UPDATE语句
        fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(novel_id)

        cursor.execute(f"""
            UPDATE novels
            SET {fields}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, values)

        conn.commit()
        conn.close()

    def delete_novel(self, novel_id: int):
        """
        删除小说（级联删除所有章节）

        Args:
            novel_id: 小说ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM novels WHERE id = ?", (novel_id,))

        conn.commit()
        conn.close()

    def update_novel_progress(self, novel_id: int):
        """
        更新小说进度（完成章节数）

        Args:
            novel_id: 小说ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count
            FROM chapters
            WHERE novel_id = ? AND status = 'completed'
        """, (novel_id,))

        completed_count = cursor.fetchone()['count']

        cursor.execute("""
            UPDATE novels
            SET completed_chapters = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (completed_count, novel_id))

        conn.commit()
        conn.close()

    # ==================== 章节相关操作 ====================

    def create_or_update_chapter(self, novel_id: int, chapter_number: int,
                                  title: str, outline: str = "", content: str = "",
                                  status: str = "pending", revision_count: int = 0,
                                  approved: bool = False, feedback: str = "",
                                  all_feedbacks: str = "") -> int:
        """
        创建或更新章节

        Args:
            novel_id: 小说ID
            chapter_number: 章节号
            title: 章节标题
            outline: 章节大纲
            content: 章节内容
            status: 状态
            revision_count: 修改次数
            approved: 是否通过审核
            feedback: 最新反馈
            all_feedbacks: 所有反馈

        Returns:
            章节ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 检查章节是否存在
        cursor.execute("""
            SELECT id FROM chapters
            WHERE novel_id = ? AND chapter_number = ?
        """, (novel_id, chapter_number))

        existing = cursor.fetchone()

        if existing:
            # 更新现有章节
            cursor.execute("""
                UPDATE chapters
                SET title = ?, outline = ?, content = ?, status = ?,
                    revision_count = ?, approved = ?, feedback = ?,
                    all_feedbacks = ?, updated_at = CURRENT_TIMESTAMP
                WHERE novel_id = ? AND chapter_number = ?
            """, (title, outline, content, status, revision_count,
                  approved, feedback, all_feedbacks, novel_id, chapter_number))
            chapter_id = existing['id']
        else:
            # 创建新章节
            cursor.execute("""
                INSERT INTO chapters
                (novel_id, chapter_number, title, outline, content, status,
                 revision_count, approved, feedback, all_feedbacks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (novel_id, chapter_number, title, outline, content, status,
                  revision_count, approved, feedback, all_feedbacks))
            chapter_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # 更新小说进度
        self.update_novel_progress(novel_id)

        return chapter_id

    def get_chapter(self, novel_id: int, chapter_number: int) -> Optional[Dict]:
        """
        获取章节信息

        Args:
            novel_id: 小说ID
            chapter_number: 章节号

        Returns:
            章节信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM chapters
            WHERE novel_id = ? AND chapter_number = ?
        """, (novel_id, chapter_number))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_all_chapters(self, novel_id: int) -> List[Dict]:
        """
        获取小说的所有章节

        Args:
            novel_id: 小说ID

        Returns:
            章节列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM chapters
            WHERE novel_id = ?
            ORDER BY chapter_number
        """, (novel_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_completed_chapters(self, novel_id: int) -> Dict[int, Dict]:
        """
        获取已完成的章节（用于知识库）

        Args:
            novel_id: 小说ID

        Returns:
            章节字典，key为章节号
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM chapters
            WHERE novel_id = ? AND status = 'completed'
            ORDER BY chapter_number
        """, (novel_id,))

        rows = cursor.fetchall()
        conn.close()

        chapters = {}
        for row in rows:
            chapter = dict(row)
            chapters[chapter['chapter_number']] = chapter

        return chapters

    def delete_chapter(self, novel_id: int, chapter_number: int):
        """
        删除章节

        Args:
            novel_id: 小说ID
            chapter_number: 章节号
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM chapters
            WHERE novel_id = ? AND chapter_number = ?
        """, (novel_id, chapter_number))

        conn.commit()
        conn.close()

        # 更新小说进度
        self.update_novel_progress(novel_id)

    # ==================== 统计相关操作 ====================

    def get_statistics(self) -> Dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 总小说数
        cursor.execute("SELECT COUNT(*) as count FROM novels")
        total_novels = cursor.fetchone()['count']

        # 活跃小说数
        cursor.execute("SELECT COUNT(*) as count FROM novels WHERE status = 'active'")
        active_novels = cursor.fetchone()['count']

        # 已完成小说数
        cursor.execute("SELECT COUNT(*) as count FROM novels WHERE status = 'completed'")
        completed_novels = cursor.fetchone()['count']

        # 总章节数
        cursor.execute("SELECT COUNT(*) as count FROM chapters")
        total_chapters = cursor.fetchone()['count']

        # 已完成章节数
        cursor.execute("SELECT COUNT(*) as count FROM chapters WHERE status = 'completed'")
        completed_chapters = cursor.fetchone()['count']

        conn.close()

        return {
            'total_novels': total_novels,
            'active_novels': active_novels,
            'completed_novels': completed_novels,
            'total_chapters': total_chapters,
            'completed_chapters': completed_chapters
        }


# 创建全局数据库实例
db = Database()
