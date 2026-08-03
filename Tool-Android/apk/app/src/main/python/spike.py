# 真机验证 spike：从 Python 侧调用 Java 的 LlmEngine（Chaquopy 桥接验证）。
# 用传入的用户语句做任务提取，验证成功后生产环境可把 task_reader/llm.py 的推理后端切到该 Java 引擎。

def bridge_test(sentence: str) -> str:
    from com.taskreader.app import LlmEngine

    initialized = LlmEngine.isInitialized()
    path = LlmEngine.getModelPath()
    prompt = (
        "你是任务提取助手。请从用户输入的中文句子中提取所有任务/计划，直接输出一个 JSON 数组，不要解释。"
        "输入：" + sentence
    )
    out = LlmEngine.generate(prompt, 256)
    return "initialized=%s path=%s output=%r" % (initialized, path, str(out))
