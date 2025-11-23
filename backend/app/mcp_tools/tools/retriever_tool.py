"""Retriever tool for vectorized knowledge database search."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..core.base_tool import BaseMCPTool, ToolExecutionResult


class RetrieverTool(BaseMCPTool):
    """Retriever tool that searches a vectorized knowledge database."""
    
    # Mock knowledge database (simulating vectorized documents)
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
        {
            "id": "doc4",
            "title": "商务旅行最佳实践",
            "content": "商务旅行需要提前规划。建议预订靠近会议地点的酒店。保持所有收据以便报销。",
            "category": "business_travel"
        },
        {
            "id": "doc5",
            "title": "家庭旅行规划",
            "content": "家庭旅行需要考虑孩子的需求。选择适合家庭的住宿和活动。提前准备必要的文件和药物。",
            "category": "family_travel"
        },
    ]
    
    def __init__(self):
        """Initialize Retriever tool."""
        super().__init__(
            name="retriever",
            description="Retrieve relevant information from vectorized knowledge database containing travel documents, guides, and resources"
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for Retriever tool."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to retrieve relevant travel information from vectorized knowledge database. Use this tool when FAQ tool doesn't find an answer. If this tool also doesn't find useful information, suggest the user contact Harry."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute knowledge base retrieval.
        
        Args:
            arguments: Dictionary containing 'query' and optionally 'max_results'
            
        Returns:
            ToolExecutionResult with retrieved documents
        """
        query = arguments.get("query", "").lower()
        max_results = arguments.get("max_results", 5)
        
        # Simulate async processing delay (vector search)
        await asyncio.sleep(0.8)
        
        # Simple keyword matching (simulating vector similarity search)
        query_keywords = set(query.split())
        scored_docs = []
        
        for doc in self.KNOWLEDGE_BASE:
            doc_text = (doc["title"] + " " + doc["content"]).lower()
            doc_keywords = set(doc_text.split())
            
            # Simple scoring: count matching keywords
            score = len(query_keywords.intersection(doc_keywords))
            
            if score > 0:
                scored_docs.append((score, doc))
        
        # Sort by score (descending) and take top results
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        results = [doc for _, doc in scored_docs[:max_results]]
        
        self.logger.info(f"Found {len(results)} results for query '{query}'")
        
        return ToolExecutionResult(
            success=True,
            data={
                "query": query,
                "results": results,
                "total_found": len(results),
                "source": "vectorized_knowledge_database"
            },
            metadata={"total_found": len(results)}
        )

