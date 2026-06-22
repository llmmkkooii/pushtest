import numpy as np

from rrt_liberation.evaluation import decision_curve, save_dca_plot


def test_treat_none_is_zero_and_prevalence():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p)
    assert all(v == 0.0 for v in curve["net_benefit_none"])
    assert curve["prevalence"] == 0.5


def test_net_benefit_hand_calc_at_threshold_0_5():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p, thresholds=[0.5])
    assert abs(curve["net_benefit_model"][0] - 0.5) < 1e-12
    assert abs(curve["net_benefit_all"][0] - 0.0) < 1e-12


def test_treat_all_formula_at_threshold_0_25():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p, thresholds=[0.25])
    expected = 0.5 - 0.5 * (0.25 / 0.75)
    assert abs(curve["net_benefit_all"][0] - expected) < 1e-12


def test_perfect_separation_model_ge_all():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p, thresholds=[0.5])
    assert curve["net_benefit_model"][0] >= curve["net_benefit_all"][0]


def test_default_grid_and_override():
    y = np.array([0, 1, 0, 1])
    p = np.array([0.3, 0.7, 0.4, 0.6])
    default = decision_curve(y, p)
    assert 0.0 < min(default["thresholds"]) <= max(default["thresholds"]) < 1.0
    assert len(default["net_benefit_model"]) == len(default["thresholds"])
    custom = decision_curve(y, p, thresholds=[0.2, 0.4, 0.6])
    assert custom["thresholds"] == [0.2, 0.4, 0.6]


def test_deterministic():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    assert decision_curve(y, p) == decision_curve(y, p)


def test_save_dca_plot_writes_png(tmp_path):
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = decision_curve(y, p)
    path = tmp_path / "sub" / "dca.png"
    save_dca_plot(curve, path)
    assert path.exists() and path.stat().st_size > 0
