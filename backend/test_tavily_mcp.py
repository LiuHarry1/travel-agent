#!/usr/bin/env python3
"""
Simple test script for tavily-mcp server.
Tests connection and tool calling.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.mcp_tools.client import MCPClient


async def test_tavily_mcp():
    """Test tavily-mcp server connection and tool calling."""
    print("=" * 60)
    print("Testing tavily-mcp Server")
    print("=" * 60)
    
    # Tavily MCP server configuration
    command = "npx"
    args = ["-y", "tavily-mcp@0.1.4"]
    env = {
        "TAVILY_API_KEY": "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",
        "TAVILY_MAX_RESULTS": "5"
    }
    
    print(f"\n1. Creating MCP client...")
    print(f"   Command: {command}")
    print(f"   Args: {args}")
    print(f"   Env: {list(env.keys())}")
    
    client = MCPClient(command=command, args=args, env=env)
    
    try:
        print(f"\n2. Initializing connection...")
        await client.initialize()
        print("   ✓ Connection established")
        
        print(f"\n3. Listing available tools...")
        tools = await client.list_tools()
        print(f"   Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool.get('description', 'No description')[:60]}")
        
        if not tools:
            print("   ⚠ No tools found!")
            return
        
        # Test the first tool (usually tavily_search)
        test_tool = tools[0]
        tool_name = test_tool['name']
        
        print(f"\n4. Testing tool: {tool_name}")
        
        # Prepare test arguments based on tool schema
        test_args = {}
        input_schema = test_tool.get('inputSchema', {})
        properties = input_schema.get('properties', {})
        
        # Set default test arguments
        if 'query' in properties:
            test_args['query'] = "What is the weather in Tokyo today?"
        if 'max_results' in properties:
            test_args['max_results'] = 3
        elif 'maxResults' in properties:
            test_args['maxResults'] = 3
        
        print(f"   Arguments: {json.dumps(test_args, indent=2)}")
        
        result = await client.call_tool(tool_name, test_args)
        
        print(f"\n5. Tool call result:")
        if isinstance(result, dict):
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result)
        
        print(f"\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n6. Closing connection...")
        await client.close()
        print("   ✓ Connection closed")


if __name__ == "__main__":
    print("Starting tavily-mcp test...\n")
    asyncio.run(test_tavily_mcp())

