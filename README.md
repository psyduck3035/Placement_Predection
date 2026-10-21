# Student Placement Prediction and Career Analysis

A Flask starter application with student profiles, adaptive-style aptitude assessment, webcam consent and face-presence monitoring, placement-readiness estimation, and career recommendations.

## Important model limitation
The included model is trained on **synthetic demonstration data** so the project runs out of the box. Its percentage is not a reliable real-world placement probability and must not be used for admissions, hiring, or other high-impact decisions. For a research-quality version, obtain permission to use representative historical student outcomes, document the label definition, evaluate on held-out cohorts, test calibration and subgroup performance, and display uncertainty.

## Features
- Registration/login with password hashing
- Student profile with academics, skills, projects, internships
- Timed, sectioned aptitude assessment
- Question ordering and basic difficulty adaptation in the browser
- Webcam permission and local face-presence checks using face-api.js
- Tab visibility/full-screen event logging; no webcam frames/video are uploaded or stored
- Placement-readiness estimate and career-role matching
- MySQL schema; SQLite fallback for quick demo

## Requirements
- Python 3.10 or later
- Modern browser
- Optional MySQL 8+

## Quick start (SQLite demo)
1. Extract the ZIP.
2. Open a terminal in the project folder.
3. Create and activate a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install packages: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and keep `USE_SQLITE_FALLBACK=1`.
6. Run: `python app.py`
7. Open `http://127.0.0.1:5000`
8. Register, sign in, save your profile, then take the test.

The first run trains and saves a synthetic-data model under `models/placement_model.pkl`. You can retrain it with `python ml_model.py`.

## MySQL setup
1. Start MySQL.
2. Run `schema.sql` in MySQL Workbench or the MySQL CLI.
3. Copy `.env.example` to `.env`, set `USE_SQLITE_FALLBACK=0`, and fill in `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`.
4. Install requirements and run `python app.py`.

## About the adaptive test
This starter chooses questions from different difficulty levels and adjusts the next question's difficulty from the previous answer. This is a simple demonstration, not a psychometrically validated adaptive assessment. Production adaptive tests need a sufficiently large, calibrated item bank and a documented scoring model.

## Webcam / AI proctoring
- The student sees a consent notice and must grant camera access.
- Face-presence checks run locally in the browser via face-api.js and its public model files. An internet connection is needed to fetch the library/model files the first time.
- The app stores only event types and timestamps, not photos, frames, or video.
- A missing face, multiple faces, browser tab change, or camera error is only a review signal; it does not automatically prove misconduct.
- Browser-based monitoring can be bypassed and should not be described as tamper-proof proctoring. Provide an accessible alternative for students who cannot use a camera.

## Folder layout
```
app.py
database.py
ml_model.py
schema.sql
requirements.txt
templates/
  base.html index.html register.html login.html dashboard.html profile.html test.html results.html
static/css/style.css
static/js/test.js
models/                 # generated on first run
```

## Next steps for a research/production version
- Replace synthetic data with approved, anonymized historical data.
- Define placement outcome and prediction horizon clearly.
- Use a time-based or cohort-based test split to reduce leakage.
- Evaluate ROC-AUC, precision/recall, calibration, and subgroup errors.
- Add admin-only aggregate reporting, audit logs, CSRF protection, rate limiting, password reset, secure cookies, and deployment hardening before production.


## Updated PathPilot AI features

- Registration and profile fields for university, stream, degree/programme, CGPA, backlogs, projects, internships, preferred role, coding, communication, SQL, web development and problem-solving self-ratings.
- Role-specific technical question sets alongside quantitative, logical and verbal aptitude questions.
- Consent and live webcam are required before assessment submission; camera images/video are not uploaded or stored by this demo.
- Every saved assessment has a browser-viewable report and a **Download complete PDF report** option. Reports include account and academic profile details, all skill ratings, assessment section scores, question-by-question answer review, role-readiness score, career matches/recommendations and proctoring review events.
- Assessment history is shown on the dashboard with links to view and download each report.

### Run locally

1. Use Python 3.10+ and create a virtual environment.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` if you want to change defaults. The default demo uses SQLite and creates `placement_demo.db` automatically.
4. Run `python app.py` and open `http://127.0.0.1:5000`.
5. Register, complete your profile, select a role, then start the assessment. Browser webcam permission is required for submission.

