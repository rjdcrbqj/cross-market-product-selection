from collections.abc import Sequence


def _round(value: float) -> float:
    return round(float(value), 2)


def sales_scores(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    normalized = [float(value) for value in values]
    if any(value < 0 for value in normalized):
        raise ValueError("销量不能为负数")
    minimum = min(normalized)
    maximum = max(normalized)
    if maximum == minimum:
        return [100.0 for _ in normalized]
    return [_round(100 * (value - minimum) / (maximum - minimum)) for value in normalized]


def price_similarity_score(actual: float, target: float) -> float:
    actual_value = float(actual)
    target_value = float(target)
    if actual_value < 0:
        raise ValueError("实际价格不能为负数")
    if target_value <= 0:
        raise ValueError("目标价格必须大于零")
    score = 100 * (1 - abs(actual_value - target_value) / target_value)
    return _round(max(0, score))


def rating_score(rating: float, maximum: float = 5.0) -> float:
    rating_value = float(rating)
    maximum_value = float(maximum)
    if maximum_value <= 0 or rating_value < 0 or rating_value > maximum_value:
        raise ValueError("评价分数超出平台评分范围")
    return _round(rating_value / maximum_value * 100)


def total_score(sales: float, price: float, rating: float) -> float:
    values = [float(sales), float(price), float(rating)]
    if any(value < 0 or value > 100 for value in values):
        raise ValueError("子分必须位于 0 到 100 之间")
    return _round(values[0] * 0.4 + values[1] * 0.4 + values[2] * 0.2)
