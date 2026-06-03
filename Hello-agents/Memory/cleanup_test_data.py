from dotenv import load_dotenv

load_dotenv()

from hello_agents.tools import MemoryTool, RAGTool
import shutil
import os

# 所有测试脚本中使用过的 user_id
USER_IDS = [
    "demo_user",
    "user123",
    "architecture_demo_user",
    "selective_user",
    "working_memory_demo",
]

# RAGTool 使用的知识库目录
RAG_KB_DIRS = [
    "./demo_rag_kb",
    "./advanced_search_kb",
]

print("清理 MemoryTool 数据...")
for uid in USER_IDS:
    try:
        mt = MemoryTool(user_id=uid)
        mt.run({"action": "clear_all"})
        print(f"  [OK] user_id='{uid}' 已清理")
    except Exception as e:
        print(f"  [SKIP] user_id='{uid}': {e}")

print("\n清理 RAGTool 知识库目录...")
base = os.path.dirname(os.path.realpath(__file__))
for d in RAG_KB_DIRS:
    target = os.path.join(base, d)
    if os.path.exists(target):
        shutil.rmtree(target)
        print(f"  [OK] 已删除: {target}")
    else:
        print(f"  [SKIP] 不存在: {target}")

print("\n清理完成。")
