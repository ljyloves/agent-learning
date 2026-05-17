import os
from serpapi import SerpApiClient

def search(query: str) -> str:
    print(f"🔍 正在使用 SerpAPI 搜索: {query}")
    try:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise ValueError("SERPAPI_API_KEY 环境变量未设置。请在 .env 文件中定义它。")
        prams = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "gl": "cn",
            "hl": "zh-CN",
        }

        client = SerpApiClient(prams)
        results = client.get_dict()

        if "answer_box_list" in results:
            return "\n".join(results["answer_box_list"])
        if "answer_box" in results and "answer" in results["answer_box"]:
            return results["answer_box"]["answer"]
        if "knowledge_graph" in results and "description" in results["knowledge_graph"]:
            return results["knowledge_graph"]["description"]
        if "organic_results" in results and results["organic_results"]:
            snippets = [
                f"[{i + 1}] {res.get('title', '')}\n{res.get('snippet', '')}"
                for i, res in enumerate(results["organic_results"][:3])
            ]
            return "\n\n".join(snippets)
        return f"没有找到关于'{query}'的信息"

    except Exception as e:
        print(f"❌ 搜索时发生错误: {e}")
        return f"搜索时发生错误: {e}"
    
def safe_calculator(expression: str) -> str:
    """
    一个安全的计算器函数，仅允许基本的数学表达式。
    :param expression: 要计算的数学表达式
    :return: 计算结果或错误信息
    """
    print(f"🧮 正在计算表达式: {expression}")
    try:
        # 仅允许数字、运算符和括号
        if not all(c in "0123456789+-*/(). " for c in expression):
            raise ValueError("表达式包含非法字符。仅允许数字、运算符和括号。")
        result = eval(expression)
        return str(result)
    except Exception as e:
        print(f"❌ 计算时发生错误: {e}")
        return f"计算时发生错误: {e}"
