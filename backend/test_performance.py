"""
Performance testing script for chat service.
Tests key performance bottlenecks.
"""
import sys
import time
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.service.chat import ChatService
from app.models import ChatRequest
from app.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_tool_detection():
    """Test tool detection performance."""
    print("\n" + "="*60)
    print("Test 1: Tool Detection Performance")
    print("="*60)
    
    service = ChatService()
    messages = [{"role": "user", "content": "今天上海的天气怎么样？"}]
    system_prompt = service._build_agent_system_prompt()
    functions = service.mcp_registry.get_tool_function_definitions_sync()
    
    print(f"Functions available: {len(functions)}")
    
    # Test tool detection
    start_time = time.time()
    result = service._detect_tool_calls(messages, system_prompt, functions)
    elapsed = time.time() - start_time
    
    print(f"\nTool detection took: {elapsed:.3f}s")
    if result:
        print(f"Content length: {len(result.get('content', '') or '')}")
        print(f"Tool calls: {len(result.get('tool_calls', []))}")
        if result.get('tool_calls'):
            tool_names = [service._extract_tool_name(tc) for tc in result['tool_calls']]
            print(f"Tools to call: {tool_names}")
    else:
        print("No result returned")
    
    return elapsed


def test_tool_execution():
    """Test tool execution performance."""
    print("\n" + "="*60)
    print("Test 2: Tool Execution Performance")
    print("="*60)
    
    service = ChatService()
    
    # Test FAQ tool
    print("\nTesting FAQ tool...")
    from app.mcp_tools import ToolCall
    import asyncio
    
    faq_call = ToolCall(
        name="faq",
        arguments={"query": "日本签证申请流程"},
        id="test_faq_1"
    )
    
    start_time = time.time()
    loop = service._ensure_event_loop()
    result = loop.run_until_complete(service.mcp_registry.call_tool(faq_call))
    elapsed = time.time() - start_time
    
    print(f"FAQ tool execution took: {elapsed:.3f}s")
    print(f"Success: {result.success}")
    if result.success:
        result_str = str(result.result)
        print(f"Result length: {len(result_str)} chars")
        print(f"Result preview: {result_str[:200]}...")
    
    return elapsed


def test_stream_response():
    """Test streaming response performance."""
    print("\n" + "="*60)
    print("Test 3: Streaming Response Performance")
    print("="*60)
    
    service = ChatService()
    messages = [{"role": "user", "content": "你好"}]
    system_prompt = service._build_agent_system_prompt()
    
    print("Testing stream with tools disabled...")
    start_time = time.time()
    first_chunk_time = None
    chunk_count = 0
    total_content = ""
    
    for chunk in service._stream_llm_response(messages, system_prompt, disable_tools=True):
        if first_chunk_time is None:
            first_chunk_time = time.time() - start_time
            print(f"First chunk (TTFB): {first_chunk_time:.3f}s")
        chunk_count += 1
        total_content += chunk
    
    elapsed = time.time() - start_time
    print(f"Total stream time: {elapsed:.3f}s")
    print(f"Chunks received: {chunk_count}")
    print(f"Total content length: {len(total_content)} chars")
    print(f"Content preview: {total_content[:200]}...")
    
    return elapsed, first_chunk_time


def test_full_chat_stream():
    """Test full chat stream performance."""
    print("\n" + "="*60)
    print("Test 4: Full Chat Stream Performance")
    print("="*60)
    
    service = ChatService()
    
    # Test case 1: Simple question (no tools needed)
    print("\nTest 4.1: Simple question (no tools)")
    request = ChatRequest(
        message="你好",
        messages=[]
    )
    
    start_time = time.time()
    first_chunk_time = None
    chunk_count = 0
    tool_call_count = 0
    
    for event in service.chat_stream(request):
        if first_chunk_time is None and event.get("type") == "chunk":
            first_chunk_time = time.time() - start_time
            print(f"First chunk (TTFB): {first_chunk_time:.3f}s")
        
        if event.get("type") == "chunk":
            chunk_count += 1
        elif event.get("type") in ("tool_call_start", "tool_call_end"):
            tool_call_count += 1
    
    elapsed = time.time() - start_time
    print(f"Total time: {elapsed:.3f}s")
    print(f"Chunks: {chunk_count}, Tool calls: {tool_call_count}")
    
    # Test case 2: Question requiring tool
    print("\nTest 4.2: Question requiring tool (FAQ)")
    request = ChatRequest(
        message="如何申请日本旅游签证？",
        messages=[]
    )
    
    start_time = time.time()
    first_chunk_time = None
    chunk_count = 0
    tool_call_count = 0
    
    for event in service.chat_stream(request):
        if first_chunk_time is None and event.get("type") == "chunk":
            first_chunk_time = time.time() - start_time
            print(f"First chunk (TTFB): {first_chunk_time:.3f}s")
        
        if event.get("type") == "chunk":
            chunk_count += 1
        elif event.get("type") == "tool_call_start":
            tool_call_count += 1
            print(f"  Tool call started: {event.get('tool')}")
        elif event.get("type") == "tool_call_end":
            print(f"  Tool call completed: {event.get('tool')}")
    
    elapsed = time.time() - start_time
    print(f"Total time: {elapsed:.3f}s")
    print(f"Chunks: {chunk_count}, Tool calls: {tool_call_count}")
    
    return elapsed, first_chunk_time


