"""故意有 bug 的小工具函数，给 Agent 验收用。"""


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("values must not be empty")
    # BUG: 整数除法会丢掉小数，mean([1, 2]) 会得到 1 而不是 1.5
    return sum(values) / len(values)