The included ML model is trained on synthetic demo data. Its placement percentage is not a validated hiring probability. Use real, representative, consented placement-history data and evaluate model quality before any real-world decisions.

## Resume ATS + progress roadmap update

- `/resume` adds a second-page style ATS resume workflow with PDF/DOCX/TXT upload.
- Resume text and the original file are saved under `uploads/resumes/` for the local demo; extracted skills, coding languages, strengths, 10th/12th percentages and ATS score are saved in the student profile.
- `/ats-analysis` shows ATS score, detected skills/languages/strengths, section checks and prioritized recommendations.
- `/compare-reports` now includes assessment history and previous-vs-current graphs, improvement cards, recommendations and a role roadmap link.
- `/career-roadmap/<role>` provides Foundation → Build → Job-ready stages and YouTube learning links for supported roles such as Data Analyst, Web Developer, Software Developer, UI/UX Designer and QA/Test Engineer.
- Install the added resume parsing dependencies from `requirements.txt` before running the updated project.

## Recent UI updates

- Dashboard now presents a three-step career journey: student profile, resume upload, and aptitude assessment.
- The assessment remains locked until the required profile fields are complete and a resume has been uploaded. Both the assessment page and assessment submission API enforce this gate.
- Assessment reports highlight incorrect answers in red and correct answers in green, including the student's selected answer and the correct answer.
- Dashboard cards, spacing, responsive behavior, focus states, and transitions have been refined for a cleaner and smoother interface.


## Render deployment (step-by-step)

1. Push this project folder to a GitHub repository.
2. On Render, choose **New + → Web Service** and connect the repository.
3. Set **Root Directory** to `student_placement_career_analysis` if the repository has this project inside that folder; otherwise leave it blank.
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Set environment variables: `SECRET_KEY` (unique secret), `USE_SQLITE_FALLBACK=1` for a quick temporary demo, and `FLASK_DEBUG=0`.
7. Deploy, open the `onrender.com` URL, register, then test the complete flow: **Save profile → Upload resume → Review ATS analysis → Start assessment → View/download report → Compare reports**.

### Database and uploaded files on Render
The SQLite database and uploaded resumes stored on a normal web-service filesystem may not persist across redeploys/restarts. For a durable deployment, use a managed MySQL database, set `USE_SQLITE_FALLBACK=0`, and provide `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`. Run `schema.sql` against that database. Add persistent storage for `uploads/resumes/` if original uploaded files must persist. Never use the development fallback secret in a public deployment.

### Notes
- Webcam access requires HTTPS; Render's generated HTTPS URL supports browser camera permissions.
- The placement prediction model uses synthetic demonstration data and must not be interpreted as a validated probability of hiring.
- The assessment question bank and adaptive behavior are demonstration features, not a validated psychometric instrument.

### Local Windows setup
```powershell
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```
Then open `http://127.0.0.1:5000`.


## Guided student workflow (latest)
1. Dashboard **Continue setup** opens the profile page whenever profile details are missing.
2. Saving the profile uses **Save profile & Next** and opens the resume upload page.
3. Uploading the resume saves it and opens the ATS analysis page.
4. The ATS analysis page offers **Save & Next · Start assessment**.
5. Assessment submission produces a report that combines academics, self-rated skills, ATS score, extracted resume skills/languages, and aptitude section scores. Role-match recommendations use skill alignment, ATS readiness, and detected resume keywords.


## Required profile fields
Every field in the profile form is mandatory, including the university, stream, degree, academic percentages, CGPA, backlog/project/internship counts, preferred role and all five skill ratings. The browser form uses `required`, and the Flask POST handler validates required values and numeric ranges server-side before saving. Values such as zero backlogs or zero internships remain valid when accurate.


## Mandatory profile validation fix
New profiles no longer receive prefilled values for university, CGPA, counts, or skill ratings. Stream, degree, and preferred-role dropdowns begin with a disabled placeholder. The server validates every required value, dropdown choice, numeric range, and whole-number-only field before writing to the database; browser-side `required` attributes are supplementary only. Tested the validation function for empty payloads, blank CGPA, blank skill ratings, invalid dropdown values, fractional counts, and a valid complete profile.
