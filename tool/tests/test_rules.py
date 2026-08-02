"""规则通道核心测试（不依赖 LLM）。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_reader.engine import TaskReader

REF = "2026-08-02"  # 周日
reader = TaskReader(ref=REF)


def tasks(sentence):
    return reader.parse_json(sentence, use_llm=False)


def find(tasks, action=None, obj=None, time=None, place=None):
    for t in tasks:
        if action is not None and action not in t["action"]:
            continue
        if obj is not None and obj not in t["object"]:
            continue
        if time is not None and t["time"] != time:
            continue
        if place is not None and place not in t["place"]:
            continue
        return t
    return None


def test_example():
    t = find(tasks("我下周三要交论文"), action="交", time="2026-08-05")
    assert t, t
    assert "论文" in t["object"], t
    print("ok 示例：下周三交论文 →", t)


def test_datetime_place():
    t = find(tasks("明天下午三点去图书馆开会"), time="2026-08-03 15:00")
    assert t, t
    assert "图书馆" in t["place"], t
    assert "开会" in t["action"], t
    print("ok 日期+时刻+地点+动作 →", t)


def test_weekday_evening():
    t = find(tasks("我打算周五晚上八点和朋友在咖啡厅见面"),
             time="2026-08-07 20:00")
    assert t, t
    assert "咖啡厅" in t["place"], t
    print("ok 周五晚上8点 →", t)


def test_x_days_after():
    t = find(tasks("两周后交作业"), time="2026-08-16")
    assert t, t
    print("ok 两周后 →", t)


def test_deadline():
    t = find(tasks("记得下周一之前把报告发给我"), time="2026-08-03")
    assert t, t
    print("ok 下周一之前 →", t)


def test_month_end():
    t = find(tasks("这个月月底之前要体检"), time="2026-08-31")
    assert t, t
    print("ok 月底 →", t)


def test_absolute():
    t = find(tasks("2026年8月5日参加面试"), time="2026-08-05")
    assert t, t
    assert "面试" in t["action"], t
    print("ok 绝对日期 →", t)


def test_multi_task():
    ts = tasks("我下周三交论文，周五下午去图书馆开会")
    t1 = find(ts, action="交", time="2026-08-05")
    t2 = find(ts, time="2026-08-07 15:00")
    assert t1 and t2, ts
    print("ok 多任务分句 →", ts)


def test_no_verb():
    ts = tasks("下周三 交论文")
    assert ts, ts
    print("ok 简洁表达 →", ts)


def test_time_only():
    ts = tasks("下午三点开会")
    t = find(ts, time="2026-08-02 15:00")
    assert t, ts
    print("ok 仅时刻 →", t)


def test_ba_construction():
    ts = tasks("下周一记得帮我把打印机修好")
    t = find(ts, obj="打印机", time="2026-08-03")
    assert t, ts
    assert "修" in t["action"], ts
    print("ok 把字句 →", ts)


def test_return_book():
    ts = tasks("一起去图书馆把书还了")
    t = find(ts, obj="书")
    assert t, ts
    assert "还" in t["action"], ts
    assert "图书馆" in t["place"], ts
    print("ok 还书 →", ts)


def test_consecutive_multi():
    ts = tasks("周五晚上六点在学校门口集合，然后一起去图书馆把书还了，顺便去食堂吃饭")
    assert find(ts, action="集合", time="2026-08-07 18:00", place="学校"), ts
    assert find(ts, action="还", place="图书馆"), ts
    assert find(ts, action="吃饭", place="食堂"), ts
    print("ok 连续多任务 →", ts)


def test_fullwidth_punct():
    t = find(tasks("下周三　交论文"), action="交")
    assert t, t
    print("ok 全角空格 →", t)


def test_compact_morning():
    t = find(tasks("明早八点到校门口集合"), time="2026-08-03 08:00")
    assert t, t
    assert "校门口" in t["place"], t
    print("ok 明早 →", t)


def test_compact_night():
    t = find(tasks("今晚八点开会"), time="2026-08-02 20:00")
    assert t, t
    print("ok 今晚 →", t)


def test_bao_reference():
    ts = tasks("记得下周一之前把报告发给我")
    t = find(ts, action="发", obj="报告", time="2026-08-03")
    assert t, ts
    assert len(ts) == 1, ts
    print("ok 把报告发给我 →", ts)


def test_next_weekend():
    t = find(tasks("下周末把那个装修方案评审一下"), time="2026-08-08")
    assert t, t
    print("ok 下周末 →", t)


def test_structured_list():
    ts = tasks("今天任务：1.看完夏商周的网课，记笔记2.对照大纲补充笔记"
               "3.刷小程序上的真题4.整理错题5.刷教辅上的选择题")
    assert len(ts) == 5, ts
    t1 = find(ts, action="看完", time="2026-08-02")
    assert t1 and t1["notes"] == "记笔记", ts
    t2 = find(ts, action="对照")
    assert t2 and "大纲" in t2["object"] and t2["notes"] == "补充笔记", ts
    assert find(ts, action="刷", time="2026-08-02"), ts
    assert find(ts, action="整理", obj="错题"), ts
    for t in ts:
        assert t["time"] == "2026-08-02", t  # 头部"今天"作为默认时间
    print("ok 结构化列表 + 头部时间 →", len(ts), "条任务")


def test_structured_dunhao():
    ts = tasks("1、写作业，2、复习语文，3、预习数学")
    assert len(ts) == 3, ts
    assert find(ts, action="写", obj="作业"), ts
    assert find(ts, action="复习", obj="语文"), ts
    assert find(ts, action="预习", obj="数学"), ts
    print("ok 顿号列表 →", len(ts), "条任务")


def test_quantity_not_structured():
    ts = tasks("我有3个苹果,5个香蕉")
    assert not any(t["action"] for t in ts), ts  # 不应被误判为结构化列表任务
    print("ok 数量枚举不误判 →", len(ts), "条")


def test_time_range():
    t = find(tasks("下午3点到5点开会"), action="开会")
    assert t, t
    assert t["time_start"] == "2026-08-02 15:00", t
    assert t["time_end"] == "2026-08-02 17:00", t
    print("ok 时间范围(点到) →", t["time_start"], "→", t["time_end"])


def test_time_range_colon():
    ts = tasks("明天2:00到4:00做实验")
    t = find(ts, action="做实验")
    assert t and len(ts) == 1, ts
    assert t["time_start"] == "2026-08-03 02:00", t
    assert t["time_end"] == "2026-08-03 04:00", t
    print("ok 时间范围(colon) →", t["time_start"], "→", t["time_end"])


def test_time_range_zhishu():
    t = find(tasks("晚上8点至10点复习英语"), action="复习")
    assert t, t
    assert t["time_start"] == "2026-08-02 20:00", t
    assert t["time_end"] == "2026-08-02 22:00", t
    print("ok 时间范围(至) →", t["time_start"], "→", t["time_end"])


def test_header_default_time():
    ts = tasks("周五计划：交论文，去图书馆还书")
    assert len(ts) == 2, ts
    for t in ts:
        assert t["time"] == "2026-08-07", t  # 头部"周五"作为默认时间
    print("ok 头部默认时间 →", ts)


if __name__ == "__main__":
    test_example()
    test_datetime_place()
    test_weekday_evening()
    test_x_days_after()
    test_deadline()
    test_month_end()
    test_absolute()
    test_multi_task()
    test_no_verb()
    test_time_only()
    test_ba_construction()
    test_return_book()
    test_consecutive_multi()
    test_fullwidth_punct()
    test_compact_morning()
    test_compact_night()
    test_bao_reference()
    test_next_weekend()
    test_structured_list()
    test_structured_dunhao()
    test_quantity_not_structured()
    test_time_range()
    test_time_range_colon()
    test_time_range_zhishu()
    test_header_default_time()
    print("\n全部通过")
