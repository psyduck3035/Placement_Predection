import io, os, re
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
SKILL_ALIASES = {
    "Python":"Python","Java":"Java","JavaScript":"JavaScript","TypeScript":"TypeScript",
    "SQL":"SQL","MySQL":"MySQL","PostgreSQL":"PostgreSQL","HTML":"HTML","CSS":"CSS",
    "Bootstrap":"Bootstrap","React":"React","Angular":"Angular","Node.js":"Node.js",
    "Flask":"Flask","Django":"Django","Pandas":"Pandas","NumPy":"NumPy","Power BI":"Power BI",
    "Excel":"Excel","Tableau":"Tableau","Figma":"Figma","Photoshop":"Photoshop","Canva":"Canva",
    "Git":"Git","GitHub":"GitHub","Selenium":"Selenium","JMeter":"JMeter","C":"C","C++":"C++"
}
CODING_LANGUAGES = ["Python","Java","JavaScript","TypeScript","C++","C"]
STRENGTH_TERMS = ["communication","leadership","teamwork","problem solving","analytical","creative","adaptable","time management","collaboration","attention to detail"]

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(file_storage):
    filename = secure_filename(file_storage.filename or "resume")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    raw = file_storage.read()
    if ext == "txt":
        return raw.decode("utf-8", errors="ignore")
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == "docx":
        from docx import Document
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Unsupported resume format")

def detect_skills(text):
    found=[]
    low=text.lower()
    for needle, label in SKILL_ALIASES.items():
        pattern = r"(?<![a-z0-9])" + re.escape(needle.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, low) and label not in found:
            found.append(label)
    return found

def detect_languages(text):
    skills=detect_skills(text)
    return [x for x in CODING_LANGUAGES if x in skills]

def detect_strengths(text):
    low=text.lower()
    return [s.title() for s in STRENGTH_TERMS if re.search(r"\b"+re.escape(s)+r"\b", low)]

def detect_percentage(text, patterns):
    for p in patterns:
        m=re.search(p, text, re.I)
        if m:
            try:
                value=float(m.group(1))
                if 0 <= value <= 100: return value
            except ValueError: pass
    return None

def detect_education(text):
    tenth = detect_percentage(text, [r"(?:10th|ssc|secondary)[^\n%]{0,80}(\d{1,2}(?:\.\d+)?)\s*%", r"(\d{1,2}(?:\.\d+)?)\s*%[^\n]{0,30}(?:10th|ssc)"])
    twelfth = detect_percentage(text, [r"(?:12th|hsc|higher secondary)[^\n%]{0,80}(\d{1,2}(?:\.\d+)?)\s*%", r"(\d{1,2}(?:\.\d+)?)\s*%[^\n]{0,30}(?:12th|hsc)"])
    return tenth, twelfth

def analyze_ats(text, preferred_role="Data Analyst"):
    skills=detect_skills(text); languages=detect_languages(text); strengths=detect_strengths(text)
    low=text.lower()
    sections={
        "contact": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)),
        "summary": bool(re.search(r"\b(summary|objective|profile)\b", low)),
        "education": bool(re.search(r"\b(education|b\.sc|bca|b\.e|btech|degree|university|college)\b", low)),
        "experience": bool(re.search(r"\b(experience|internship|intern|work experience)\b", low)),
        "projects": bool(re.search(r"\b(projects?|portfolio)\b", low)),
        "skills": len(skills)>=3,
        "action_words": bool(re.search(r"\b(developed|built|analyzed|designed|created|tested|implemented|improved|automated|managed)\b", low)),
        "readability": len(text.split()) >= 180,
    }
    score=round(sum(sections.values())/len(sections)*100)
    tips=[]
    if not sections["summary"]: tips.append("Add a 2–3 line professional summary tailored to the target role.")
    if not sections["skills"]: tips.append("Add a dedicated Skills section with job-description keywords.")
    if not sections["projects"]: tips.append("Add 2–4 projects with measurable outcomes and technologies used.")
    if not sections["action_words"]: tips.append("Start bullet points with strong action verbs such as Built, Analyzed, Designed or Automated.")
    if not sections["experience"]: tips.append("Include internships, practical experience, or relevant college work.")
    if not sections["readability"]: tips.append("Add concise achievement bullets so the resume contains enough role-relevant detail.")
    role_keywords={
      "Data Analyst":["SQL","Excel","Power BI","Python","Pandas","Tableau","statistics"],
      "Web Developer":["HTML","CSS","JavaScript","React","Node.js","REST","Git"],
      "Software Developer":["Python","Java","SQL","Git","testing","data structures"],
      "UI/UX Designer":["Figma","wireframing","prototyping","user research","UI","UX"],
      "QA / Test Engineer":["Selenium","testing","SQL","API","JMeter","automation"],
    }
    target=role_keywords.get(preferred_role, role_keywords["Data Analyst"])
    role_hits=sum(1 for k in target if re.search(r"\b"+re.escape(k.lower())+r"\b", low))
    keyword_score=round(role_hits/max(1,len(target))*100)
    if keyword_score < 60: tips.append(f"Add more keywords relevant to {preferred_role}: {', '.join(target)}.")
    final=round(score*0.65 + keyword_score*0.35)
    return {"score":final,"base_score":score,"keyword_score":keyword_score,"skills":skills,"languages":languages,"strengths":strengths,"tips":tips[:6],"sections":sections}
