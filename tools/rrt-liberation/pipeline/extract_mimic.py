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
    build_mimic_stays,
)
from rrt_liberation.utils import read_csv_filtered, write_csv

logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../conf", config_name="extract_mimic")
def main(cfg: DictConfig) -> None:
    raw = cfg.raw
    # Memory-safe reads: labevents (~17 GB) and inputevents (~2.7 GB) are filtered by
    # itemid per chunk; the rest are read with only the columns the builders need.
    procedureevents = pd.read_csv(
        raw.procedureevents,
        usecols=["subject_id", "stay_id", "starttime", "endtime", "itemid"],
    )
    outputevents = read_csv_filtered(
        raw.outputevents, usecols=["stay_id", "itemid", "value"],
        filter_col="itemid", keep_values=list(cfg.itemids.urine),
    )
    labevents = read_csv_filtered(
        raw.labevents, usecols=["subject_id", "itemid", "valuenum", "charttime"],
        filter_col="itemid", keep_values=list(cfg.itemids.creatinine),
    )
    diagnoses_icd = pd.read_csv(raw.diagnoses_icd, usecols=["hadm_id", "icd_code"])
    inputevents = read_csv_filtered(
        raw.inputevents, usecols=["stay_id", "itemid"],
        filter_col="itemid", keep_values=list(cfg.itemids.vasopressor),
    )
    stays = pd.read_csv(
        raw.icustays,
        usecols=["subject_id", "hadm_id", "stay_id", "intime", "outtime"],
    )
    admissions = pd.read_csv(
        raw.admissions, usecols=["hadm_id", "dischtime", "hospital_expire_flag"]
    )
    # MIMIC-IV 3.1 removed the ventilation table; derive from procedureevents instead.
    ventilation = procedureevents[["stay_id", "itemid"]].drop_duplicates()

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
    write_csv(build_mimic_stays(stays, admissions), out / "stays.csv")
    logger.info("Wrote canonical MIMIC CSVs to %s", out)


if __name__ == "__main__":
    main()
