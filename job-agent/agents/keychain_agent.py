"""
Keychain Agent — Multi-turn conversational job search
Collects: role → country → experience → city (optional)
Then returns filtered job links + nearby city fallback
"""

import json
from utils.nvidia_client import chat_completion
from utils.job_search import search_jobs_filtered

SYSTEM_PROMPT = """You are JobHunterAI, a conversational job search assistant using a step-by-step approach.

You collect information through a guided conversation:
STEP 1: User mentions their role → Ask for their country
STEP 2: User gives country → Ask for years of experience  
STEP 3: User gives experience → Ask if they want jobs in a specific city
STEP 4: User gives city (or says no) → Confirm and search

Rules:
- Ask ONE question at a time
- Be friendly and conversational
- Remember all previous answers
- When all info is collected, respond with SEARCH_READY in your message

Keep responses short (1-2 sentences max per turn).
"""

# Conversation states
STATE_INIT = "init"
STATE_ASKED_COUNTRY = "asked_country"
STATE_ASKED_EXPERIENCE = "asked_experience"
STATE_ASKED_CITY = "asked_city"
STATE_COMPLETE = "complete"


def process_keychain_turn(session: dict, user_message: str) -> dict:
    """
    Process a single turn of the keychain conversation.
    session = {
        "state": ...,
        "role": ...,
        "country": ...,
        "experience": ...,
        "city": ...,
        "history": [...]
    }
    Returns updated session + agent response.
    """
    state = session.get("state", STATE_INIT)
    history = session.get("history", [])
    history.append({"role": "user", "content": user_message})

    response_text = ""
    search_results = None
    is_complete = False

    if state == STATE_INIT:
        # Extract role from user's first message
        role = _extract_role(user_message)
        session["role"] = role
        session["state"] = STATE_ASKED_COUNTRY
        response_text = f"Great! You're a {role}. Which country are you based in or looking for jobs in?"

    elif state == STATE_ASKED_COUNTRY:
        country = _extract_country(user_message)
        session["country"] = country
        session["state"] = STATE_ASKED_EXPERIENCE
        response_text = f"Got it — {country}! How many years of experience do you have as a {session.get('role', 'professional')}?"

    elif state == STATE_ASKED_EXPERIENCE:
        experience = _extract_experience(user_message)
        session["experience"] = experience
        session["state"] = STATE_ASKED_CITY
        response_text = f"Perfect — {experience} of experience noted! Are you looking for jobs in a specific city? If yes, tell me the city name. If not, just say 'no' or 'any'."

    elif state == STATE_ASKED_CITY:
        city = _extract_city(user_message)
        session["city"] = city
        session["state"] = STATE_COMPLETE

        # Perform the actual search
        role = session.get("role", "Software Developer")
        country = session.get("country", "India")
        experience = session.get("experience", "2 years")

        if city and city.lower() not in ["no", "any", "anywhere", "none", "-"]:
            search_results = search_jobs_filtered(role, country, experience, city)
            city_text = f"in {city}"
        else:
            session["city"] = None
            search_results = search_jobs_filtered(role, country, experience)
            city_text = f"across {country}"

        # Generate summary
        total = len(search_results.get("primary", []))
        nearby_count = len(search_results.get("nearby", []))

        intro = _generate_search_intro(role, country, experience, city, total, nearby_count)
        search_results["intro"] = intro
        search_results["role"] = role
        is_complete = True
        response_text = intro

    history.append({"role": "assistant", "content": response_text})
    session["history"] = history

    return {
        "session": session,
        "response": response_text,
        "is_complete": is_complete,
        "search_results": search_results,
    }


def _extract_role(text: str) -> str:
    """Use AI to extract job role from user message."""
    prompt = f"""Extract the job role from this message: "{text}"
Return ONLY the job title, nothing else. Examples: "Python Developer", "Data Scientist", "UI/UX Designer"
If unclear, return "Software Developer"."""
    result = chat_completion([{"role": "user", "content": prompt}], temperature=0.1)
    return result.strip().strip('"').strip("'")


def _extract_country(text: str) -> str:
    """Extract country name from user message."""
    prompt = f"""Extract the country name from this message: "{text}"
Return ONLY the country name. Example: "India", "United States", "Germany"
If unclear, return the text as-is."""
    result = chat_completion([{"role": "user", "content": prompt}], temperature=0.1)
    return result.strip().strip('"').strip("'")


def _extract_experience(text: str) -> str:
    """Extract experience from user message."""
    prompt = f"""Extract years of experience from: "{text}"
Return in format like "2 years", "5+ years", "fresher", "1 year". Just the experience phrase, nothing else."""
    result = chat_completion([{"role": "user", "content": prompt}], temperature=0.1)
    return result.strip().strip('"').strip("'")


def _extract_city(text: str) -> str | None:
    """Extract city name, or return None if user says no."""
    no_words = ["no", "any", "anywhere", "none", "nope", "don't", "dont", "not", "skip", "-", "no preference"]
    text_lower = text.lower().strip()
    for word in no_words:
        if word in text_lower:
            return None

    prompt = f"""Extract the city name from: "{text}"
Return ONLY the city name. If no specific city mentioned, return "NONE"."""
    result = chat_completion([{"role": "user", "content": prompt}], temperature=0.1)
    result = result.strip().strip('"').strip("'")
    if result.upper() == "NONE":
        return None
    return result


def _generate_search_intro(role, country, experience, city, total, nearby_count) -> str:
    """Generate a friendly search completion message."""
    location = city if city else country
    prompt = f"""Generate a 2-3 sentence friendly message for job search results:
- Role: {role}
- Location: {location} ({country})
- Experience: {experience}
- Jobs found: {total} portal links
- Nearby city results: {nearby_count} (fallback suggestions)

{'Mention that some results from nearby cities are included as bonus.' if nearby_count > 0 else ''}
Plain text only, no markdown."""
    return chat_completion([{"role": "user", "content": prompt}], temperature=0.6)