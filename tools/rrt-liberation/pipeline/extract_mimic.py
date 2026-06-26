"""Extract MIMIC-IV raw tables into the canonical pipeline CSVs."""

from __future__ import annotations

import logging
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.extract import (
    build_mimic_flags,
    build_mimic_labs,
    build_mimic_rrt_events,
)
from rrt_liberation.utils import write_csv

logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../conf", config_name="extract_mimic")
def main(cfg: DictConfig) -> None:
    raw = cfg.raw
    procedureevents = pd.read_csv(raw.procedureevents)
    outputevents = pd.read_csv(raw.outputevents)
    labevents = pd.read_csv(raw.labevents)
    diagnoses_icd = pd.read_csv(raw.diagnoses_icd)
    inputevents = pd.read_csv(raw.inputevents)
    ventilation = pd.read_csv(raw.ventilation)
    stays = pd.read_csv(raw.icustays)

    out = Path(cfg.paths.output_dir)
    write_csv(
        build_mimic_rrt_events(
            procedureevents, list(cfg.itemids.crrt), list(cfg.itemids.ihd), cfg.merge_gap_hours
        ),
        out / "crrt_events.csv",
    )
    write_csv(
        build_mimic_labs(
            outputevents, labevents, stays,
            list(cfg.itemids.urine), list(cfg.itemids.creatinine),
        ),
        out / "labs.csv",
    )
    write_csv(
        build_mimic_flags(
            stays, diagnoses_icd, inputevents, ventilation,
            list(cfg.codes.septic_shock_icd), list(cfg.itemids.vasopressor),
            list(cfg.itemids.ventilation),
        ),
        out / "flags.csv",
    )
    logger.info("Wrote canonical MIMIC CSVs to %s", out)


if __name__ == "__main__":
    main()
