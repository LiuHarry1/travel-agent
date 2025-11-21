#!/usr/bin/env python3
"""Test OpenAI API with streaming."""
import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")
client = OpenAI(api_key=api_key)

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Count from 1 to 5"}],
    stream=True
)

print("Streaming response:")
for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # New line at the end



#!/usr/bin/env python3
"""Quick OpenAI API test."""
import os
from openai import OpenAI

# 设置你的 API key
api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

# 创建客户端
client = OpenAI(api_key=api_key)

# 发送请求
try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello! Just say 'API is working'."}],
        max_tokens=20
    )
    
    print("✅ Success!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Error: {e}")