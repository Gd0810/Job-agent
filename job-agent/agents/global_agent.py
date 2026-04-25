"""
Global Agent — No filters, just role → job links across the internet
"""

from utils.nvidia_client import chat_completion
from utils.job_search import search_jobs_global

SYSTEM_PROMPT = """You are JobHunterAI, an expert job search assistant.
Your task is to help users find job opportunities based on their role.

When a user says they are a [role] developer/designer/etc:
1. Understand their exact job role and skills
2. Expand it into relevant job titles (e.g., "Python Developer" → "Python Developer, Backend Engineer, Software Engineer Python, Django Developer, FastAPI Developer")
3. Return a clean, structured response summarizing what you searched for

Be concise. Do NOT make up job links — those come from search. Just explain the search strategy used.
Format your intro like:
"Found X job listings for [role]. Here are search links from top portals:"
"""


def run_global_agent(user_message: str) -> dict:
    """
    Run global job search. Takes user's role statement and returns job links.
    """
    # Step 1: Use AI to extract role and expand keywords
    extraction_prompt = f"""
The user said: "{user_message}"

Extract:
1. The primary job role (e.g., "Python Developer")
2. 3-5 related job titles to also search for
3. Key skills associated with this role

Respond in this exact JSON format (no markdown, no explanation):
{{
  "primary_role": "...",
  "related_titles": ["...", "...", "..."],
  "key_skills": ["...", "...", "..."],
  "search_summary": "One sentence describing what you'll search for"
}}
"""
    import json
    raw = chat_completion([{"role": "user", "content": extraction_prompt}], temperature=0.2)

    # Parse AI response
    try:
        # Strip markdown fences if any
        clean = raw.strip().replace("```json", "").replace("```", "").strip()
        role_data = json.loads(clean)
    except Exception:
        role_data = {
            "primary_role": user_message.replace("I am a", "").replace("I am an", "").strip(),
            "related_titles": [],
            "key_skills": [],
            "search_summary": f"Searching for {user_message} jobs globally"
        }

    primary_role = role_data.get("primary_role", "Software Developer")

    # Step 2: Fetch job links
    job_links = search_jobs_global(primary_role)

    # Step 3: Generate a friendly AI intro
    intro_prompt = f"""
The user is looking for: {primary_role} jobs
Related titles found: {', '.join(role_data.get('related_titles', []))}
Number of job portals found: {len(job_links)}

Write a 2-3 sentence friendly response introducing these results.
Mention the role, and the fact that you've found job links from multiple portals.
Do NOT use markdown. Plain text only.
"""
    intro = chat_completion([{"role": "user", "content": intro_prompt}], temperature=0.5)

    return {
        "mode": "global",
        "role": primary_role,
        "related_titles": role_data.get("related_titles", []),
        "key_skills": role_data.get("key_skills", []),
        "intro": intro,
        "jobs": job_links,
        "total": len(job_links),
    }