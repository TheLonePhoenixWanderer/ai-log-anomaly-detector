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