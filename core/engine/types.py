# core/engine/types.py
from dataclasses import dataclass
import pandas as pd

@dataclass
class CurriculumData:
    ssbb_df: pd.DataFrame
    relaciones_long: pd.DataFrame
    ce_df: pd.DataFrame
    cev_df: pd.DataFrame
    do_df: pd.DataFrame
    ce_do_exp: pd.DataFrame
    descripciones: dict

    # índices (sets) para clasificar rápido
    ssbb_set: set
    ce_set: set
    cev_set: set
    do_set: set
