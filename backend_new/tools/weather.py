"""
天气查询工具示例
"""
import json
import logging

logger = logging.getLogger(__name__)

# 模拟天气数据
WEATHER_DATA = {
    "上海": {"weather": "晴天", "temperature": "28°C", "humidity": "65%"},
    "北京": {"weather": "多云", "temperature": "22°C", "humidity": "45%"},
    "广州": {"weather": "小雨", "temperature": "30°C", "humidity": "80%"},
    "深圳": {"weather": "晴天", "temperature": "32°C", "humidity": "70%"},
}


def query_weather(city: str) -> dict:
    """
    查询天气信息
    
    Args:
        city: 城市名称
        
    Returns:
        天气信息字典
    """
    logger.info(f"Querying weather for city: {city}")
    
    # 查找城市（支持部分匹配）
    matched_city = None
    for key in WEATHER_DATA.keys():
        if city in key or key in city:
            matched_city = key
            break
    
    if not matched_city:
        return {
            "city": city,
            "error": f"未找到城市 {city} 的天气信息",
            "available_cities": list(WEATHER_DATA.keys())
        }
    
    weather_info = WEATHER_DATA[matched_city].copy()
    weather_info["city"] = matched_city
    weather_info["query"] = city
    
    logger.info(f"Weather result: {json.dumps(weather_info, ensure_ascii=False)}")
    return weather_info


# OpenAI Function Schema
schema = {
    "description": "查询指定城市的天气信息，包括天气状况、温度和湿度",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "要查询天气的城市名称，例如：上海、北京、广州、深圳"
            }
        },
        "required": ["city"]
    }
}

