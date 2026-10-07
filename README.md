# AI-Powered Placement Job Fit & Skill Gap Analyzer

## Problem Statement

Placement organizations and individual candidates need a fast, objective way
to answer one question: **"How well does this candidate's resume and
skillset match this specific job, and what should they improve?"**

This project answers exactly that question — nothing more. It is explicitly
**not** a candidate ranking system, a recruiter shortlist tool, or a job
recommendation engine. It evaluates **one candidate against one selected
job** at a time.

## Objective

Given a job selected from a placement organization's job database and a
candidate's resume (PDF), the system:

1. Extracts resume text (with OCR fallback for scanned PDFs).
2. Extracts the candidate's skills using a controlled skill dictionary.
3. Compares candidate skills against the job's required skills.
4. Calculates skill match %, mandatory skill match %, and skill gaps.
5. Engineers ML features from the comparison + experience/projects/certifications.
6. Uses a trained ML classifier to predict a **selection probability**.
7. Produces a full Job Fit Analysis dashboard with matched/missing skills,
   charts, and a fit classification.
8. Generates rule-based improvement recommendations for skill gaps.

## Features

- Placement organization admin UI to add/edit/delete jobs and their
  required skills (level 1–5, mandatory flag, weight).
- PDF resume upload with automatic text extraction (PyMuPDF) and OCR
  fallback (Tesseract) for scanned resumes.
- Dictionary-based skill extraction with alias normalization
  (e.g. "sklearn" → "Scikit-learn").
- Editable candidate profile (name, email, phone, education, experience,
  skills with proficiency, projects, certifications).
- Deterministic skill gap analysis (required vs. candidate level).
- ML-based selection probability prediction (Logistic Regression, Decision
  Tree, Random Forest — XGBoost optional).
- Rule-based, prioritized skill-improvement recommendations.
- Visual dashboard: gauges, bar charts for skill levels/gaps, progress bars.
- Persistent prediction history per candidate (returning candidates keep
  one permanent Student ID).
- MySQL database for all persistent data.
- Optional AI-enhanced resume/profile extraction (Google Gemini API,
  free tier), with
  automatic fallback to the deterministic heuristic extractor.
- Optional import of real, live remote job postings (Remotive API, no
  key required) as a starting point for job management.

## Architecture

```
Placement Organization → Job Database → Select Job → Job Requirements
                                                            |
Candidate Resume (PDF) → PyMuPDF → [scanned?] → OCR (Tesseract) → Cleaned Text
                                                            |
                                                    Skill Extraction
                                                            |
                                                   Candidate Profile
                                                            |
                                        Candidate vs Job Comparison (deterministic)
                                          /                              \
                                Matched Skills                    Missing Skills
                                          \                              /
                                            Feature Engineering
                                                     |
                                          ML Prediction (selection probability)
                                                     |
                                          Final Job Fit Analysis
                                                     |
                                          Rule-Based Recommendations
```

**Key design rule:** Skill extraction, skill matching, gap calculation, and
match percentages are all **deterministic Python logic** — not ML. Machine
learning is used **only** for selection-probability prediction, because that
outcome depends on non-linear interactions between many factors that a
manual formula can't capture as reliably.

## Technology Stack

| Purpose                | Technology                                  |
|-------------------------|---------------------------------------------|
| UI                       | Streamlit                                    |
| Database                 | MySQL (via PyMySQL)                          |
| PDF text extraction      | PyMuPDF (fitz)                               |
| OCR fallback             | Tesseract (via pytesseract) + Pillow         |
| Data handling            | Pandas, NumPy                                |
| ML models                | scikit-learn (Logistic Regression, Decision Tree, Random Forest), optional XGBoost |
| Model persistence        | Joblib                                       |
| Charts                   | Plotly                                       |
| Live job postings        | Remotive public API (no key required)        |
| AI-enhanced extraction   | Google Gemini API, free tier (optional, off by default) |

No React/Angular/Vue, Java, AWS/Docker/Kubernetes, or JWT auth are used,
per project scope. The two external APIs above (live job postings and
AI-enhanced resume extraction) are both **optional, additive layers**:
the app runs fully without either configured, using the original
deterministic Remotive-free / LLM-free behavior as the fallback path.

## ML Pipeline

1. **`models/generate_dataset.py`** creates several thousand synthetic
   candidate-job feature rows. The `selected` target is generated from an
   internal (not user-facing) scoring function that rewards higher skill
   match, higher mandatory match, lower skill gaps, sufficient experience,
   more projects, and more certifications — plus random noise, so it is not
   perfectly deterministic.
2. **`models/train_model.py`** trains Logistic Regression, Decision Tree,
   and Random Forest (and XGBoost if installed), evaluates each with
   Accuracy, Precision, Recall, F1, and ROC-AUC on a held-out test split,
   and saves the best model (by ROC-AUC) plus a fitted `StandardScaler` via
   Joblib.
