"""
Resume Analyser Agent
Reads PDF / DOCX / TXT resume → extracts skills, role, experience → returns job links
"""

import os
import io
import json

# ── PDF ──────────────────────────────────────────────────────────────────────
def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except ImportError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


# ── DOCX ─────────────────────────────────────────────────────────────────────
def _extract_docx(file_bytes: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")


# ── TXT ──────────────────────────────────────────────────────────────────────
def _extract_txt(file_bytes: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


# ── Dispatcher ────────────────────────────────────────────────────────────────
def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return _extract_docx(file_bytes)
    elif ext == "txt":
        return _extract_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}  (use PDF, DOCX, or TXT)")


# ── AI analysis ───────────────────────────────────────────────────────────────
def analyse_resume(resume_text: str) -> dict:
    """
    Send resume text to NVIDIA AI → get structured profile.
    Returns dict with role, skills, experience, education, job_titles.
    """
    from utils.nvidia_client import chat_completion

    # Limit text to first 6000 chars to stay within context limits
    truncated = resume_text[:6000]

    prompt = f"""You are an expert HR analyst and resume parser.

Analyse the resume below and extract key information. Return ONLY valid JSON, no markdown fences, no explanation.

Resume:
\"\"\"
{truncated}
\"\"\"

Return this exact JSON structure:
{{
  "candidate_name": "full name or Unknown",
  "primary_role": "most suitable job title e.g. Python Developer",
  "related_job_titles": ["title1", "title2", "title3", "title4"],
  "top_skills": ["skill1", "skill2", "skill3", "skill4", "skill5", "skill6"],
  "experience_years": "e.g. 2 years or Fresher",
  "experience_level": "Fresher | Junior | Mid-level | Senior | Lead",
  "education": "highest degree e.g. B.Tech Computer Science",
  "industries": ["industry1", "industry2"],
  "key_achievements": ["one liner achievement 1", "one liner achievement 2"],
  "summary": "2-3 sentence professional summary of this candidate",
  "search_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""

    raw = chat_completion([{"role": "user", "content": prompt}], temperature=0.1)

    # Strip markdown fences if any
    clean = raw.strip()
    for fence in ("```json", "```"):
        clean = clean.replace(fence, "")
    clean = clean.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Fallback: extract role from raw text heuristically
        return {
            "candidate_name": "Unknown",
            "primary_role": "Software Developer",
            "related_job_titles": ["Software Engineer", "Developer"],
            "top_skills": [],
            "experience_years": "Not specified",
            "experience_level": "Mid-level",
            "education": "Not specified",
            "industries": ["Technology"],
            "key_achievements": [],
            "summary": raw[:300],
            "search_keywords": ["Software Developer"],
        }


# ── Job search from profile ───────────────────────────────────────────────────
def get_jobs_for_profile(profile: dict) -> list[dict]:
    """Generate job portal links based on parsed resume profile."""
    from utils.job_search import search_jobs_global

    primary_role = profile.get("primary_role", "Software Developer")
    skills = profile.get("top_skills", [])
    experience_level = profile.get("experience_level", "Mid-level")

    # Build an enriched search query
    skill_str = " ".join(skills[:3]) if skills else ""
    search_query = f"{primary_role} {skill_str}".strip()

    return search_jobs_global(search_query)


# ── Main entry point ──────────────────────────────────────────────────────────
def run_resume_agent(file_bytes: bytes, filename: str) -> dict:
    """
    Full pipeline:
      file_bytes + filename → extract text → AI analyse → job links
    """
    # Step 1: Extract text
    resume_text = extract_text_from_file(file_bytes, filename)

    if len(resume_text.strip()) < 50:
        raise ValueError("Could not extract enough text from the file. Please upload a readable resume.")

    # Step 2: AI analysis
    profile = analyse_resume(resume_text)

    # Step 3: Get job links
    jobs = get_jobs_for_profile(profile)

    # Step 4: Generate AI intro
    intro = _generate_intro(profile, len(jobs))

    return {
        "mode": "resume",
        "filename": filename,
        "profile": profile,
        "jobs": jobs,
        "total": len(jobs),
        "intro": intro,
    }


def _generate_intro(profile: dict, job_count: int) -> str:
    from utils.nvidia_client import chat_completion

    prompt = f"""Write a 2-3 sentence friendly message for a job seeker whose resume was analysed.

Candidate: {profile.get('candidate_name', 'there')}
Role: {profile.get('primary_role')}
Experience: {profile.get('experience_years')} ({profile.get('experience_level')})
Skills: {', '.join(profile.get('top_skills', [])[:4])}
Jobs found: {job_count} portal links

Be encouraging and mention what role we searched for. Plain text only."""

    return chat_completion([{"role": "user", "content": prompt}], temperature=0.6)