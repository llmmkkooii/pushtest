import pandas as pd

from rrt_liberation.reporting.report import build_table1, write_flow


def test_table1_has_overall_and_group_columns():
    cohort = pd.DataFrame({"success": [1, 1, 0], "urine_output_24h": [800, 1200, 100]})
    t1 = build_table1(cohort, by="success")
    assert t1.loc["n", "overall"] == 3
    assert "success=1" in t1.columns
    assert t1.loc["n", "success=1"] == 2
    assert t1.loc["urine_output_24h_mean", "success=1"] == 1000.0


def test_write_flow_creates_file(tmp_path):
    path = tmp_path / "flow.txt"
    write_flow({"raw_episodes": 10, "after_exclusions": 7, "attempts": 5}, path)
    assert path.exists()
    assert "attempts" in path.read_text()