3. **`models/predict.py`** loads the saved model once per app session and
   exposes `predict_probability()` for live inference — the app never
   retrains on startup.

### Selection Probability Thresholds

| Range     | Classification   |
|-----------|------------------|
| 80–100%   | Excellent Fit    |
| 65–79%    | Good Fit         |
| 50–64%    | Moderate Fit     |
| 0–49%     | Low Fit          |

These thresholds are defined as a simple constant (`FIT_THRESHOLDS` in
`models/predict.py`) and easy to change.

> **Disclaimer shown in-app:** "Selection probability is an ML-based
> estimate based on the information analyzed by this system. It does not
> represent a guaranteed hiring outcome."

## Resume Processing Pipeline

```
PDF → is text extractable (PyMuPDF)?
    YES → extract_text_from_pdf()
    NO  → extract_text_with_ocr() [Tesseract]
        → clean_resume_text()
        → extract_skills() [dictionary-based]
        → extract_candidate_profile() [name, email, phone, education, experience, projects, certifications]
```

Tesseract OCR is used strictly as an off-the-shelf fallback for
scanned/image-based resumes — **no OCR model is trained** by this project.

## Database Design

MySQL tables: `students`, `skills`, `student_skills`, `jobs`, `job_skills`,
`projects`, `certifications`, `ml_predictions`, `recommendations` (see
`database/schema.py`; InnoDB engine, foreign keys enforced).

A student keeps **one permanent `student_id`** across visits — re-analyzing
with the same ID updates the existing record rather than creating a
duplicate (see `database/database.py: upsert_student`).

Connection settings live in `database/config.py` and are read from
environment variables (see **Database Setup** below) — no credentials are
hardcoded. `app.py` calls `init_database()` on first run, which creates the
target database (if missing) and all tables/indexes (if missing), so no
manual `CREATE DATABASE` step is required as long as the configured MySQL
user has permission to create databases.

## Live Job Postings (optional)

The **Placement Organization / Job Management** page has an
**🌐 Import Live Posting** tab that searches the free, keyless
[Remotive](https://remotive.com/api-documentation) API for real, currently
open remote jobs. Selecting one pre-fills the "Add Job" form (title,
company, description) and auto-suggests required skills by running the
same deterministic `skill_extractor.extract_skills()` used for resumes
against the posting's description — the admin still reviews/adjusts
suggested skills before creating the job, and can always add a job
manually instead. If the API is unreachable, the tab simply reports no
results; nothing else in the app is affected (see
`integrations/job_board_api.py`).

## AI-Enhanced Resume Extraction (optional)

The **Candidate Resume Analysis** page has an "✨ Enhance extraction with
AI" checkbox that, when a `GEMINI_API_KEY` is configured, sends the
cleaned resume text to Google's Gemini API (free tier — no credit card
required, get a key at https://aistudio.google.com/apikey) to extract
name/email/phone/education/experience/projects/certifications (see
`resume/llm_extractor.py`). This is **strictly an alternative path for
profile *fields*** — the candidate still reviews/edits everything
afterward, exactly as with the heuristic extractor. If the key isn't set,
the call fails, or the response can't be parsed, the app silently falls
back to the original heuristic extractor (`resume/profile_extractor.py`)
— the checkbox never breaks the flow.

**Skill detection and skill-gap scoring remain 100% deterministic
either way** — the LLM is never used to decide matched/missing skills or
selection probability, preserving the project's core design rule (see
"Key design rule" above).

## Skill Gap Methodology

For each required job skill:

```
gap = max(required_level - candidate_level, 0)
status = MATCHED if candidate_level >= required_level else GAP/MISSING
```

```
match_percentage = skills_matched / total_required_skills * 100
mandatory_match_percentage = mandatory_matched / mandatory_required * 100
```

