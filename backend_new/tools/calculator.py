"""
计算器工具示例
"""
import logging

logger = logging.getLogger(__name__)


def calculate(expression: str) -> dict:
    """
    计算数学表达式
    
    Args:
        expression: 数学表达式，例如: "2 + 3 * 4"
        
    Returns:
        计算结果字典
    """
    logger.info(f"Calculating expression: {expression}")
    
    try:
        # 安全评估数学表达式（仅支持基本数学运算）
        # 在生产环境中应该使用更安全的解析方式
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            raise ValueError("表达式包含不允许的字符")
        
        result = eval(expression)
        
        logger.info(f"Calculation result: {expression} = {result}")
        return {
            "expression": expression,
            "result": result,
            "success": True
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Calculation error: {error_msg}")
        return {
            "expression": expression,
            "error": error_msg,
            "success": False
        }


# OpenAI Function Schema
schema = {
    "description": "计算数学表达式，支持基本数学运算（加、减、乘、除、括号）",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "要计算的数学表达式，例如: '2 + 3 * 4' 或 '(10 + 5) / 3'"
            }
        },
        "required": ["expression"]
    }
}

