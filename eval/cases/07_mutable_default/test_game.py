from game import record_guess


def test_history_not_shared_between_games():
    first = record_guess(5)
    second = record_guess(7)
    assert first == [5]
    assert second == [7]


def test_existing_history_is_extended():
    assert record_guess(3, [1, 2]) == [1, 2, 3]
