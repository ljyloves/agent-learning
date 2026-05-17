import requests
import os
from tavily import TavilyClient
from geopy.geocoders import Nominatim


def get_weather(city: str) -> str:
    """
    1. 将城市名转换为经纬度
    2. 使用 Open-Meteo API 查询实时天气
    """
    try:
        # --- 第一步：地理编码 (City -> Lat, Lon) ---
        # user_agent 是必填项，可以随便起个名字
        geolocator = Nominatim(user_agent="my_travel_agent")
        location = geolocator.geocode(city)

        if not location:
            return f"错误：无法找到城市 '{city}' 的地理坐标。"

        lat, lon = location.latitude, location.longitude

        # --- 第二步：查询 Open-Meteo API ---
        # current_weather=true 表示获取当前实时天气
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # 提取当前天气数据
        current = data["current_weather"]
        temp_c = current["temperature"]
        windspeed = current["windspeed"]
        # Open-Meteo 返回的是 weathercode，我们可以简单映射一下
        weather_code = current["weathercode"]

        # 简易天气代码映射 (可以根据需要扩充)
        weather_map = {
            0: "晴朗",
            1: "晴间多云",
            2: "多云",
            3: "阴天",
            45: "雾",
            61: "小雨",
        }
        weather_desc = weather_map.get(weather_code, "多云/阴")

        return f"{city} (经纬度: {lat:.2f}, {lon:.2f}) 当前天气：{weather_desc}，气温 {temp_c}摄氏度，风速 {windspeed}km/h"

    except Exception as e:
        return f"查询过程中出错: {str(e)}"


def get_attraction(city: str, weather: str) -> str:
    """
    根据城市和天气，使用Tavily Search API搜索并返回优化后的景点推荐。
    """
    # 1. 从环境变量中读取API密钥
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "错误:未配置TAVILY_API_KEY环境变量。"

    # 2. 初始化Tavily客户端
    tavily = TavilyClient(api_key=api_key)

    # 3. 构造一个精确的查询
    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐及理由"

    try:
        # 4. 调用API，include_answer=True会返回一个综合性的回答
        response = tavily.search(query=query, search_depth="basic", include_answer=True)

        # 5. Tavily返回的结果已经非常干净，可以直接使用
        # response['answer'] 是一个基于所有搜索结果的总结性回答
        if response.get("answer"):
            return response["answer"]

        # 如果没有综合性回答，则格式化原始结果
        formatted_results = []
        for result in response.get("results", []):
            formatted_results.append(f"- {result['title']}: {result['content']}")

        if not formatted_results:
            return "抱歉，没有找到相关的旅游景点推荐。"

        return "根据搜索，为您找到以下信息:\n" + "\n".join(formatted_results)

    except Exception as e:
        return f"错误:执行Tavily搜索时出现问题 - {e}"


# 将所有工具函数放入一个字典，方便后续调用
available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
}
