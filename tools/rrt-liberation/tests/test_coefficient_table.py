import numpy as np

from rrt_liberation.reporting.report import build_coefficient_table


def test_coefficient_table_odds_ratio_and_ci():
    coef_ci = {
        "urine_output_24h": {"point": 0.0, "ci_low": -0.1, "ci_high": 0.1},
        "creatinine": {"point": np.log(2.0), "ci_low": 0.0, "ci_high": np.log(4.0)},
    }
    t = build_coefficient_table(coef_ci)
    assert list(t.columns) == ["beta", "odds_ratio", "ci_low", "ci_high"]
    assert abs(t.loc["urine_output_24h", "odds_ratio"] - 1.0) < 1e-9
    assert abs(t.loc["creatinine", "odds_ratio"] - 2.0) < 1e-9
    assert abs(t.loc["creatinine", "ci_high"] - 4.0) < 1e-9  # exp(log4)
