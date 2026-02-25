from __future__ import annotations

import os
import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sklearn.ensemble import IsolationForest

# Custom Modules
from addons.impossible_travel import add_impossible_travel_flags
from addons.risk_plotter import plot_risk_over_time

# Config

RNG_SEED = 42
N_USERS = 40
N_EVENTS = 6000
ANOMALY_RATE = 0.03 # ~3% injected anomalies
OUT_DIR = "output"

np.random.seed(RNG_SEED)

@dataclass
class OrgContext:
    users: list[str]
    ips_internal: list[str]
    countries: list[str]
    user_home_country: dict[str, str]

def ensure_out_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def random_ip_private(n: int) -> list[str]:
    # 10.x.x.x private IPs
    a = 10
    b = np.random.randint(0, 256, n)
    c = np.random.randint(0, 256, n)
    d = np.random.randint(1, 255, n)
    return [f"{a}.{b[i]}.{c[i]}.{d[i]}" for i in range(n)]

def random_ip_public(n: int) -> list[str]:
    # Crude public-looking IPs (avoids private ranges)
    a = np.random.choice([23, 34, 45, 52, 63, 72, 85, 91, 101, 122, 143, 159, 173, 186, 201], n)
    b = np.random.randint(0, 256, n)
    c = np.random.randint(0, 256, n)
    d = np.random.randint(1, 255, n)
    return [f"{a[i]}.{b[i]}.{c[i]}.{d[i]}" for i in range(n)]

def make_context() -> OrgContext:
    users = [f"user{i:02d}" for i in range(1, N_USERS + 1)]
    countries = ["AU", "NZ", "US", "GB", "SG", "DE", "IN", "JP"]
    
    # Most users are AU-based; a few are elsewhere
    home_choices = np.random.choice(countries, size=len(users), p=[0.65, 0.08, 0.08, 0.06, 0.05, 0.03, 0.03, 0.02])
    user_home_country = {u: hc for u, hc in zip(users, home_choices)}
    ips_internal = random_ip_private(200)
    return OrgContext(users=users, ips_internal=ips_internal, countries=countries, user_home_country=user_home_country)

def generate_base_logs(ctx: OrgContext) -> pd.DataFrame:

    """
    Generate normal auth logs:
    - Mostly business hours
    - Mostly internal IPs
    - Country aligns with user's home
    - Mostly success with occasional failures
    """

    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc)

    # Random timestamps over last 7 days
    ts = start + (end - start) * np.random.rand(N_EVENTS)

    users = np.random.choice(ctx.users, size=N_EVENTS)

    # Business hours bias: Create "hour" distribution with peaks 8-18 
    hours = np.array([t.hour for t in ts])

    # Re-weight hours toward business hours by resampling a portion
    mask_offhours = (hours < 7) | (hours > 20)

    # For off-hours, push many into business hours
    ts = np.array(ts, dtype="datetime64[ns]")
    off_idx = np.where(mask_offhours)[0]

    if len(off_idx) > 0:
        # Move 70% of off-hours events into business hours same day
        move_n = int(0.70 * len(off_idx))
        chosen = np.random.choice(off_idx, size=move_n, replace=False)

        # Set hour 8-18
        new_hours = np.random.randint(8, 19, size=move_n)

        # Keep date, change hour/min/sec
        for i, h in zip(chosen, new_hours):
            dt = pd.Timestamp(ts[i]).to_pydatetime().replace(tzinfo=timezone.utc)
            ts[i] = np.datetime64(dt.replace(hour=int(h), minute=int(np.random.randint(0, 60)), second=int(np.random.randint(0, 60))))
    
    ts = pd.to_datetime(ts).tz_localize("UTC")

    # IP source: mostly internal
    is_internal = np.random.rand(N_EVENTS) < 0.88
    ip = np.where(
        is_internal,
        np.random.choice(ctx.ips_internal, size=N_EVENTS),
        np.random.choice(random_ip_public(400), size=N_EVENTS)
    )

    # Country: mostly user's home, sometimes other (travel/roaming)
    country = []
    for u in users:
        if np.random.rand() < 0.93:
            country.append(ctx.user_home_country[u])
        else:
            country.append(np.random.choice(ctx.countries))
    country = np.array(country)

    # Device types & auth type
    device = np.random.choice(["Windows", "Mac", "iOS", "Android", "Linux"], size=N_EVENTS, p=[0.55, 0.15, 0.13, 0.12, 0.05])
    auth_type = np.random.choice(["Password", "MFA", "SSO"], size=N_EVENTS, p=[0.40, 0.35, 0.25])

    # Outcome: mostly success; failures slightly more common on password
    base_fail = np.where(auth_type == "Password", 0.06, 0.03)
    success = np.random.rand(N_EVENTS) > base_fail

    df = pd.DataFrame({
        "timestamp_utc": ts,
        "user": users,
        "src_ip": ip,
        "country": country,
        "device": device,
        "auth_type": auth_type,
        "success": success.astype(int),
    })

    return df.sort_values("timestamp_utc").reset_index(drop=True)

