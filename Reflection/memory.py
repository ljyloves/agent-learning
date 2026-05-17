from typing import Dict, Any, List, Optional

class Memory:
    """
    内存类，用于存储和管理Agent的记忆信息。
    """
    def __init__ (self):
        self.record: List[Dict[str, Any]] = []

    def add_record(self, record_type: str, content: str):
        """添加一条新的记忆记录。"""
        record = {"type": record_type, "content": content}
        self.record.append(record)
        print(f"🧠 记忆更新, 新增一条: {record_type} - {content}")

    def get_trajectory(self) -> str:
        """获取当前的记忆轨迹。"""
        trajectory_parts = []
        for record in self.record:
            if record["type"] == "excution":
                trajectory_parts.append(f"--- 上一轮尝试 (代码) ---\n{record['content']}")
            elif record["type"] == "reflection":
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")
        return "\n\n".join(trajectory_parts)
    
    def get_last_execution(self) -> Optional[str]:
        """获取最后一次执行的代码。"""
        for record in reversed(self.record):
            if record["type"] == "execution":
                return record["content"]
        return None