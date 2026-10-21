"""Training/inference for placement prediction.
The included model is trained on synthetic demonstration data, not real placement records.
Replace it with institution-approved historical data before making real-world claims.
"""
import os, pickle, json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

FEATURES = ["cgpa","backlogs","projects","internships","coding","communication","sql","web",
            "quantitative","logical","verbal","technical","data","aptitude_score"]
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "placement_model.pkl")

def make_demo_dataset(n=1800, seed=42):
    """Synthetic data solely to make the starter app runnable."""
    rng = np.random.default_rng(seed)
    cgpa = rng.uniform(5.0, 10.0, n)
    backlogs = rng.integers(0, 5, n)
    projects = rng.integers(0, 6, n)
    internships = rng.integers(0, 4, n)
    coding, communication, sql, web = [rng.integers(25, 101, n) for _ in range(4)]
    quantitative, logical, verbal, technical, data = [rng.integers(20, 101, n) for _ in range(5)]
    aptitude = np.round((quantitative+logical+verbal+technical+data)/5)
    logit = (-4.0 + 0.48*(cgpa-6) - 0.55*backlogs + 0.16*projects + 0.28*internships
             + 0.012*(coding-50) + 0.006*(communication-50) + 0.009*(sql-50) + 0.007*(web-50)
             + 0.009*(aptitude-50))
    p = 1/(1+np.exp(-logit))
    placed = rng.binomial(1, p)
    df = pd.DataFrame(dict(cgpa=cgpa, backlogs=backlogs, projects=projects, internships=internships,
      coding=coding, communication=communication, sql=sql, web=web, quantitative=quantitative,
      logical=logical, verbal=verbal, technical=technical, data=data, aptitude_score=aptitude, placed=placed))
    return df

def train_model():
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    df = make_demo_dataset()
    X, y = df[FEATURES], df["placed"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")),
                      ("scale", StandardScaler()),
                      ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced"))])
    model.fit(X_train, y_train)
    prob = model.predict_proba(X_test)[:,1]
    metrics = {"accuracy": float(accuracy_score(y_test, model.predict(X_test))),
               "roc_auc": float(roc_auc_score(y_test, prob)),
               "classification_report": classification_report(y_test, model.predict(X_test), output_dict=True)}
    with open(MODEL_PATH, "wb") as f: pickle.dump({"model": model, "features": FEATURES, "metrics": metrics}, f)
    print("Saved", MODEL_PATH)
    print("Demo validation metrics (synthetic data; not evidence of real-world performance):", metrics)
    return metrics

def load_model():
    if not os.path.exists(MODEL_PATH):
        train_model()
    with open(MODEL_PATH, "rb") as f: return pickle.load(f)

def predict_placement(bundle, features):
    row = pd.DataFrame([{name: features.get(name, 0) for name in bundle["features"]}])
    probability = float(bundle["model"].predict_proba(row)[0,1])
    return {"probability": round(probability, 4),
            "percent": round(probability*100),
            "label": "Higher estimated readiness" if probability >= .60 else ("Developing readiness" if probability >= .40 else "Needs further preparation"),
            "model_note": "Illustrative estimate from a synthetic-data model; not a validated hiring probability."}

def career_recommendations(f):
    """Rank roles from profile skills, assessment sections, ATS quality, and resume keywords."""
    try:
        raw_skills = f.get("resume_skills", [])
        resume_skills = json.loads(raw_skills) if isinstance(raw_skills, str) else (raw_skills or [])
        if not isinstance(resume_skills, list):
            resume_skills = []
    except (ValueError, TypeError):
        resume_skills = []
    skill_text = " ".join(str(x).lower() for x in resume_skills)
    ats = max(0, min(100, float(f.get("ats_score", 0) or 0)))
    base_roles = {
      "Data Analyst": (0.30*f.get("sql",0)+0.28*f.get("data",0)+0.18*f.get("quantitative",0)+0.12*f.get("communication",0)+0.12*f.get("aptitude_score",0),
                       ["SQL", "Excel or Power BI", "Statistics", "Portfolio dashboard"], ["sql", "excel", "power bi", "pandas", "data analysis"]),
      "Software Developer": (0.34*f.get("coding",0)+0.22*f.get("logical",0)+0.20*f.get("technical",0)+0.14*f.get("quantitative",0)+0.10*f.get("aptitude_score",0),
                       ["Data structures and algorithms", "Git", "Testing", "Deploy two projects"], ["python", "java", "c++", "git", "api", "software development"]),
      "QA / Test Engineer": (0.25*f.get("logical",0)+0.24*f.get("technical",0)+0.20*f.get("communication",0)+0.16*f.get("coding",0)+0.15*f.get("aptitude_score",0),
                       ["Test case design", "SQL", "API testing", "Selenium or Playwright"], ["testing", "selenium", "jmeter", "postman", "qa", "test cases"]),
      "Web Developer": (0.36*f.get("web",0)+0.24*f.get("coding",0)+0.16*f.get("logical",0)+0.12*f.get("technical",0)+0.12*f.get("aptitude_score",0),
                       ["JavaScript fundamentals", "Responsive UI", "REST APIs", "Deploy a full-stack app"], ["html", "css", "javascript", "react", "flask", "web development"]),
    }
    ranked = []
    for name, (base_score, tips, keywords) in base_roles.items():
        keyword_hits = sum(1 for keyword in keywords if keyword in skill_text)
        resume_bonus = min(5, keyword_hits)
        match_score = round(0.90 * base_score + 0.10 * ats + resume_bonus)
        personal_tips = list(tips)
        if ats < 70:
            personal_tips.insert(0, "Improve ATS readiness: add clear education, project, experience and role-specific skill sections.")
        missing_keywords = [k for k in keywords if k not in skill_text]
        if missing_keywords:
            personal_tips.append("Consider demonstrating relevant resume keywords: " + ", ".join(missing_keywords[:3]) + ".")
        ranked.append((name, match_score, personal_tips))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [{"role": name, "match_score": max(0, min(100, score)), "recommendations": tips}
            for name, score, tips in ranked[:3]]

if __name__ == "__main__":
    train_model()
