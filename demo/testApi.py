# 测试天气 API
import requests

# 测试 Tavily API
from tavily import TavilyClient

response = requests.get("https://wttr.in/Beijing?format=j1")
print("天气API状态:", response.status_code)


tavily = TavilyClient(
    api_key="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"
)
try:
    result = tavily.search("test", search_depth="basic")
    print("Tavily API 连接成功")
except Exception as e:
    print("Tavily API 错误:", e)
