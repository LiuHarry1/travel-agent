"""FAQ tool for travel-related questions."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..core.base_tool import BaseMCPTool, ToolExecutionResult


class FAQTool(BaseMCPTool):
    """FAQ tool that searches a travel FAQ knowledge base."""
    
    # FAQ database
    FAQ_DATABASE = {
        "visa": "大多数国家需要提前申请签证。建议在出发前至少2-4周申请。请查看目的地国家的大使馆网站了解具体要求。",
        "passport": "护照有效期通常需要至少6个月。请确保护照在旅行期间有效，并留有足够的有效期。",
        "insurance": "强烈建议购买旅行保险，包括医疗、行李丢失和行程取消保险。",
        "currency": "建议在出发前兑换一些当地货币，或在到达后使用ATM机取款。信用卡在大多数国家都可以使用。",
        "vaccination": "某些目的地可能需要疫苗接种证明。请咨询医生或查看目的地国家的健康要求。",
        "luggage": "请查看航空公司的行李限制。通常经济舱允许携带一件手提行李和一件托运行李。",
        "timezone": "旅行前请了解目的地的时区，以便调整行程和避免时差问题。",
    }
    
    def __init__(self):
        """Initialize FAQ tool."""
        super().__init__(
            name="faq",
            description="Search travel FAQ knowledge base for answers to common travel questions"
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for FAQ tool."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The travel-related question to search in FAQ knowledge base. If no answer is found, you should try the retriever tool next."
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute FAQ search.
        
        Args:
            arguments: Dictionary containing 'query' key with the search query
            
        Returns:
            ToolExecutionResult with FAQ answer
        """
        query = arguments.get("query", "").lower()
        
        # Simulate async processing delay
        await asyncio.sleep(0.5)
        
        # Simple keyword matching
        matched_key = None
        for key in self.FAQ_DATABASE.keys():
            if key in query:
                matched_key = key
                break
        
        if matched_key:
            answer = self.FAQ_DATABASE[matched_key]
            self.logger.info(f"Matched query '{query}' to key '{matched_key}'")
            return ToolExecutionResult(
                success=True,
                data={
                    "answer": answer,
                    "matched_key": matched_key,
                    "source": "travel_faq_database"
                },
                metadata={"matched_key": matched_key}
            )
        else:
            # No match found - return explicit "not found" result
            self.logger.info(f"No match for query '{query}', returning not found result")
            return ToolExecutionResult(
                success=True,
                data={
                    "answer": None,  # Explicitly None to indicate no answer found
                    "matched_key": None,
                    "found": False,  # Explicit flag
                    "message": "FAQ知识库中没有找到匹配的答案。",
                    "source": "travel_faq_database"
                }
            )

