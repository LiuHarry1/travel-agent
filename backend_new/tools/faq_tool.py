"""FAQ tool for travel-related questions (简化版)"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict

from .base_tool import BaseTool, ToolExecutionResult


class FAQTool(BaseTool):
    """FAQ 工具 - 搜索旅行常见问题知识库"""
    
    def __init__(self):
        # 尝试从 backend 项目复制数据文件
        backend_data_path = Path(__file__).parent.parent.parent / "backend" / "app" / "mcp_tools" / "data" / "travel-faq.csv"
        csv_path = backend_data_path if backend_data_path.exists() else None
        
        super().__init__(
            name="faq",
            description="搜索旅行常见问题知识库，查找常见旅行问题的答案。重要：查询必须使用中文。"
        )
        
        self.csv_path = csv_path
        self.faq_database = []
        self._load_faq_database()
    
    def _load_faq_database(self):
        """加载 FAQ 数据库"""
        if not self.csv_path or not self.csv_path.exists():
            # 使用默认数据
            self.faq_database = [
                ("日本签证需要什么材料？", "日本签证需要护照、照片、申请表、行程单、酒店预订证明等材料，通常需要5-7个工作日。"),
                ("去欧洲旅行需要什么签证？", "去欧洲旅行通常需要申根签证，需要准备护照、照片、申请表、行程单、酒店预订、保险等材料。"),
                ("东南亚旅行最佳时间？", "东南亚旅行最佳时间是11月到次年3月，天气较为凉爽干燥。"),
            ]
            return
        
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    question = row.get("问题", "").strip()
                    answer = row.get("答案", "").strip()
                    if question and answer:
                        self.faq_database.append((question, answer))
        except Exception as e:
            print(f"Error loading FAQ: {e}")
            # 使用默认数据
            self.faq_database = [
                ("日本签证需要什么材料？", "日本签证需要护照、照片、申请表、行程单、酒店预订证明等材料，通常需要5-7个工作日。"),
            ]
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜索的旅行相关问题，必须使用中文。如果找不到答案，应该尝试使用 retriever 工具。"
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """执行 FAQ 搜索"""
        query = arguments.get("query", "").strip()
        
        if not query:
            return ToolExecutionResult(
                success=False,
                data=None,
                error="查询参数是必需的"
            )
        
        # 简单的关键词匹配
        query_lower = query.lower()
        best_match = None
        best_score = 0.0
        
        for question, answer in self.faq_database:
            question_lower = question.lower()
            # 计算匹配分数
            score = 0.0
            if query_lower in question_lower or question_lower in query_lower:
                score = 0.8
            else:
                # 计算共同字符数
                query_chars = set(c for c in query_lower if '\u4e00' <= c <= '\u9fff')
                question_chars = set(c for c in question_lower if '\u4e00' <= c <= '\u9fff')
                if query_chars:
                    overlap = len(query_chars.intersection(question_chars))
                    score = overlap / len(query_chars)
            
            if score > best_score:
                best_score = score
                best_match = (question, answer)
        
        if best_match and best_score >= 0.3:
            matched_question, answer = best_match
            return ToolExecutionResult(
                success=True,
                data={
                    "answer": answer,
                    "matched_question": matched_question,
                    "score": best_score,
                    "source": "travel_faq_database"
                }
            )
        else:
            return ToolExecutionResult(
                success=True,
                data={
                    "answer": None,
                    "found": False,
                    "message": "FAQ知识库中没有找到匹配的答案。",
                    "source": "travel_faq_database"
                }
            )

