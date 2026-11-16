"""등록, 점수, 임계값, K 카운터 시험."""

import pytest

from core import model


def test_enroll_uses_mean_and_sample_std():
    mean, std = model.enroll([[1.0, 10.0], [2.0, 10.0], [3.0, 10.0]])
    assert mean == pytest.approx([2.0, 10.0])
    assert std == pytest.approx([1.0, 0.0])  # ddof=1


def test_score_is_mean_of_scaled_distances():
    # 특징 1: |3-1|/1 = 2,  특징 2: |5-5|/2 = 0  ->  평균 1
    assert model.score([3.0, 5.0], mean=[1.0, 5.0], std=[1.0, 2.0]) == pytest.approx(1.0)


def test_score_uses_std_floor():
    # 표준편차가 0 이어도 0.005 로 나눈다: 0.01 / 0.005 = 2
    assert model.score([0.11], mean=[0.10], std=[0.0]) == pytest.approx(2.0)


def test_threshold_is_95th_percentile_with_linear_interpolation():
    # 1~5 의 95 백분위수: 위치 0.95*4 = 3.8 -> 4 + 0.8*(5-4) = 4.8
    assert model.threshold([1, 2, 3, 4, 5]) == pytest.approx(4.8)


def test_anomaly_only_when_score_is_above_tau():
    assert model.is_anomaly(2.1, tau=2.0) is True
    assert model.is_anomaly(2.0, tau=2.0) is False
    assert model.is_anomaly(1.9, tau=2.0) is False


def test_counter_counts_consecutive_anomalies():
    counter = 0
    counter = model.update_counter(counter, anomaly=True)
    counter = model.update_counter(counter, anomaly=True)
    assert counter == 2
    assert model.needs_reauth(counter) is False
    counter = model.update_counter(counter, anomaly=True)
    assert counter == 3
    assert model.needs_reauth(counter) is True


def test_counter_resets_on_normal_decision():
    counter = model.update_counter(2, anomaly=False)
    assert counter == 0
