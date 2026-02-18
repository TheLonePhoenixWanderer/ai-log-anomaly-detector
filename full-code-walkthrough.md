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

### Why we do this
- **RNG_SEED** gives repeatability. Without it, every run produces totally different logs and anomalies, making debugging and tuning painful.
- **N_USERS**, **N_EVENTS** controls dataset scale. 
- **ANOMALY_RATE** controls how often you inject "anomalies". 
- **OUT_DIR** keeps output tidy. 

**Real-world note**: In reality you rarely know your anomaly rate. That's why unsupervised models are tricky - you pick a threshold that matches operational capacity (how many alerts per day can SOC triage).

OrgContext dataclass
--------------------
    @dataclass
    class OrgContext:
        users: list[str]
        ips_internal: list[str]
        countries: list[str]
        user_home_country: dict[str, str]

This is your "organisation metadata".

### Why this matters
In real systems, you always have "context":
- user -> home office location
- user -> normal device types
- IP ranges -> corporate networks
- normal geo distribution

The model becomes much more meaningful when you simulate these realities.

Utility functions
-----------------
### ensure_out_dir
    def ensure_out_dir(path: str) -> None:
        os.makedirs(path, exist_ok=True)

Creates output folder if missing.

**Why *exist_ok=True*:** avoids crashing if folder already exists.

### random_ip_private / random_ip_public
You generate:
- internal IPs in *10.x.x.x*
- "public-like" IPs with non-private ranges

Why do this?
- internal vs external network source is a huge security signal
- many org detections start with: "new external IP login"

make_context()
--------------
This sets up the simulated company environment:

    users = [f"user{i:02d}" for i in range(1, N_USERS + 1)]
    countries = ["AU", "NZ", "US", "GB", "SG", "DE", "IN", "JP"]
    home_choices = np.random.choice(countries, p=[...])
    user_home_country = {u: hc for u, hc in zip(users, home_choice)}
    ips_internal = random_ip_private(200)

**What's happening?**
- Create **user01..user40**
- Define a country set
- Assign most users to AU (biased distribution)
- Generate 200 internal IPs

**Security realism**
- Most orgs have a dominant "home" region
- A smaller subset travel or work offshore
- Internal IP space is consistent and repeated

generate_base_logs(ctx)
-----------------------
This is the "normal activity generator".

### Time range and timestamps
    start = now - 7 (days)
    end = now
    ts = start + (end - start) * np.random.rand(N_EVENTS)

This makes random timestamps across 7 days.

Then you bias toward business hours:
- identify events outside 7am to 8pm
- move 70% of off-hours events into 8am to 6pm

**Why this matters?**

Normal auth activity is not uniformly random. Business horu bias makes anomalies more meaningful. 

### Users
    users = np.random.choice(ctx.users, size=N_EVENTS)

Just random users. In reality you might weight some users higher (admins, service accounts)

