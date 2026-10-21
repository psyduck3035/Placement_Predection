import os, json, random
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from database import init_db, get_db
from ml_model import load_model, predict_placement, career_recommendations
from resume_utils import allowed, extract_text, analyze_ats, detect_education

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-development-secret")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
RESUME_DIR = os.path.join(os.path.dirname(__file__), "uploads", "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)

# MySQL is used when configured; set USE_SQLITE_FALLBACK=1 for quick local demo.
init_db()
model_bundle = load_model()

@app.template_filter("from_json")
def from_json_filter(value):
    try:
        return json.loads(value or "[]") if isinstance(value, str) else (value or [])
    except Exception:
        return []



def profile_completion(profile):
    """Return (is_complete, missing_fields) for assessment access."""
    if not profile:
        return False, ["Complete your student profile"]
    checks = [
        ("university", "University name"),
        ("stream", "Faculty / stream"),
        ("degree", "Degree / programme"),
        ("tenth_percentage", "10th / SSC percentage"),
        ("twelfth_percentage", "12th / HSC percentage"),
        ("cgpa", "CGPA"),
        ("backlogs", "Active backlogs"),
        ("projects", "Projects completed"),
        ("internships", "Internships completed"),
        ("coding", "Coding / programming skill"),
        ("communication", "Communication skill"),
        ("sql", "SQL / databases skill"),
        ("web", "Web development skill"),
        ("problem_solving", "Problem solving skill"),
        ("preferred_role", "Preferred role"),
    ]
    missing = []
    for key, label in checks:
        value = profile.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(label)
    return not missing, missing


@app.context_processor
def inject_profile_status():
    if not session.get("user_id"):
        return {"profile_complete": False, "profile_missing": [], "resume_uploaded": False, "assessment_ready": False}
    try:
        db = get_db()
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if profile and "sql_score" in profile:
            profile["sql"] = profile["sql_score"]
        complete, missing = profile_completion(profile)
        resume_uploaded = bool(profile and profile.get("resume_filename"))
        return {
            "profile_complete": complete,
            "profile_missing": missing,
            "resume_uploaded": resume_uploaded,
            "assessment_ready": complete and resume_uploaded,
        }
    except Exception:
        return {"profile_complete": False, "profile_missing": ["Complete your profile"], "resume_uploaded": False, "assessment_ready": False}
    finally:
        try:
            db.close()
        except Exception:
            pass

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email, and a password of at least 8 characters.", "error")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users (name,email,password_hash,created_at) VALUES (%s,%s,%s,%s)",
                       (name, email, generate_password_hash(password), datetime.utcnow().isoformat()))
            new_user = db.execute("SELECT id FROM users WHERE email=%s", (email,)).fetchone()
            university = request.form.get("university", "University of Mumbai").strip()[:190]
            stream = request.form.get("stream", "Science").strip()[:100]
            degree = request.form.get("degree", "B.Sc. Computer Science").strip()[:100]
            sql_col = "sql_score" if os.getenv("USE_SQLITE_FALLBACK", "1") != "1" else "sql"
            db.execute(f"INSERT INTO student_profiles (user_id,university,stream,degree) VALUES (%s,%s,%s,%s)", (new_user["id"], university, stream, degree))
            db.commit()
            flash("Account created. Please sign in.", "success")
            return redirect(url_for("login"))
        except Exception:
            db.rollback()
            flash("Could not create account. That email may already be registered.", "error")
        finally:
            db.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        try:
            row = db.execute("SELECT id,name,email,password_hash FROM users WHERE email=%s", (email,)).fetchone()
        finally:
            db.close()
        if row and check_password_hash(row["password_hash"], password):
            session["user_id"], session["name"], session["email"] = row["id"], row["name"], row["email"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    try:
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if profile and "sql_score" in profile:
            profile["sql"] = profile["sql_score"]
        results = db.execute("SELECT id, aptitude_score, predicted_probability, predicted_label, created_at FROM assessments WHERE user_id=%s ORDER BY id DESC", (session["user_id"],)).fetchall()
    finally:
        db.close()
    return render_template("dashboard.html", profile=profile, results=results)

def validate_profile_form(form):
    """Server-side validation; never rely only on HTML required attributes."""
    required = {
        "university": "University name", "stream": "Faculty / stream",
        "degree": "Degree / programme", "tenth_percentage": "10th / SSC percentage",
        "twelfth_percentage": "12th / HSC percentage", "cgpa": "CGPA",
        "backlogs": "Active backlogs", "projects": "Projects completed",
        "internships": "Internships completed", "coding": "Coding / programming skill",
        "communication": "Communication skill", "sql": "SQL / databases skill",
        "web": "Web development skill", "problem_solving": "Problem solving skill",
        "preferred_role": "Preferred role",
    }
    missing = [label for key, label in required.items() if not str(form.get(key, "")).strip()]
    if missing:
        return ["Please complete all required profile fields: " + ", ".join(missing)]

    choices = {
        "stream": {"Science", "Commerce", "Arts", "Engineering & Technology", "Management", "Other"},
        "degree": {"B.Sc. Computer Science", "B.Sc. Information Technology", "B.Sc. Data Science",
                   "B.Sc. Biotechnology", "B.Sc. Microbiology", "B.Sc. Physics", "B.Sc. Chemistry",
                   "B.Sc. Mathematics", "B.Sc. Statistics", "B.Sc. Life Sciences", "B.Sc. Electronics",
                   "B.Sc. Environmental Science", "B.Sc. Botany", "B.Sc. Zoology", "B.Sc. Geology",
                   "B.Sc. Bioinformatics", "B.Sc. Forensic Science", "Other Science programme",
                   "BCA", "B.E. / B.Tech", "Other"},
        "preferred_role": {"Software Developer", "Data Analyst", "Data Scientist / ML Engineer",
                           "Web Developer", "Cybersecurity Analyst", "Database Administrator",
                           "QA / Test Engineer", "Business Analyst", "UI/UX Designer",
                           "Network Engineer", "Cloud / DevOps Engineer", "ERP Consultant"},
    }
    labels = {"stream": "Faculty / stream", "degree": "Degree / programme", "preferred_role": "Preferred role"}
    invalid_choices = [labels[k] for k, allowed in choices.items() if form.get(k, "").strip() not in allowed]
    if invalid_choices:
        return ["Please select a valid value for: " + ", ".join(invalid_choices)]

    ranges = {
        "tenth_percentage": (0, 100, "10th / SSC percentage"),
        "twelfth_percentage": (0, 100, "12th / HSC percentage"),
        "cgpa": (0, 10, "CGPA"),
        "backlogs": (0, 30, "Active backlogs"),
        "projects": (0, 30, "Projects completed"),
        "internships": (0, 20, "Internships completed"),
        "coding": (0, 100, "Coding / programming skill"),
        "communication": (0, 100, "Communication skill"),
        "sql": (0, 100, "SQL / databases skill"),
        "web": (0, 100, "Web development skill"),
        "problem_solving": (0, 100, "Problem solving skill"),
    }
    integers = {"backlogs", "projects", "internships", "coding", "communication", "sql", "web", "problem_solving"}
    invalid = []
    for key, (low, high, label) in ranges.items():
        try:
            raw = str(form.get(key, "")).strip()
            number = float(raw)
            if number < low or number > high:
                invalid.append(f"{label} must be between {low} and {high}")
            elif key in integers and not number.is_integer():
                invalid.append(f"{label} must be a whole number")
        except (TypeError, ValueError):
            invalid.append(f"{label} must be a valid number")
    return ["Please correct the following fields: " + "; ".join(invalid)] if invalid else []


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    try:
        current = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if current and "sql_score" in current:
            current["sql"] = current["sql_score"]
        if request.method == "POST":
            validation_errors = validate_profile_form(request.form)
            if validation_errors:
                for error in validation_errors:
                    flash(error, "error")
                return render_template("profile.html", profile=current), 400

            values = {
                "university": request.form.get("university", "University of Mumbai").strip()[:190],
                "stream": request.form.get("stream", "Science").strip()[:100],
                "degree": request.form.get("degree", "B.Sc. Computer Science").strip()[:100],
                "tenth_percentage": safe_float(request.form.get("tenth_percentage"), 0, 100),
                "twelfth_percentage": safe_float(request.form.get("twelfth_percentage"), 0, 100),
                "cgpa": safe_float(request.form.get("cgpa"), 0, 10),
                "backlogs": safe_int(request.form.get("backlogs"), 0, 30),
                "projects": safe_int(request.form.get("projects"), 0, 30),
                "internships": safe_int(request.form.get("internships"), 0, 20),
                "coding": safe_int(request.form.get("coding"), 0, 100),
                "communication": safe_int(request.form.get("communication"), 0, 100),
                "sql": safe_int(request.form.get("sql"), 0, 100),
                "web": safe_int(request.form.get("web"), 0, 100),
                "problem_solving": safe_int(request.form.get("problem_solving"), 0, 100),
                "preferred_role": request.form.get("preferred_role", "Data Analyst"),
            }
            if current:
                sql_col = "sql_score" if os.getenv("USE_SQLITE_FALLBACK", "1") != "1" else "sql"
                db.execute(f"""UPDATE student_profiles SET university=%s,stream=%s,degree=%s,tenth_percentage=%s,twelfth_percentage=%s,cgpa=%s,backlogs=%s,projects=%s,internships=%s,
                    coding=%s,communication=%s,{sql_col}=%s,web=%s,problem_solving=%s,preferred_role=%s WHERE user_id=%s""",
                    (*values.values(), session["user_id"]))
            else:
                sql_col = "sql_score" if os.getenv("USE_SQLITE_FALLBACK", "1") != "1" else "sql"
                db.execute(f"""INSERT INTO student_profiles
                    (user_id,university,stream,degree,tenth_percentage,twelfth_percentage,cgpa,backlogs,projects,internships,coding,communication,{sql_col},web,problem_solving,preferred_role)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (session["user_id"], *values.values()))
            db.commit()
            flash("Profile saved. Next, upload your resume and review its ATS analysis.", "success")
            return redirect(url_for("resume"))
        return render_template("profile.html", profile=current)
    finally:
        db.close()

@app.route("/resume", methods=["GET", "POST"])
@login_required
def resume():
    db = get_db()
    try:
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if not profile:
            flash("Complete and save your student profile before uploading a resume.", "error")
            return redirect(url_for("profile"))
        profile_complete, profile_missing = profile_completion(profile)
        if not profile_complete:
            flash("Complete and save your profile before uploading your resume.", "error")
            return redirect(url_for("profile"))
        if request.method == "POST":
            upload = request.files.get("resume")
            if not upload or not upload.filename:
                flash("Choose a PDF, DOCX or TXT resume first.", "error")
                return redirect(url_for("resume"))
            if not allowed(upload.filename):
                flash("Only PDF, DOCX and TXT resumes are supported.", "error")
                return redirect(url_for("resume"))
            try:
                raw_resume = upload.read()
                upload.stream.seek(0)
                text = extract_text(upload)
            except Exception as exc:
                flash(f"Could not read the resume: {exc}", "error")
                return redirect(url_for("resume"))
            if not text.strip():
                flash("The resume appears empty or scanned. Please upload a text-readable PDF/DOCX.", "error")
                return redirect(url_for("resume"))
            role = profile.get("preferred_role", "Data Analyst") if profile else "Data Analyst"
            analysis = analyze_ats(text, role)
            tenth, twelfth = detect_education(text)
            safe_name = secure_resume_name(upload.filename, session["user_id"])
            # Re-open the file from request is not possible after extract_text consumed it, so save the extracted text as the searchable copy.
            ext = upload.filename.rsplit(".", 1)[1].lower()
            original_path = os.path.join(RESUME_DIR, safe_name + "." + ext)
            with open(original_path, "wb") as f: f.write(raw_resume)
            text_path = os.path.join(RESUME_DIR, safe_name + ".txt")
            with open(text_path, "w", encoding="utf-8") as f: f.write(text[:200000])
            if profile:
                db.execute("""UPDATE student_profiles SET resume_filename=%s,resume_text=%s,resume_skills=%s,coding_languages=%s,resume_strengths=%s,ats_score=%s,
                    tenth_percentage=CASE WHEN %s > 0 THEN %s ELSE tenth_percentage END,
                    twelfth_percentage=CASE WHEN %s > 0 THEN %s ELSE twelfth_percentage END WHERE user_id=%s""",
                    (upload.filename[:255], text[:200000], json.dumps(analysis["skills"]), json.dumps(analysis["languages"]), json.dumps(analysis["strengths"]), analysis["score"], tenth or 0, tenth or 0, twelfth or 0, twelfth or 0, session["user_id"]))
                db.commit()
            flash("Resume saved and analyzed. Review the ATS score, then continue to your assessment.", "success")
            return redirect(url_for("ats_analysis"))
        if profile and "sql_score" in profile: profile["sql"] = profile["sql_score"]
        return render_template("resume.html", profile=profile)
    finally:
        db.close()

def secure_resume_name(filename, user_id):
    from werkzeug.utils import secure_filename
    base = secure_filename(filename).rsplit(".",1)[0] or "resume"
    return f"user_{user_id}_{base[:100]}"

@app.route("/ats-analysis")
@login_required
def ats_analysis():
    db = get_db()
    try:
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if not profile or not profile.get("resume_text"):
            flash("Upload your resume first to generate an ATS analysis.", "error")
            return redirect(url_for("resume"))
        analysis = analyze_ats(profile.get("resume_text", ""), profile.get("preferred_role", "Data Analyst"))
        return render_template("ats_analysis.html", profile=profile, analysis=analysis)
    finally:
        db.close()

@app.route("/career-roadmap/<path:role>")
@login_required
def career_roadmap(role):
    roadmaps = {
      "Data Analyst": [("Foundation", ["Excel formulas & pivot tables", "SQL SELECT, JOIN, GROUP BY", "Statistics basics"]),("Build", ["Python + Pandas", "Power BI dashboards", "3 portfolio projects"]),("Job ready", ["Advanced SQL + DAX", "Case-study practice", "Resume + interview preparation"])],
      "Web Developer": [("Foundation", ["HTML + semantic CSS", "JavaScript fundamentals", "Git & GitHub"]),("Build", ["Responsive UI", "REST APIs", "Database integration"]),("Job ready", ["React or Flask", "Deploy a full-stack project", "DSA + interview practice"])],
      "Software Developer": [("Foundation", ["Programming fundamentals", "OOP", "Git"]),("Build", ["Data structures & algorithms", "SQL", "Backend/API project"]),("Job ready", ["Testing", "System design basics", "Interview projects"])],
      "UI/UX Designer": [("Foundation", ["Design principles", "Typography & color", "Figma"]),("Build", ["Wireframes", "Prototypes", "Usability testing"]),("Job ready", ["Case studies", "Portfolio", "Design interview practice"])],
      "QA / Test Engineer": [("Foundation", ["STLC", "Test cases", "SQL"]),("Build", ["API testing", "Selenium", "JMeter"]),("Job ready", ["Automation framework", "Bug reporting", "Interview practice"])],
    }
    roadmap = roadmaps.get(role, roadmaps["Data Analyst"])
    youtube = {
      "Data Analyst":["https://www.youtube.com/results?search_query=SQL+for+data+analysts","https://www.youtube.com/results?search_query=Power+BI+beginner+tutorial","https://www.youtube.com/results?search_query=Python+Pandas+data+analysis"],
      "Web Developer":["https://www.youtube.com/results?search_query=HTML+CSS+JavaScript+full+course","https://www.youtube.com/results?search_query=React+beginner+course","https://www.youtube.com/results?search_query=REST+API+Flask"],
      "Software Developer":["https://www.youtube.com/results?search_query=data+structures+algorithms+beginner","https://www.youtube.com/results?search_query=Java+OOP+course","https://www.youtube.com/results?search_query=software+developer+interview+preparation"],
      "UI/UX Designer":["https://www.youtube.com/results?search_query=Figma+UI+UX+course","https://www.youtube.com/results?search_query=UX+case+study+tutorial","https://www.youtube.com/results?search_query=design+portfolio+tips"],
      "QA / Test Engineer":["https://www.youtube.com/results?search_query=manual+testing+STLC","https://www.youtube.com/results?search_query=Selenium+Python+course","https://www.youtube.com/results?search_query=API+testing+Postman+course"],
    }.get(role, [])
    return render_template("roadmap.html", role=role, roadmap=roadmap, youtube=youtube)

@app.route("/test")
@login_required
def test():
    # Questions are authored in-app for demonstration. Production questions should be reviewed and validated.
    db = get_db()
    try:
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if profile and "sql_score" in profile: profile["sql"] = profile["sql_score"]
    finally: db.close()
    complete, missing = profile_completion(profile)
    if not complete:
        flash("Complete all profile details before starting the assessment. Missing: " + ", ".join(missing), "error")
        return redirect(url_for("profile"))
    if not profile or not profile.get("resume_filename"):
        flash("Upload your resume and review the ATS analysis before starting the assessment.", "error")
        return redirect(url_for("resume"))
    questions = get_role_questions(profile.get("preferred_role", "Software Developer"))
    return render_template("test.html", questions=questions, user_name=session.get("name", "Student"), profile=profile)

@app.route("/api/submit-assessment", methods=["POST"])
@login_required
def submit_assessment():
    payload = request.get_json(silent=True) or {}
    db = get_db()
    try:
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
    finally:
        db.close()
    complete, missing = profile_completion(profile)
    if not complete:
        return jsonify({"error": "Complete your profile before submitting the assessment.", "missing": missing}), 403
    if not profile or not profile.get("resume_filename"):
        return jsonify({"error": "Upload your resume before submitting the assessment."}), 403
    answers = payload.get("answers", {})
    events = payload.get("events", [])
    consent = payload.get("proctoringConsent") is True
    camera_enabled = payload.get("cameraEnabled") is True
    if not consent:
        return jsonify({"error": "Please confirm consent before submitting the proctored assessment."}), 400
    if not camera_enabled:
        return jsonify({"error": "Enable the webcam and wait for the camera-ready confirmation before submitting."}), 400

    db = get_db()
    try:
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if profile and "sql_score" in profile:
            profile["sql"] = profile["sql_score"]
        if not profile:
            return jsonify({"error": "Please complete your student profile before taking the assessment."}), 400
        questions = {q["id"]: q for q in get_role_questions(profile.get("preferred_role", "Software Developer"))}
        scored = {"quantitative": [0,0], "logical": [0,0], "verbal": [0,0], "technical": [0,0], "data": [0,0]}
        for qid, answer in answers.items():
            q = questions.get(str(qid))
            if q:
                scored[q["section"]][1] += 1
                if str(answer) == str(q["answer"]):
                    scored[q["section"]][0] += 1
        section_scores = {k: round((v[0]/v[1])*100) if v[1] else 0 for k,v in scored.items()}
        answer_details = []
        for qid, q in questions.items():
            answer = answers.get(qid)
            try: selected = q["options"][int(answer)] if answer is not None else "Not answered"
            except (ValueError, IndexError, TypeError): selected = "Invalid option"
            try: correct = q["options"][int(q["answer"])]
            except (ValueError, IndexError, TypeError): correct = "Not available"
            answer_details.append({"question": q["text"], "section": q["section"], "selected": selected, "correct": correct, "is_correct": answer is not None and str(answer) == str(q["answer"])})
        total_answered = sum(v[1] for v in scored.values())
        total_correct = sum(v[0] for v in scored.values())
        aptitude_score = round((total_correct / max(1, total_answered)) * 100)
        # A test score is an assessment feature, not a guarantee or a hiring decision.
        features = {
            "cgpa": float(profile["cgpa"]), "backlogs": int(profile["backlogs"]),
            "projects": int(profile["projects"]), "internships": int(profile["internships"]),
            "coding": int(profile["coding"]), "communication": int(profile["communication"]),
            "sql": int(profile["sql"]), "web": int(profile["web"]),
            "problem_solving": int(profile.get("problem_solving", 0)),
            "quantitative": section_scores["quantitative"], "logical": section_scores["logical"],
            "verbal": section_scores["verbal"], "technical": section_scores["technical"],
            "data": section_scores["data"], "aptitude_score": aptitude_score,
            "ats_score": int(profile.get("ats_score") or 0),
            "resume_skills": profile.get("resume_skills", "[]"),
            "coding_languages": profile.get("coding_languages", "[]"),
            "resume_strengths": profile.get("resume_strengths", "[]"),
            "tenth_percentage": float(profile.get("tenth_percentage") or 0),
            "twelfth_percentage": float(profile.get("twelfth_percentage") or 0),
        }
        prediction = predict_placement(model_bundle, features)
        # Role readiness is a transparent skill/assessment score, distinct from a hiring probability.
        role = profile.get("preferred_role", "Software Developer")
        technical_signal = features["technical"] if role in ("Software Developer", "Web Developer", "QA / Test Engineer", "Cybersecurity Analyst", "Cloud / DevOps Engineer") else features["data"]
        readiness = round(0.23 * aptitude_score + 0.18 * features["coding"] + 0.13 * features["communication"] + 0.13 * features["problem_solving"] + 0.13 * technical_signal + 0.10 * min(100, features["cgpa"] * 10) + 0.10 * features["ats_score"])
        readiness_label = "Job-ready foundation" if readiness >= 80 else "Developing" if readiness >= 60 else "Needs focused preparation"
        features.update({"university": profile.get("university", ""), "stream": profile.get("stream", ""), "degree": profile.get("degree", ""), "preferred_role": role, "readiness_score": readiness, "readiness_label": readiness_label, "answered_count": total_answered, "correct_count": total_correct, "answer_details": answer_details})
        careers = career_recommendations(features)
        # Keep only event types/counts; never store webcam images or video.
        safe_events = []
        allowed = {"tab_hidden", "fullscreen_exit", "camera_unavailable", "face_not_detected", "multiple_faces_detected"}
        for event in events[:100]:
            if isinstance(event, dict) and event.get("type") in allowed:
                safe_events.append({"type": event["type"], "at": str(event.get("at", ""))[:40]})
        cursor = db.execute("""INSERT INTO assessments
          (user_id, aptitude_score, section_scores, features_json, predicted_probability, predicted_label, proctor_events, created_at)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
          (session["user_id"], aptitude_score, json.dumps(section_scores), json.dumps(features),
           prediction["probability"], prediction["label"], json.dumps(safe_events), datetime.utcnow().isoformat()))
        assessment_id = getattr(cursor, "lastrowid", None)
        db.commit()
        return jsonify({"ok": True, "assessment_id": assessment_id, "aptitude_score": aptitude_score,
                        "section_scores": section_scores, "prediction": prediction, "readiness_score": readiness, "readiness_label": readiness_label, "careers": careers,
                        "proctor_event_count": len(safe_events),
                        "note": "Demo model estimate only. Validate with representative historical placement data before real-world use."})
    finally:
        db.close()

@app.route("/results/<int:assessment_id>")
@login_required
def results(assessment_id):
    db = get_db()
    try:
        row = db.execute("SELECT * FROM assessments WHERE id=%s AND user_id=%s",
                         (assessment_id, session["user_id"])).fetchone()
        if not row:
            flash("Assessment result not found.", "error")
            return redirect(url_for("dashboard"))
        features = json.loads(row["features_json"])
        user = db.execute("SELECT name,email,created_at FROM users WHERE id=%s", (session["user_id"],)).fetchone()
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if profile and "sql_score" in profile: profile["sql"] = profile["sql_score"]
        return render_template("results.html", result=row, user=user, profile=profile,
            section_scores=json.loads(row["section_scores"]), features=features,
            careers=career_recommendations(features), proctor_events=json.loads(row["proctor_events"]))
    finally:
        db.close()

@app.route("/compare-reports")
@login_required
def compare_reports():
    """Compare the most recent assessment with the previous assessment for this user."""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM assessments WHERE user_id=%s ORDER BY id DESC LIMIT 2", (session["user_id"],)).fetchall()
        if len(rows) < 2:
            flash("Complete at least two assessments to compare your previous and current reports.", "error")
            return redirect(url_for("dashboard"))
        current, previous = rows[0], rows[1]
        current_sections = json.loads(current["section_scores"] or "{}")
        previous_sections = json.loads(previous["section_scores"] or "{}")
        current_features = json.loads(current["features_json"] or "{}")
        previous_features = json.loads(previous["features_json"] or "{}")
        keys = sorted(set(current_sections) | set(previous_sections))
        section_comparison = [{"name": key.replace("_", " ").title(),
            "previous": float(previous_sections.get(key, 0) or 0),
            "current": float(current_sections.get(key, 0) or 0),
            "change": float(current_sections.get(key, 0) or 0) - float(previous_sections.get(key, 0) or 0)} for key in keys]
        metrics = [
            {"name": "Overall aptitude score", "previous": float(previous["aptitude_score"] or 0), "current": float(current["aptitude_score"] or 0)},
            {"name": "Role readiness", "previous": float(previous_features.get("readiness_score", 0) or 0), "current": float(current_features.get("readiness_score", 0) or 0)},
            {"name": "Correct answers", "previous": float(previous_features.get("correct_count", 0) or 0), "current": float(current_features.get("correct_count", 0) or 0)},
        ]
        for metric in metrics:
            metric["change"] = metric["current"] - metric["previous"]
        user = db.execute("SELECT name,email FROM users WHERE id=%s", (session["user_id"],)).fetchone()
        profile = db.execute("SELECT preferred_role FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        all_rows = db.execute("SELECT id,aptitude_score,section_scores,features_json,created_at FROM assessments WHERE user_id=%s ORDER BY id ASC", (session["user_id"],)).fetchall()
        trend = []
        for r in all_rows:
            f = json.loads(r["features_json"] or "{}")
            trend.append({"label": r["created_at"][:10], "aptitude": float(r["aptitude_score"] or 0), "readiness": float(f.get("readiness_score",0) or 0)})
        improvements = sorted(section_comparison, key=lambda x: x["change"], reverse=True)
        return render_template("compare_reports.html", user=user, current=current, previous=previous,
            metrics=metrics, section_comparison=section_comparison,
            current_features=current_features, previous_features=previous_features, trend=trend,
            improvements=improvements, preferred_role=(profile or {}).get("preferred_role","Data Analyst"))
    finally:
        db.close()

@app.route("/results/<int:assessment_id>/download")
@login_required
def download_report(assessment_id):
    """Download a detailed PDF report for an assessment owned by the signed-in user."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape
    db = get_db()
    try:
        row = db.execute("SELECT * FROM assessments WHERE id=%s AND user_id=%s", (assessment_id, session["user_id"])).fetchone()
        if not row:
            flash("Report not found.", "error"); return redirect(url_for("dashboard"))
        user = db.execute("SELECT name,email,created_at FROM users WHERE id=%s", (session["user_id"],)).fetchone()
        profile = db.execute("SELECT * FROM student_profiles WHERE user_id=%s", (session["user_id"],)).fetchone()
        if profile and "sql_score" in profile: profile["sql"] = profile["sql_score"]
    finally: db.close()
    features = json.loads(row["features_json"]); sections = json.loads(row["section_scores"]); events = json.loads(row["proctor_events"])
    buf = BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet(); styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#126b4f"), spaceAfter=12))
    styles.add(ParagraphStyle(name="SectionHead", parent=styles["Heading2"], textColor=colors.HexColor("#126b4f"), spaceBefore=12, spaceAfter=6))
    story = [Paragraph("PathPilot AI", styles["ReportTitle"]), Paragraph("Student Profile & Assessment Report", styles["Heading1"]),
      Paragraph("Generated: " + datetime.now().strftime("%d %b %Y, %I:%M %p"), styles["Normal"]), Spacer(1, 10)]
    def section(title, rows):
        story.append(Paragraph(title, styles["SectionHead"]))
        data = [[Paragraph("<b>Field</b>", styles["BodyText"]), Paragraph("<b>Details</b>", styles["BodyText"])]]
        for k,v in rows:
            data.append([Paragraph(escape(str(k)), styles["BodyText"]), Paragraph(escape(str(v if v not in (None, "") else "Not provided")), styles["BodyText"])])
        table = Table(data, colWidths=[150, 330], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8f4ef")),("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d5e2dc")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story.append(table)
    section("Student account", [("Full name", user["name"]), ("Email", user["email"]), ("Account created", user["created_at"])])
    section("Academic profile", [("University", profile.get("university")), ("Stream", profile.get("stream")), ("Degree / programme", profile.get("degree")), ("CGPA", str(profile.get("cgpa"))+" / 10"), ("Active backlogs", profile.get("backlogs")), ("Projects completed", profile.get("projects")), ("Internships completed", profile.get("internships")), ("Preferred role", profile.get("preferred_role"))])
    section("Self-rated skills", [("Coding / programming", str(profile.get("coding"))+" / 100"), ("Communication", str(profile.get("communication"))+" / 100"), ("SQL / databases", str(profile.get("sql"))+" / 100"), ("Web development", str(profile.get("web"))+" / 100"), ("Problem solving", str(profile.get("problem_solving",0))+" / 100")])
    section("Assessment summary", [("Assessment ID", row["id"]), ("Date", row["created_at"]), ("Target role", features.get("preferred_role", profile.get("preferred_role"))), ("Overall aptitude score", str(row["aptitude_score"])+" / 100"), ("Questions answered", features.get("answered_count", "Not available")), ("Correct answers", features.get("correct_count", "Not available")), ("Role readiness", str(features.get("readiness_score", "Not calculated"))+" / 100 - "+str(features.get("readiness_label", ""))), ("Model estimate", str(round(float(row["predicted_probability"])*100))+"% (synthetic-demo model only)"), ("Readiness label", row["predicted_label"])])
    section("Section scores", [(k.replace("_"," ").title(), str(v)+" / 100") for k,v in sections.items()])
    section("Assessment profile signals", [(k.replace("_"," ").title(), v) for k,v in features.items() if k not in sections and k not in ("university","stream","degree","preferred_role","readiness_label","readiness_score","answer_details","answered_count","correct_count")])
    careers = career_recommendations(features)
    section("Career matches and recommendations", [(c["role"], str(c["match_score"])+"/100 skill alignment; Recommendations: " + ", ".join(c["recommendations"])) for c in careers])
    section("Question-by-question review", [(f"Q{i}. {a.get('question','')}", "Your answer: " + str(a.get("selected")) + "; Correct answer: " + str(a.get("correct")) + "; Result: " + ("Correct" if a.get("is_correct") else "Incorrect")) for i,a in enumerate(features.get("answer_details", []), 1)] or [("Question review", "No answer details available")])
    section("Proctoring events", [("Recorded event count", len(events)), ("Event details", ", ".join(e.get("type", "event")+" at "+e.get("at", "") for e in events) if events else "No review events recorded")])
    story += [Spacer(1, 12), Paragraph("Interpretation and limitations", styles["SectionHead"]), Paragraph("This report is an educational readiness aid, not a hiring decision or guarantee. The included placement model is trained on synthetic demonstration data; its percentage is not a validated probability of employment. Readiness is a transparent score based on profile and assessment inputs. Review results alongside interviews, projects, eligibility rules and actual placement data.", styles["BodyText"])]
    doc.build(story); response = make_response(buf.getvalue()); response.headers["Content-Type"] = "application/pdf"; response.headers["Content-Disposition"] = f"attachment; filename=PathPilot_Assessment_Report_{assessment_id}.pdf"; return response

def safe_float(value, minimum, maximum):
    try: return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError): return minimum

def safe_int(value, minimum, maximum):
    try: return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError): return minimum

ROLE_TOPICS = {
 "Software Developer": ("technical", [
  ("Which data structure follows FIFO order?", ["Stack","Queue","Tree","Graph"], "1"),
  ("Typical binary-search complexity on a sorted array?", ["O(1)","O(log n)","O(n)","O(n²)"], "1"),
  ("OOP encapsulation primarily means:", ["Bundling data and methods with controlled access","Running code in parallel","Sorting objects","Compiling code"], "0")]),
 "Data Analyst": ("data", [("Which SQL clause filters rows before grouping?",["ORDER BY","HAVING","WHERE","GROUP BY"],"2"),("Median of 4, 6, 6, 8, 11?",["4","6","7","8"],"1"),("A metric rises from 40 to 50. Increase?",["10%","20%","25%","30%"],"2")]),
 "Data Scientist / ML Engineer": ("data", [("Which method is commonly used for classification?",["Logistic regression","Linear search","HTML","Normalization only"],"0"),("What does overfitting mean?",["Model fits training data too closely","Data is always missing","Model has no features","Training is skipped"],"0"),("Which measure summarizes the middle value?",["Mean only","Median","Range","Variance"],"1")]),
 "Web Developer": ("technical", [("Which language adds interactivity in the browser?",["SQL","JavaScript","CSV","Bash only"],"1"),("What does HTTP status 404 mean?",["Success","Unauthorized","Not found","Server created"],"2"),("Which CSS layout is one-dimensional?",["Flexbox","SQL","DOM","JSON"],"0")]),
 "QA / Test Engineer": ("technical", [("What is a test case?",["Steps and expected result to verify behavior","A production server","A design color","A database password"],"0"),("A defect is found. What should a good bug report include?",["Only the tester name","Steps, expected/actual result and evidence","Only a screenshot","No details"],"1"),("Which test checks a small unit in isolation?",["Unit test","Acceptance only","Load test only","Exploratory only"],"0")]),
 "Cybersecurity Analyst": ("technical", [("What does MFA add?",["Multiple verification factors","More bandwidth","A backup database","A new browser"],"0"),("Which is a sign of phishing?",["Expected internal link","Urgent request with suspicious link","Known bookmark","Signed company update"],"1"),("Principle of least privilege means:",["Give only needed access","Give everyone admin","Disable passwords","Share accounts"],"0")]),
 "Database Administrator": ("technical", [("Which SQL command retrieves rows?",["SELECT","DROP","GRANT","COMMIT"],"0"),("Normalization mainly helps reduce:",["Redundancy and anomalies","Network speed","User accounts","Indexes always"],"0"),("Which clause sorts results?",["ORDER BY","WHERE","JOIN","HAVING"],"0")]),
 "Business Analyst": ("data", [("A requirement should be:",["Clear and testable","Vague","Hidden","Unapproved"],"0"),("Which tool commonly visualizes processes?",["Flowchart","Compiler","Firewall","Router"],"0"),("Stakeholder analysis identifies:",["People affected by a project","Only source code","Only bugs","Network ports"],"0")]),
 "UI/UX Designer": ("technical", [("A wireframe is primarily used to:",["Plan interface structure","Store passwords","Train a model","Route packets"],"0"),("Usability testing observes:",["How users complete tasks","Only server uptime","Code compilation","Database indexes"],"0"),("Accessibility helps make products usable by:",["People with varied abilities","Only developers","Only administrators","Only one browser"],"0")]),
 "Network Engineer": ("technical", [("What does DNS do?",["Maps domain names to IP addresses","Encrypts all files","Creates spreadsheets","Runs tests"],"0"),("Which device forwards packets between networks?",["Router","Keyboard","Monitor","Compiler"],"0"),("What is an IP address used for?",["Identifying a network interface","Formatting a document","Sorting SQL rows","Drawing UI"],"0")]),
 "Cloud / DevOps Engineer": ("technical", [("CI/CD aims to automate:",["Build, test and delivery steps","Only UI colors","Manual typing","Email signatures"],"0"),("Containers package an application with:",["Its dependencies","A monitor","Only source comments","A spreadsheet"],"0"),("Which command commonly shows running processes on Linux?",["ps","paint","SELECT","mkdir only"],"0")]),
 "ERP Consultant": ("technical", [("ERP systems integrate:",["Core business processes","Only browser bookmarks","Only images","Only email"],"0"),("Requirements gathering should involve:",["Stakeholders and business workflows","Guessing","Skipping users","Only deployment"],"0" )]),
}
def get_role_questions(role):
    base = [dict(q) for q in QUESTION_BANK if q["section"] in ("quantitative", "logical", "verbal")]
    topic, specialized = ROLE_TOPICS.get(role, ROLE_TOPICS["Software Developer"])
    for i, (text, options, answer) in enumerate(specialized, 1):
        base.append({"id": f"role{i}", "section": topic, "text": text, "options": options, "answer": answer, "difficulty": i})
    return base

QUESTION_BANK = [
 {"id":"q1","section":"quantitative","text":"A product priced at ₹800 is discounted by 15%. What is the sale price?","options":["₹620","₹680","₹700","₹720"],"answer":"1","difficulty":1},
 {"id":"q2","section":"quantitative","text":"If 5 workers complete a job in 12 days, how many days would 10 equally productive workers take?","options":["3","6","10","24"],"answer":"1","difficulty":1},
 {"id":"q3","section":"quantitative","text":"A number increases from 80 to 100. What is the percentage increase?","options":["20%","25%","30%","40%"],"answer":"1","difficulty":2},
 {"id":"q4","section":"logical","text":"Find the next number: 2, 6, 12, 20, 30, __","options":["36","40","42","44"],"answer":"2","difficulty":2},
 {"id":"q5","section":"logical","text":"All analysts use data. Some graduates are analysts. Which statement must be true?","options":["All graduates use data","Some graduates use data","No graduates use data","All data users are analysts"],"answer":"1","difficulty":2},
 {"id":"q6","section":"verbal","text":"Choose the grammatically correct sentence.","options":["She have completed the task.","She has completed the task.","She completing the task.","She have completing the task."],"answer":"1","difficulty":1},
 {"id":"q7","section":"verbal","text":"Closest meaning of “concise”:","options":["Brief and clear","Uncertain","Very detailed","Unrelated"],"answer":"0","difficulty":1},
 {"id":"q8","section":"technical","text":"Which data structure follows FIFO order?","options":["Stack","Queue","Tree","Graph"],"answer":"1","difficulty":1},
 {"id":"q9","section":"technical","text":"Which SQL clause filters rows before grouping?","options":["ORDER BY","HAVING","WHERE","GROUP BY"],"answer":"2","difficulty":1},
 {"id":"q10","section":"technical","text":"In object-oriented programming, encapsulation primarily means:","options":["Hiding implementation details and bundling data with methods","Running code in parallel","Sorting objects","Converting source to machine code"],"answer":"0","difficulty":2},
 {"id":"q11","section":"data","text":"A team completes 40 tasks on Monday and 50 on Tuesday. What is the percentage increase?","options":["10%","20%","25%","30%"],"answer":"2","difficulty":1},
 {"id":"q12","section":"data","text":"A dataset has values 4, 6, 6, 8, 11. What is its median?","options":["4","6","7","8"],"answer":"1","difficulty":1},
 {"id":"q13","section":"quantitative","text":"A bag contains 3 red and 2 blue balls. Probability of drawing a blue ball is:","options":["1/5","2/5","3/5","1/2"],"answer":"1","difficulty":2},
 {"id":"q14","section":"logical","text":"If CAT is coded as DBU (each letter shifted one forward), DOG is coded as:","options":["EPH","CNG","EOG","FPI"],"answer":"0","difficulty":1},
 {"id":"q15","section":"technical","text":"Which algorithmic complexity is typical for binary search on a sorted array?","options":["O(1)","O(log n)","O(n)","O(n²)"],"answer":"1","difficulty":2},
]

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
