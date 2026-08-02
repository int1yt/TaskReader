"""LLM 集成测试（可选）：Ollama 不可用或未拉模型时自动跳过。"""
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_reader.llm import OllamaClient
from task_reader.engine import TaskReader


def test_llm_parse():
    client = OllamaClient()
    if not client._check():
        print("跳过：Ollama 或模型不可用")
        return
    tasks = client.parse_tasks("下周五下午三点把评审材料交给王老师",
                               datetime.date(2026, 8, 2))
    assert isinstance(tasks, list)
    if tasks:
        first = tasks[0]
        assert "action" in first and "date" in first, first
    print("ok LLM 原始解析 →", tasks)


def test_llm_fallback():
    reader = TaskReader(ref="2026-08-02")
    # 规则层找不到动作的词（评审不在词典），应触发 LLM 兜底并融合
    ts = reader.parse_json("下周末把那个装修方案评审一下", use_llm=True)
    assert ts, ts
    t = ts[0]
    assert "评审" in t["action"], ts
    assert t["time"] == "2026-08-08", ts
    print("ok LLM 兜底融合 →", ts)


if __name__ == "__main__":
    test_llm_parse()
    test_llm_fallback()
    print("LLM 测试完成")
