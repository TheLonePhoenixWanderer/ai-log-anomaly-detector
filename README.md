AI Log Anomaly Detector
=======================
A Python-based anomaly detection engine that simulates authentication logs and detects suspicious behaviour using **unsupervised machine learning (Isolation Forest).**

This project demonstrats how behavioural security analytics can be built from scratch - including log generation, anomaly injection, feature engineering, and model scoring.

Project Overview
----------------
Modern SOC environments generate millions of authentication events daily. Identifying suspicious activity such as the below are critical for detecting early signs of compromise:
- Off-hours login attempts
- Brute-force behaviour
- Impossible travel scenarios
- Country mismatches
- Public IP login attempts

This project simulates that environment and uses **unsupervised anomaly detection** to automatically identify high-risk events. 
