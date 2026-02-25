# impossible_travel.py

'''
Flags country changes for the same user within X minutes (default 10m)
Produces:
    - is_impssible_travel column on the main dataframe
    - impossible_travel_pairs.csv with the flagged event pairs
'''

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import pandas as pd

@dataclass(frozen=True)
class ImpossibleTravelConfig:
    user_col: str = "user"
    time_col: str = "timestamp_utc"
    country_col: str = "country"
    window_minutes: int = 10

def detect_impossible_travel_pairs(
        df: pd.DataFrame,
        cfg: ImpossibleTravelConfig = ImpossibleTravelConfig(),
) -> pd.DataFrame:
    required = {cfg.user_col, cfg.time_col, cfg.country_col}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns for impossible travel: {sorted(missing)}")
    
    work = df[[cfg.user_col, cfg.time_col, cfg.country_col] + (["src_ip"] if "src_ip" in df.columns else [])].copy()
    work.rename(columns={"index": "row_index"}, inplace=True)

    work = work.sort_values([cfg.user_col, cfg.time_col]).reset_index()
    work.rename(columns={"index": "row_index"}, inplace=True)

    g = work.groupby(cfg.user_col, sort=False)
    work["prev_row_index"] = g["row_index"].shift(1)
    work["prev_time"] = g[cfg.time_col].shift(1)
    work["prev_country"] = g[cfg.country_col].shift(1)
    if "src_ip" in work.columns:
        work["prev_src_ip"] = g["src_ip"].shift(1)

    work["delta_seconds"] = (work[cfg.time_col] - work["prev_time"]).dt.total_seconds()

    within_window = work["delta_seconds"].notna() & (work["delta_seconds"] <= cfg.window_minutes * 60)
    country_changed = work["prev_country"].notna() & (work[cfg.country_col] != work["prev_country"])
    flagged = work[within_window & country_changed].copy()

    if flagged.empty:
        return pd.DataFrame(columns=[
            cfg.user_col,
            "row_index_1", "time_1", "country_1", "src_ip_1",
            "row_index_2", "time_2", "country_2", "src_ip_2",
            "delta_seconds",
            "rule_reason",
        ])
    return pd.DataFrame({
        cfg.user_col: flagged[cfg.user_col].values,
        "row_index_1": flagged["prev_row_index"].astype("Int64").values,
        "time_1": flagged["prev_time"].values,
        "country_1": flagged("prev_country").values,
        "src_ip_1": flagged.get("prev_src_ip", pd.Series([pd.NA] * len(flagged))).values,
        "row_index_2": flagged["row_index"].astype("Int64").values,
        "time_2": flagged[cfg.time_col].values,
        "country_2": flagged[cfg.country_col].values,
        "src_ip_2": flagged.get("src_ip", pd.Series([pd.NA] * len(flagged))).values,
        "delta_seconds": flagged["delta_seconds"].values,
        "rule_reason": [f"country changed within {cfg.window_minutes}m" for _ in range(len(flagged))],
    })

def add_impossible_travel_flags(
        df: pd.DataFrame,
        cfg: ImpossibleTravelConfig = ImpossibleTravelConfig(),
        flag_col: str = "is_impossible_travel",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    flagged_pairs = detect_impossible_travel_pairs(df, cfg)

    out = df.copy()
    out[flag_col] = 0

    if flagged_pairs.empty:
        return out, flagged_pairs
    
    idxs = pd.Index([])
    idx = idxs.append(pd.Index(flagged_pairs["row_index_1"].dropna().astype(int).tolist()))
    idxs = idxs.append(pd.Index(flagged_pairs["row_index_2"].dropna().astype(int).tolist()))

    out.loc[idxs.unique(), flag_col] = 1

    return out, flagged_pairs