def inject_anomalies(ctx: OrgContext, df: pd.DataFrame) -> pd.DataFrame:

    """
    Inject a few realistic anomalies:
    1) Impossible travel: Same user logs in from two far countries within 10 minutes
    2) Off-hours burst: High frequency failed logins at 2-4am
    3) New country + public IP + password failures combo
    """

    df = df.copy()
    n_anom = max(1, int(len(df) * ANOMALY_RATE))
    anom_indicies = np.random.choice(df.index, size=n_anom, replace=False)

    df["is_injected_anomaly"] = 0
    df.loc[anom_indicies, "is_injected_anomaly"] = 1

    # Split anomalies roughly into types
    types = np.random.choice(["impossible_travel", "offhours_burst", "new_country_fail"], size=n_anom, p=[0.35, 0.35, 0.30])
    df.loc[anom_indicies, "anomaly_type"] = types

    # Type 1: Impossible travel
    travel_idx = anom_indicies[types == "impossible_travel"]
    for idx in travel_idx:
        u = df.at[idx, "user"]
        home = ctx.user_home_country[u]
        other = np.random.choice([c for c in ctx.countries if c != home])
        
        # Set event to other country and public IP
        df.at[idx, "country"] = other
        df.at[idx, "src_ip"] = np.random.choice(random_ip_public(50))
        df.at[idx, "auth_type"] = "Password"
        df.at[idx, "success"] = 1

        # Create a second event within 10 mins in home country to simulate "impossible travel"
        if np.random.rand() < 0.8:
            ts = df.at[idx, "timestamp_utc"]
            new_row = df.loc[idx].copy()
            new_row["timestamp_utc"] = ts + pd.Timedelta(minutes=int(np.random.randint(2, 10)))
            new_row["country"] = home
            new_row["src_ip"] = np.random.choice(ctx.ips_internal)
            df = pd.concat([df, new_row.to_frame().T], ignore_index=True)

    # Type 2: Off-hours burst (failed attempts)
    burst_idx = anom_indicies[types == "offhours_burst"]
    for idx in burst_idx:
        u = df.at[idx, "user"]
        ts = df.at[idx, "timestamp_utc"]

        # Force time to 02:00-04:59 UTC (still "off-hours" generally)
        forced = ts.replace(
            hour=int(np.random.randint(2, 5)),
            minute=int(np.random.randint(0, 60)),
            second=int(np.random.randint(0, 60))
        )
        df.at[idx, "timestamp_utc"] = forced
        df.at[idx, "src_ip"] = np.random.choice(random_ip_public(50))
        df.at[idx, "auth_type"] = "Password"
        df.at[idx, "success"] = 0

        # Add additional rapid failures
        burst_n = int(np.random.randint(8, 25))
        rows = []
        for k in range(burst_n):
            r = df.loc[idx].copy()
            r["timestamp_utc"] = forced + pd.Timedelta(seconds=int(k * np.random.randint(5, 20)))
            r["success"] = 0
            r["anomaly_type"] = "offhours_burst_member"
            rows.append(r)
        df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)

    # Type 3: New country + public IP + failures
    nc_idx = anom_indicies[type == "new_country_fail"]
    for idx in nc_idx:
        u = df.at[idx, "user"]
        home = ctx.user_home_country[u]
        other = np.random.choice([c for c in ctx.countries if c != home])
        df.at[idx, "country"] = other
        df.at[idx, "src_ip"] = np.random.choice(random_ip_public(50))
        df.at[idx, "auth_type"] = "Password"
        df.at[idx, "success"] = 0

    # Clean up + sort
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    return df

