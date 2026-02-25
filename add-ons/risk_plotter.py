# risk_plotter.py

'''
    - Selects top users by max risk_score (default top 5)
    - Saves 1 plot per user to: output/plots/
    - Annotates top spikes for quick visual triage
'''

from __future__ import annotations

import os
from typing import Optional, Sequence
import pandas as pd

def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def select_users_for_plotting(
        df: pd.DataFrame,
        user_col: str = "user",
        score_col: str = "risk_score",
        top_k: int = 5,
        include_users: Optional[Sequence[str]] = None,
) -> list[str]:
    if user_col not in df.columns:
        raise ValueError(f"Missing column '{user_col}'")
    if score_col not in df.columns:
        raise ValueError(f"Missing column `{score_col}`")
    
    present_users = set(df[user_col].dropna().astype(str).unique().tolist())

    if include_users:
        chosen  = [u for u in include_users if str(u) in present_users]
        
        if not chosen:
            raise ValueError("include_users provided, but none were found in the dataframe")
        
    by_user = df.groupby(user_col, as_index=True)[score_col].max().sort_values(ascending=False)

    return by_user.head(top_k).index.astype(str).tolist()

def plot_risk_over_time(
        df: pd.DataFrame,
        out_dir: str = "output",
        user_col: str = "user",
        time_col: str = "timestamp_utc",
        score_col: str = "risk_score",
        top_k: int = 5,
        include_users: Optional[Sequence[str]] = None,
        annotate_top_n: int = 3,
) -> list[str]:
    
    import matplotlib.pyplot as plt # lazy import

    if time_col not in df.columns:
        raise ValueError(f"Missing column '{time_col}'")
    
    work = df.copy()
    work[time_col] = pd.to_datetime(work[time_col], utc=True, errors="coerce")
    work = work.dropna(subset=[time_col, user_col, score_col])

    users = select_users_for_plotting(
        work, user_col=user_col, score_col=score_col, top_k=top_k, include_users=include_users
    )

    plots_dir = os.path.join(out_dir, "plots")
    _safe_mkdir(plots_dir)

    saved_paths: list[str] = []

    for u in users:
        u_df = work[work[user_col].astype(str) == str(u)].sort_values(time_col)
        
        if u_df.empty:
            continue

        fig = plt.figure(figsize=(12, 4))
        plt.plot(u_df[time_col], u_df[score_col])
        plt.title(f"Risk score over time - {u}")
        plt.xlabel("Time (UTC)")
        plt.ylabel("Risk score (higher = more anomalous)")

        top_events = u_df.nlargest(annotate_top_n, score_col)

        for _, r in top_events.iterrows():
            plt.annotate(
                f"{r[score_col]:.3f}",
                (r[time_col], r[score_col]),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
            )

        fpath = os.path.join(plots_dir, f"risk_over_time_{str(u)}.png")
        plt.tight_layout()
        plt.savefig(fpath, dpi=160)
        plt.close(fig)
        saved_paths.append(fpath)

    return saved_paths
