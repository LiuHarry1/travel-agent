"""Retriever tool for document search (简化版)"""
from __future__ import annotations

from typing import Any, Dict

from .base_tool import BaseTool, ToolExecutionResult


class RetrieverTool(BaseTool):
    """文档检索工具 - 搜索向量化知识库"""
    
    # 模拟知识库
    KNOWLEDGE_BASE = [
        {
            "id": "doc1",
            "title": "日本旅游指南",
            "content": "日本是一个充满文化和历史的美丽国家。最佳旅行时间是春季（3-5月）和秋季（9-11月）。主要城市包括东京、大阪、京都。日本签证申请需要准备护照、照片、申请表、行程单等材料，通常需要5-7个工作日。",
            "category": "destination_guide"
        },
        {
            "id": "doc2",
            "title": "欧洲旅行注意事项",
            "content": "欧洲旅行需要申根签证（如果适用）。建议提前预订酒店和交通。主要语言包括英语、法语、德语等。",
            "category": "travel_tips"
        },
        {
            "id": "doc3",
            "title": "东南亚背包客指南",
            "content": "东南亚是预算旅行者的理想目的地。主要国家包括泰国、越南、柬埔寨。建议携带现金和信用卡。",
            "category": "budget_travel"
        },
    ]
    
    def __init__(self):
        super().__init__(
            name="retriever",
            description="搜索向量化知识库，查找旅行相关的文档和指南。用于查找FAQ中没有的详细信息。"
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜索的查询内容，使用中文。"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的结果数量，默认3",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """执行文档检索"""
        query = arguments.get("query", "").strip()
        top_k = arguments.get("top_k", 3)
        
        if not query:
            return ToolExecutionResult(
                success=False,
                data=None,
                error="查询参数是必需的"
            )
        
        # 简单的关键词匹配
        query_lower = query.lower()
        results = []
        
        for doc in self.KNOWLEDGE_BASE:
            content_lower = doc["content"].lower()
            title_lower = doc["title"].lower()
            
            # 计算匹配分数
            score = 0.0
            if query_lower in content_lower:
                score = 0.8
            elif query_lower in title_lower:
                score = 0.6
            else:
                # 计算共同字符数
                query_chars = set(c for c in query_lower if '\u4e00' <= c <= '\u9fff')
                content_chars = set(c for c in content_lower if '\u4e00' <= c <= '\u9fff')
                if query_chars:
                    overlap = len(query_chars.intersection(content_chars))
                    score = overlap / len(query_chars) * 0.5
            
            if score > 0.2:
                results.append({
                    "title": doc["title"],
                    "content": doc["content"],
                    "category": doc["category"],
                    "score": score
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]
        
        if results:
            return ToolExecutionResult(
                success=True,
                data={
                    "results": results,
                    "total_found": len(results),
                    "query": query
                }
            )
        else:
            return ToolExecutionResult(
                success=True,
                data={
                    "results": [],
                    "total_found": 0,
                    "query": query,
                    "message": "未找到相关文档。"
                }
            )

