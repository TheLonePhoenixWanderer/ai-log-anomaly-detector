Mental model of the whole script
--------------------------------
Think of this as a mini security analytics pipeline:
1. **Create an organisation world** (users, home countries, internal IP space)
2. **Generate normal auth logs** (mostly benign)
3. **Inject attacker-like patterns** (ground truth anomalies)
4. **Turn raw logs into numeric features** (so ML can learn)
5. **Train an unsupervised model** on the full dataset
6. **Score everything** and flag the riskiest 2%
7. **Add human-readable "reasons"** for each flagged event
8. **Save to CSV** for inspection + future use

Even if the model is imperfect, this teaches the  *real pipeline shape*.

Imports + global configuration
------------------------------
### Imports
- numpy, pandas: data generation, transformation, time handling
- dataclasses: clean container for org context
- datetime, timezone, timedelta: time range generation
- IsolationForest: anomaly detection model
### Key config variables
    RNG_SEED = 42
    N_USERS = 40
    N_EVENTS = 6000
    ANOMALY_RATE = 0.03
    OUT_DIR = "output"
    np.random.seed(RNG_SEED)