def add_features(ctx: OrgContext, df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    # Time features
    df["hour"] = df["timestamp_utc"].dt.hour
    df["dayofweek"] = df["timestamp_utc"].dt.dayofweek # Mon=0

    # Internal IP heuristic
    df["is_internal_ip"] = df["src_ip"].astype(str).str.startswith("10.").astype(int)

    # Home-country mismatch
    df["home_country"] = df["user"].map(ctx.user_home_country)
    df["is_home_country"] = (df["country"] == df["home_country"]).astype(int)

    # Per-user rolling features: recent failures + event rate
    df = df.sort_values(["user", "timestamp_utc"]).reset_index(drop=True)

    # Rolling window: 30 minutes
    df["ts_unix"] = df["timestamp_utc"].astype("int64") // 10**9

    # Compute per-user rolling counts by iterating groups (fast enough for this size)
    recent_failures = np.zeros(len(df), dtype=float)
    recent_events = np.zeros(len(df), dtype=float)

    window_sec = 30 * 60

    for u, g in df.groupby("user", sort=False):
        idxs = g.index.to_numpy()
        ts = g["ts_unix"].to_numpy()
        succ = g["success"].to_numpy()

        left = 0
        fail_count = 0
        
        # Maintain a moving window (ts[i]-window_sec, ts[i])
        for j in range(len(idxs)):
            t = ts[j]

            # Expand window includes current event; shrink left bound
            while ts[left] < t - window_sec:
                # Remove left event
                if succ[left] == 0:
                    fail_count -= 1
                left += 1

            # Window is now [left..j-1] (past) plus current
            past_events = j - left # excluding current
            past_fails = fail_count

            recent_events[idxs[j]] = past_events
            recent_failures[idxs[j]] = past_fails

            # Add current to counts for next iterations
            if succ[j] == 0:
                fail_count += 1

    df["recent_events_30m"] = recent_events
    df["recent_failures_30m"] = recent_failures

    # Encode categorical fields lightly (no one-hot to keep it quick)
    # Simple hashing trick into small integer buckets
    def hash_bucket(series: pd.Series, buckets: int = 32) -> pd.Series:
        return series.astype(str).apply(lambda x: hash(x) % buckets).astype(int)
    
    df["device_bucket"] = hash_bucket(df["device"], 16)
    df["auth_bucket"] = hash_bucket(df["auth_type"], 8)
    df["country_bucket"] = hash_bucket(df["country"], 16)

    # Feature set
    return df

def train_and_score(df: pd.DataFrame) -> pd.DataFrame:
    
    df = df.copy()

    feature_cols = [
        "hour",
        "dayofweek",
        "success",
        "is_internal_ip",
        "is_home_country",
        "recent_events_30m",
        "recent_failures_30m",
        "device_bucket",
        "auth_bucket",
        "country_bucket",
    ]

    X = df[feature_cols].astype(float)
    
    model = IsolationForest(
        n_estimators=250,
        contamination="auto",
        random_state=RNG_SEED,
    )
    model.fit(X)
    
    # decision_function: higher = more normal, lower = more anomalous
    df["anomaly_score"] = model.decision_function(X)

    # Invert to a more intuitive score: higher = more anomalous
    df["risk_score"] = -df["anomaly_score"]

    # Label anomalies by percentile threshold
    thresh = np.quantile(df["risk_score"], 0.98) # top 2% as anomalies
    df["is_flagged_anomaly"] = (df["risk_score"] >= thresh).astype(int)

    return df, feature_cols, thresh

def explain_row(row: pd.Series) -> list[str]:

    reasons = []

    if row["success"] == 0 and row["recent_failures_30m"] >= 3:
        reasons.append("Multiple recent failures (30m)")
    if row["hour"] <= 5 or row["hour"] >= 22:
        reasons.append("off-hours login time")
    if row["is_internal_ip"] == 0:
        reasons.append("Public IP source")
    if row["is_home_country"] == 0:
        reasons.append("Country mismatch vs home")
    if row["recent_events_30m"] >= 10:
        reasons.append("High event volume (30m)")

    return reasons or ["Model outlier (combined features)"]

def main() -> None:

    ensure_out_dir(OUT_DIR)

    ctx = make_context()
    base = generate_base_logs(ctx)
    logs = inject_anomalies(ctx, base)
    logs = add_features(ctx, logs)

    scored, feature_cols, thresh = train_and_score(logs)

    scored, it_pairs = add_impossible_travel_flags(scored)
    it_pairs.to_csv(os.path.join(OUT_DIR, "impossible_travel_pairs.csv"), index=False)

    try:
        plot_paths = plot_risk_over_time(scored, out_dir=OUT_DIR, top_k=5)
    except ModuleNotFoundError as e:
        plot_paths = []
        print(f"\n[plot] Skipped (missing dependency): {e}")

    # Save full logs and anomalies
    logs_path = os.path.join(OUT_DIR, "logs.csv")
    scored.to_csv(logs_path, index=False)

    anomalies = scored[(scored["is_flagged_anomaly"] == 1) | (scored["is_impossible_travel"] == 1)].copy()
    anomalies["reasons"] = anomalies.apply(explain_row, axis=1).apply(lambda xs: "; ".join(xs))
    anomlies = anomalies.sort_values("risk_score", ascending=False)

    anom_path = os.path.join(OUT_DIR, "anomalies.csv")
    anomlies.to_csv(anom_path, index=False)

    # Print summary
    injected = int(scored.get("is_injected_anomaly", pd.Series([0])).sum())
    flagged = int(anomlies.shape[0])

    print("\n=== AI Log Anomaly Detector ===")
    print(f"Total events: {len(scored)}")
    print(f"Injected anomalies (ground truth): {injected}")
    print(f"Flagged anomalies (top 2% risk): {flagged}")
    print(f"Risk threshold (98th percentile): {thresh:.4f}")
    print("\nTop 15 flagged events:\n")

    display_cols = [
        "timestamp_utc", "user", "src_ip", "country", "device", "auth_type",
        "success", "recent_failures_30m", "recent_events_30m",
        "risk_score", "is_injected_anomaly", "anomaly_type"
    ]

    # anomaly_type may not exist for all rows
    for col in display_cols:
        if col not in anomalies.columns:
            anomalies[col] = ""

    print(anomalies[display_cols + ["reasons"]].head(15).to_string(index=False))

    print(f"\nSaved: {logs_path}")
    print(f"Saved: {anom_path}")

if __name__ == "__main__":
    main()
