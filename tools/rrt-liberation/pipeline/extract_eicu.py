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
    # usecols keeps memory bounded: lab (~4 GB) / intakeoutput (~2 GB) uncompressed
    # collapse to a few columns; .csv.gz is decompressed by pandas transparently.
    treatment = pd.read_csv(
        raw.treatment,
        usecols=["patientunitstayid", "treatmentoffset", "treatmentstring"],
    )
    # eICU `treatment` is point-documented (no stop offset): each RRT mention is a
    # zero-duration marker at treatmentoffset. merge_gap_minutes coalesces markers of the
    # same episode; the IHD/CRRT off-thresholds then detect liberation. eICU carries no
    # true RRT duration — a documented limitation vs MIMIC procedureevents intervals.
    treatment["treatmentstopoffset"] = treatment["treatmentoffset"]
    lab = pd.read_csv(raw.lab, usecols=["patientunitstayid", "labname", "labresult"])
    intakeoutput = pd.read_csv(
        raw.intakeoutput, usecols=["patientunitstayid", "celllabel", "cellvaluenumeric"]
    )
    diagnosis = pd.read_csv(raw.diagnosis, usecols=["patientunitstayid", "diagnosisstring"])
    infusiondrug = pd.read_csv(raw.infusiondrug, usecols=["patientunitstayid", "drugname"])
    respiratorycare = pd.read_csv(raw.respiratorycare, usecols=["patientunitstayid"])
    patient = pd.read_csv(
        raw.patient,
        usecols=["patientunitstayid", "hospitaldischargeoffset", "hospitaldischargestatus"],
    )

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
