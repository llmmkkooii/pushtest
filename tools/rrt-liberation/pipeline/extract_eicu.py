"""Extract eICU-CRD raw tables into the pipeline input CSVs."""

from __future__ import annotations

import logging
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

from rrt_liberation.extract import (
    build_eicu_flags,
    build_eicu_labs,
    build_eicu_rrt_events,
    build_eicu_stays,
)
from rrt_liberation.utils import write_csv

logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../conf", config_name="extract_eicu")
def main(cfg: DictConfig) -> None:
    raw = cfg.raw
    treatment = pd.read_csv(raw.treatment)
    lab = pd.read_csv(raw.lab)
    intakeoutput = pd.read_csv(raw.intakeoutput)
    diagnosis = pd.read_csv(raw.diagnosis)
    infusiondrug = pd.read_csv(raw.infusiondrug)
    respiratorycare = pd.read_csv(raw.respiratorycare)
    patient = pd.read_csv(raw.patient)

    out = Path(cfg.paths.output_dir)
    write_csv(
        build_eicu_rrt_events(
            treatment, list(cfg.terms.crrt), list(cfg.terms.ihd), cfg.merge_gap_minutes
        ),
        out / "crrt_events.csv",
    )
    write_csv(
        build_eicu_labs(lab, intakeoutput, list(cfg.terms.creatinine), list(cfg.terms.urine)),
        out / "labs.csv",
    )
    write_csv(
        build_eicu_flags(
            patient, diagnosis, infusiondrug, respiratorycare,
            list(cfg.terms.septic_shock), list(cfg.terms.vasopressor), list(cfg.terms.ventilation),
        ),
        out / "flags.csv",
    )
    write_csv(build_eicu_stays(patient), out / "stays.csv")
    logger.info("Wrote canonical eICU CSVs to %s", out)


if __name__ == "__main__":
    main()
