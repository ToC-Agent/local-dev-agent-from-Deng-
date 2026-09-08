from math_utils import mean


def test_mean_two_ints_should_be_one_point_five():
    assert mean([1, 2]) == 1.5


def test_mean_three_evens():
    assert mean([2, 4, 6]) == 4.0
