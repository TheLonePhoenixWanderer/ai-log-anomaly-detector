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

Architecture 
------------
**1. Synthetic Log Generation**
- 7 days of authentication activity
- Business hour bias
- Realistic IP distributions
- User home-country mapping

**2. Anomaly Injection**
- Impossible travel
- Off-hours login bursts
- Public IP + country mismatch + failures

**3. Feature Engineering**
- Hour of login
- Day of week
- Internal vs public IP
- Country mismatch
- Rolling 30-minute failure counts
- Rolling 30-minute event rate
- Encoded device / auth / country buckets

**4. Model Training**
- IsolationForest (unsupervised)
- Risk scoring via inverted anomaly score
- Top 2% highest-risk events flagged

**5. Output**
- Full log dataset
- Flaggedd anomalies with human-readable "reason strings"

Tech Stack
----------
- Python 3.10+
- pandas
- numpy
- scikit-learn
- Isolation Forest (unsupervised anomaly detection)

Project Structure
-----------------
    ai-log-anomaly-detector/
    │
    ├── detector.py
    ├── requirements.txt
    ├── README.md
    └── output/
        ├── logs.csv
        └── anomalies.csv

How to Run
----------
### 1. Create virtual environment
    python -m venv .venv
    source .venv/bin/activate

### 2. Install dependencies
    pip install -r requirements.txt

### 3. Run detector
    python detector.py

Example Output
--------------
Console summary:
![detector.py console summary](/assets/console-summary.png)

Saved outputs:
- output/logs.csv
- outputs/anomlies.csv

Each anomaly includes 'explanation' tags such as:
![detector.py explanation tags](/assets/example-explanation-tags.png)

Why Isolation Forest?
---------------------
Isolation Forest works well for:
- High-dimensional behavioural data
- Unlabelled datasets
- Rare-event detection
- Security analytics use cases

Unlike rule-based systems, it learns patterns of "normal" behaviour and flags statistical outliers automatically. 

Security Relevance
------------------
This project mirros real-world detection logic used in:
- SIEM behavioural analytics
- UEBA systems
- Identity threat detection
- DLP anomaly modelling

It demonstrates how ML can enhance traditional detection engineering.

Author
------
Built as a hands-on AI + cybersecurity mini-project to strengthen applied machine learning engineering skills