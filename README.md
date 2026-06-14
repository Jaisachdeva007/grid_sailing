# Grid-Sailing Task

A Pygame-based behavioural experiment for studying motor imagery (MI) in sequential motor skill learning.

Participants navigate a 5 × 5 grid using three finger keys, planning and executing (or imagining) movements across three sessions. The software handles participant registration, session management, per-keypress data logging, crash recovery, and CSV export — all without the researcher needing to touch a terminal after initial setup.

---

## Requirements

- Python 3.9+
- pygame 2.6+

```bash
pip install -r requirements.txt
```

---

## Running the experiment

```bash
python main.py
```

This opens the **Researcher Setup** screen where Juliet configures the session before handing the computer to the participant.

---

## Project structure

```
grid_sailing/
├── main.py                   # Entry point
├── config.py                 # All tunable constants
├── demo.py                   # Standalone interview demo (not used in real experiment)
├── requirements.txt
│
├── core/
│   ├── grid.py               # 5×5 grid logic + DFS puzzle generator
│   ├── trial.py              # Trial state machine (PLANNING → INPUT → ACTION → FEEDBACK → ITI)
│   └── session.py            # Block / session orchestration, auto-resume
│
├── database/
│   ├── db.py                 # SQLite CRUD layer (WAL mode, per-keypress commits)
│   └── experiment.db         # Created automatically on first run
│
├── export/
│   └── exporter.py           # CSV export (single participant / all / trial summary)
│
├── screens/
│   ├── researcher_setup.py   # Pre-session config UI (groups, timings, ratios)
│   ├── participant_login.py  # Participant ID + PIN verification
│   ├── reflection.py         # 3E report card for MI groups
│   └── export_screen.py      # Export UI accessible from researcher setup
│
└── exports/                  # All CSV files land here (created automatically)
```

---

## Experimental groups

| Code | Condition |
|------|-----------|
| MI-High | Motor imagery — high imagery ability |
| MI-Low  | Motor imagery — low imagery ability  |
| PP-High | Physical practice — high imagery ability |
| PP-Low  | Physical practice — low imagery ability  |
| CTRL-High | Control (no action stage) — high imagery ability |
| CTRL-Low  | Control (no action stage) — low imagery ability  |

---

## Session structure

| Session | Blocks |
|---------|--------|
| 1 | Familiarization × 2 → Pre-test → Practice × 2 |
| 2 | Practice × 2 |
| 3 | Practice × 2 → Post-test |

Grid ratios (repeated : random):
- **Familiarization** — 0 % repeated (all random)
- **Practice** — 72 % repeated (configurable)
- **Pre/Post-test** — 60 % repeated (configurable)

---

## Data export

From the Researcher Setup screen press **Export Data** to open the export panel. Three options:

1. **Export Participant** — full keypress-level CSV for one participant (`exports/{ID}_data.csv`)
2. **Export All** — all participants in one timestamped CSV
3. **Trial Summary** — one row per trial, no keypress detail (faster for R)

All files are written to `exports/`.

---

## Crash recovery

If the experiment crashes mid-session, restart with `python main.py` and log in the same participant. The session manager detects the incomplete session in the database and resumes from the last completed trial automatically.

---

## Database schema (SQLite)

| Table | Key fields |
|-------|-----------|
| `participants` | participant_id, age, gender, handedness, group_name, pin_hash |
| `sessions` | session_id, participant_id, session_number, block_type, block_number, completed |
| `trials` | trial_id, session_id, trial_number, grid_type, planned_sequence, reaction_time_ms, … |
| `keypresses` | keypress_id, trial_id, key_pressed, cursor positions, timestamps |
| `reflections` | reflection_id, participant_id, session_number, imagery_content, perspective, modalities, engagement_score, next_session_goal |