A weighted match percentage (using each skill's configured weight) is also
computed and available in `analysis/skill_gap.py`.

## Recommendation Priority Rules

- **HIGH** — mandatory skill with gap ≥ 2
- **MEDIUM** — non-mandatory skill with gap ≥ 2, or mandatory skill with gap = 1
- **LOW** — small gap (1) on a non-mandatory skill

## Project Structure

```
placement_analyzer/
├── app.py                       # Streamlit entry point & navigation
├── database/
│   ├── database.py               # Connection + CRUD helpers
│   ├── schema.py                 # Table definitions
│   └── seed_data.py              # Sample jobs & skill dictionary seeding
├── models/
│   ├── generate_dataset.py       # Synthetic training data generator
│   ├── train_model.py            # Model training & comparison
│   ├── predict.py                # Inference wrapper (loads saved model)
│   ├── job_fit_model.joblib      # (generated) trained model bundle
│   └── model_metadata.joblib     # (generated) evaluation metrics
├── resume/
│   ├── resume_parser.py          # PyMuPDF + Tesseract OCR pipeline
│   ├── skill_extractor.py        # Dictionary-based skill extraction
│   └── profile_extractor.py      # Name/email/phone/education/projects/certs
├── analysis/
│   ├── skill_gap.py              # Deterministic skill comparison
│   ├── feature_engineering.py    # ML feature vector construction
│   └── recommendations.py        # Rule-based improvement suggestions
├── pages/
│   ├── jobs.py                   # Placement org job management UI
│   ├── candidate.py              # Resume upload & profile review UI
│   ├── analysis.py               # Job fit analysis dashboard
│   └── history.py                # Prediction history UI
├── utils/
│   └── paths.py                  # Centralized, project-safe file paths
├── data/
│   ├── skill_dictionary.json     # Editable controlled skill vocabulary
│   ├── training_dataset.csv      # (generated) synthetic dataset
│   └── placement.db              # (generated) SQLite database
├── requirements.txt
├── .gitignore
└── README.md
```

## How to Install

```bash
pip install -r requirements.txt
```

Tesseract must also be installed as a system binary for the OCR fallback to
work (it is optional — resumes with a real text layer work without it):

- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- macOS: `brew install tesseract`
- Windows: install from the [Tesseract UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)

## Database Setup (MySQL)

1. Make sure a MySQL server (5.7+/8.0+, or MariaDB) is running and
   reachable, and that you have a user with permission to create
   databases (or pre-create an empty `placement_analyzer` database and
   grant that user access to it).
2. Copy `.env.example` to `.env` and fill in your connection details:

   ```bash
   cp .env.example .env
   ```

   ```env
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=placement_analyzer
   ```

   (Plain environment variables work too if you'd rather not use a `.env`
   file — `database/config.py` reads from the environment either way.)
3. That's it — `streamlit run app.py` creates the database and all
   tables/indexes automatically on first run (see `database/database.py:
   init_database`). No manual schema step is required.

## Optional: AI-Enhanced Extraction Setup

To enable the "✨ Enhance extraction with AI" checkbox on the Candidate
page, get a free Gemini API key (no credit card required) at
https://aistudio.google.com/apikey, then add it to `.env`:

```env
GEMINI_API_KEY=AIza...
```

Leave it unset to keep using the standard heuristic extractor only — the
app works fully either way.

## How to Train the Model

```bash
python models/generate_dataset.py   # creates data/training_dataset.csv
python models/train_model.py        # trains & saves models/job_fit_model.joblib
```

## How to Run the Application

```bash
streamlit run app.py
```

The database and sample jobs are created and seeded automatically on first
run (`app.py` calls `init_database()` and `run_seed()`).

## How to Use the Application

1. Go to **Placement Organization / Job Management** to review or add jobs
   (8 sample jobs are seeded automatically).
2. Go to **Candidate Resume Analysis**:
   - Select a job.
   - Enter a Student ID (any unique value for a new candidate; your
     existing ID to update a previous profile).
   - Upload your resume PDF and click "Extract Resume".
   - Review and edit the extracted name, contact info, education,
     experience, skills (with confirmed proficiency 1–5), projects, and
     certifications, then save.
3. Go to **Job Fit Analysis**, select the job, and click "Analyze Job Fit"
   to see your skill match %, gaps, ML-predicted selection probability,
   fit classification, and improvement suggestions.
4. Go to **Prediction History** to review past analyses for your Student ID.

## Example Output

```
Overall Skill Match: 82%
Mandatory Skill Match: 90%
Selection Probability: 74%
Fit Classification: Good Fit

Matched Skills: Python, Pandas, NumPy, Scikit-learn, Machine Learning, TensorFlow
Missing Skills: SQL

Experience — Required: 1 year | Candidate: 0 years

Improvement Suggestions:
[HIGH] Improve SQL: focus on joins, aggregation, subqueries and database querying.
[MEDIUM] Gain practical project experience applying the missing skills above.
```

## Project Limitations

- Resume parsing (name/education/projects/certifications) is heuristic and
  may need manual correction for unusual resume layouts — this is why the
  UI always provides an edit step.
- Skill proficiency cannot be inferred from a PDF; it is always
  self-reported/confirmed by the candidate.
- The skill dictionary is controlled and finite; skills outside it are
  stored as free text but won't be auto-detected from resumes.
- The synthetic training dataset approximates realistic hiring patterns but
  is not derived from real placement outcome data.
- No authentication — this is a local prototype, not a production
  multi-tenant system.

## Future Improvements

- BERT-based Named Entity Recognition for more robust profile extraction.
- Sentence-Transformer–based semantic skill matching (e.g. matching
  "worked with neural networks" to "Deep Learning" without an exact
  keyword hit).
- Support for `.docx` resumes.
- XGBoost / deep learning selection model once more (real) training data
  is available.
- Direct links to learning resources per recommended skill.
- Cloud deployment and multi-user authentication for production use.