def test_function_definitions_loading():
    """Test function definitions loading performance."""
    print("\n" + "="*60)
    print("Test 5: Function Definitions Loading Performance")
    print("="*60)
    
    service = ChatService()
    
    # First load (cold start)
    start_time = time.time()
    functions1 = service.mcp_registry.get_tool_function_definitions_sync()
    first_load_time = time.time() - start_time
    print(f"First load (cold start): {first_load_time:.3f}s")
    print(f"Functions loaded: {len(functions1)}")
    
    # Second load (should be cached/faster)
    start_time = time.time()
    functions2 = service.mcp_registry.get_tool_function_definitions_sync()
    second_load_time = time.time() - start_time
    print(f"Second load (warm): {second_load_time:.3f}s")
    print(f"Functions loaded: {len(functions2)}")
    
    return first_load_time, second_load_time


def test_system_prompt_building():
    """Test system prompt building performance."""
    print("\n" + "="*60)
    print("Test 6: System Prompt Building Performance")
    print("="*60)
    
    service = ChatService()
    
    start_time = time.time()
    prompt = service._build_agent_system_prompt()
    elapsed = time.time() - start_time
    
    print(f"System prompt building took: {elapsed:.3f}s")
    print(f"Prompt length: {len(prompt)} chars")
    print(f"Prompt preview (first 200 chars): {prompt[:200]}...")
    
    return elapsed


def main():
    """Run all performance tests."""
    print("\n" + "="*60)
    print("Performance Testing Suite")
    print("="*60)
    
    results = {}
    
    try:
        # Test 1: Function definitions loading
        first_load, second_load = test_function_definitions_loading()
        results['function_definitions_first'] = first_load
        results['function_definitions_second'] = second_load
        
        # Test 2: System prompt building
        prompt_time = test_system_prompt_building()
        results['system_prompt'] = prompt_time
        
        # Test 3: Tool detection
        detection_time = test_tool_detection()
        results['tool_detection'] = detection_time
        
        # Test 4: Tool execution
        tool_exec_time = test_tool_execution()
        results['tool_execution'] = tool_exec_time
        
        # Test 5: Stream response
        stream_time, ttfb = test_stream_response()
        results['stream_response'] = stream_time
        results['stream_ttfb'] = ttfb
        
        # Test 6: Full chat stream
        chat_time, chat_ttfb = test_full_chat_stream()
        results['chat_stream'] = chat_time
        results['chat_ttfb'] = chat_ttfb
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Print summary
    print("\n" + "="*60)
    print("Performance Test Summary")
    print("="*60)
    print(f"{'Test':<40} {'Time (s)':>15}")
    print("-" * 60)
    for test_name, time_taken in sorted(results.items(), key=lambda x: x[1], reverse=True):
        print(f"{test_name:<40} {time_taken:>15.3f}")
    
    print("\n" + "="*60)
    print("Performance Analysis")
    print("="*60)
    
    # Identify bottlenecks
    total_time = sum(results.values())
    print(f"\nTotal test time: {total_time:.3f}s")
    
    # Find slowest operations
    slowest = max(results.items(), key=lambda x: x[1])
    print(f"\nSlowest operation: {slowest[0]} ({slowest[1]:.3f}s)")
    
    # Check for potential issues
    if results.get('tool_detection', 0) > 2.0:
        print("WARNING: Tool detection is slow (>2s)")
    
    if results.get('tool_execution', 0) > 1.0:
        print("WARNING: Tool execution is slow (>1s)")
    
    if results.get('stream_ttfb', 0) > 1.0:
        print("WARNING: Stream TTFB is slow (>1s)")
    
    if results.get('function_definitions_first', 0) > 1.0:
        print("WARNING: Function definitions loading is slow (>1s)")
        print("  -> This is the main bottleneck! MCP servers are being reinitialized every time.")
        print("  -> Solution: Cache MCP clients and reuse them across requests.")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()

