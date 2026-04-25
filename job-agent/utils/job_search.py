"""
Job Search Utility — uses Google Custom Search API + fallback googlesearch-python
Fetches real job links from job portals (LinkedIn, Indeed, Naukri, Glassdoor, etc.)
"""

import os
import re
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

# Top job portals to target in search queries
JOB_PORTALS = [
    "linkedin.com/jobs",
    "indeed.com",
    "naukri.com",
    "glassdoor.com",
    "monster.com",
    "timesjobs.com",
    "shine.com",
    "foundit.in",
    "internshala.com",
    "wellfound.com",
]

PORTAL_DISPLAY = {
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "naukri.com": "Naukri",
    "glassdoor.com": "Glassdoor",
    "monster.com": "Monster",
    "timesjobs.com": "TimesJobs",
    "shine.com": "Shine",
    "foundit.in": "Foundit",
    "internshala.com": "Internshala",
    "wellfound.com": "Wellfound",
    "remoteok.com": "RemoteOK",
    "stackoverflow.com": "StackOverflow Jobs",
    "angel.co": "AngelList",
}


def _portal_label(url: str) -> str:
    for domain, label in PORTAL_DISPLAY.items():
        if domain in url:
            return label
    return "Job Portal"


def _google_cse_search(query: str, num: int = 10) -> list[dict]:
    """Use Google Custom Search Engine API."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num, 10),
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": _portal_label(item.get("link", "")),
            })
        return results
    except Exception as e:
        print(f"[CSE Error] {e}")
        return []


def _fallback_search(query: str, num: int = 10) -> list[dict]:
    """Fallback: construct direct job portal search URLs."""
    # Since we can't do live search without keys, we construct deep-link search URLs
    encoded = quote_plus(query)
    results = []

    portal_searches = [
        {
            "source": "LinkedIn",
            "link": f"https://www.linkedin.com/jobs/search/?keywords={encoded}",
            "title": f"{query} Jobs on LinkedIn",
            "snippet": "Search for jobs on LinkedIn, the world's largest professional network.",
        },
        {
            "source": "Indeed",
            "link": f"https://www.indeed.com/jobs?q={encoded}",
            "title": f"{query} Jobs on Indeed",
            "snippet": "Find millions of jobs on Indeed. Search by title, location, and more.",
        },
        {
            "source": "Naukri",
            "link": f"https://www.naukri.com/{query.lower().replace(' ', '-')}-jobs",
            "title": f"{query} Jobs on Naukri",
            "snippet": "India's No.1 Job Portal. Search for jobs across top companies.",
        },
        {
            "source": "Glassdoor",
            "link": f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={encoded}",
            "title": f"{query} Jobs on Glassdoor",
            "snippet": "Find jobs with salary insights, reviews, and company ratings.",
        },
        {
            "source": "Monster",
            "link": f"https://www.monster.com/jobs/search?q={encoded}",
            "title": f"{query} Jobs on Monster",
            "snippet": "Search thousands of job openings on Monster.",
        },
        {
            "source": "TimesJobs",
            "link": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={encoded}",
            "title": f"{query} Jobs on TimesJobs",
            "snippet": "Discover job opportunities tailored to your skills on TimesJobs.",
        },
        {
            "source": "Shine",
            "link": f"https://www.shine.com/job-search/{query.lower().replace(' ', '-')}-jobs",
            "title": f"{query} Jobs on Shine",
            "snippet": "Find top {query} jobs on Shine.com.",
        },
        {
            "source": "Foundit",
            "link": f"https://www.foundit.in/srp/results?query={encoded}",
            "title": f"{query} Jobs on Foundit (Monster India)",
            "snippet": "Explore {query} job openings on Foundit.",
        },
        {
            "source": "Wellfound",
            "link": f"https://wellfound.com/jobs?role={encoded}",
            "title": f"{query} Jobs at Startups — Wellfound",
            "snippet": "Find startup jobs and apply directly on Wellfound (AngelList Talent).",
        },
        {
            "source": "RemoteOK",
            "link": f"https://remoteok.com/remote-{query.lower().replace(' ', '-')}-jobs",
            "title": f"Remote {query} Jobs — RemoteOK",
            "snippet": "Browse remote-only {query} job listings worldwide.",
        },
    ]
    return portal_searches[:num]


def search_jobs_global(role: str) -> list[dict]:
    """
    GLOBAL METHOD: Search for all jobs matching a role across the internet.
    """
    query = f"{role} jobs hiring 2024 site:linkedin.com OR site:indeed.com OR site:naukri.com OR site:glassdoor.com"

    # Try Google CSE first
    results = _google_cse_search(query, num=10)
    if results:
        return results

    # Fallback to portal deep links
    return _fallback_search(role, num=10)


def search_jobs_filtered(role: str, country: str, experience: str, city: str = None) -> dict:
    """
    KEYCHAIN METHOD: Search jobs with filters — country, experience, city.
    Returns primary results + nearby city results if city-specific search is empty.
    """
    # Build filtered query
    location = city if city else country
    query = f"{role} jobs {experience} experience {location} {country} site:linkedin.com OR site:indeed.com OR site:naukri.com"

    primary = []
    nearby = []

    # Try CSE
    primary = _google_cse_search(query, num=10)

    if not primary:
        # Fallback: build location-aware deep links
        encoded_role = quote_plus(role)
        encoded_location = quote_plus(location)
        encoded_exp = quote_plus(experience)

        # India-specific portals get priority for Indian users
        is_india = "india" in country.lower()

        portals = []
        if is_india:
            portals = [
                {
                    "source": "Naukri",
                    "link": f"https://www.naukri.com/{role.lower().replace(' ', '-')}-jobs-in-{(city or country).lower().replace(' ', '-')}",
                    "title": f"{role} Jobs in {city or country} — Naukri",
                    "snippet": f"Find {role} jobs in {city or country} with {experience} experience on Naukri.",
                },
                {
                    "source": "LinkedIn",
                    "link": f"https://www.linkedin.com/jobs/search/?keywords={encoded_role}&location={encoded_location}",
                    "title": f"{role} Jobs in {city or country} — LinkedIn",
                    "snippet": f"Apply to {role} positions in {city or country} on LinkedIn.",
                },
                {
                    "source": "Indeed India",
                    "link": f"https://in.indeed.com/jobs?q={encoded_role}&l={encoded_location}",
                    "title": f"{role} Jobs in {city or country} — Indeed India",
                    "snippet": f"Thousands of {role} openings in {city or country} on Indeed.",
                },
                {
                    "source": "TimesJobs",
                    "link": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={encoded_role}&txtLocation={encoded_location}",
                    "title": f"{role} Jobs in {city or country} — TimesJobs",
                    "snippet": f"Browse {role} vacancies in {city or country} on TimesJobs.",
                },
                {
                    "source": "Foundit",
                    "link": f"https://www.foundit.in/srp/results?query={encoded_role}&locations={encoded_location}",
                    "title": f"{role} Jobs in {city or country} — Foundit",
                    "snippet": f"Explore {role} job listings in {city or country} on Foundit.",
                },
                {
                    "source": "Shine",
                    "link": f"https://www.shine.com/job-search/{role.lower().replace(' ', '-')}-jobs-in-{(city or country).lower().replace(' ', '-')}",
                    "title": f"{role} Jobs in {city or country} — Shine",
                    "snippet": f"Find {role} openings in {city or country} on Shine.",
                },
                {
                    "source": "Glassdoor",
                    "link": f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={encoded_role}&locT=C&locName={encoded_location}",
                    "title": f"{role} Jobs in {city or country} — Glassdoor",
                    "snippet": f"See salary, reviews and apply for {role} jobs in {city or country}.",
                },
                {
                    "source": "Internshala",
                    "link": f"https://internshala.com/jobs/{role.lower().replace(' ', '-')}-jobs-in-{(city or country).lower().replace(' ', '-')}",
                    "title": f"{role} Jobs in {city or country} — Internshala",
                    "snippet": f"Freshers & experienced {role} jobs in {city or country}.",
                },
            ]
        else:
            portals = [
                {
                    "source": "LinkedIn",
                    "link": f"https://www.linkedin.com/jobs/search/?keywords={encoded_role}&location={encoded_location}",
                    "title": f"{role} Jobs in {location} — LinkedIn",
                    "snippet": f"Apply to {role} positions in {location}.",
                },
                {
                    "source": "Indeed",
                    "link": f"https://www.indeed.com/jobs?q={encoded_role}&l={encoded_location}",
                    "title": f"{role} Jobs in {location} — Indeed",
                    "snippet": f"Browse thousands of {role} jobs in {location}.",
                },
                {
                    "source": "Glassdoor",
                    "link": f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={encoded_role}&locName={encoded_location}",
                    "title": f"{role} Jobs in {location} — Glassdoor",
                    "snippet": f"Research salaries and apply for {role} in {location}.",
                },
                {
                    "source": "Monster",
                    "link": f"https://www.monster.com/jobs/search?q={encoded_role}&where={encoded_location}",
                    "title": f"{role} Jobs in {location} — Monster",
                    "snippet": f"Find {role} opportunities near {location}.",
                },
                {
                    "source": "Wellfound",
                    "link": f"https://wellfound.com/jobs?role={encoded_role}&location={encoded_location}",
                    "title": f"{role} Startup Jobs in {location} — Wellfound",
                    "snippet": f"Browse startup {role} roles in {location} on Wellfound.",
                },
            ]

        primary = portals

    # Generate nearby city results if city was specified
    if city:
        nearby_cities = _get_nearby_cities(city, country)
        for nc in nearby_cities[:3]:
            enc_nc = quote_plus(nc)
            nearby.append({
                "source": "LinkedIn (Nearby)",
                "link": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(role)}&location={enc_nc}",
                "title": f"{role} Jobs in {nc} (Nearby City)",
                "snippet": f"Couldn't find enough results in {city}? Try similar {role} openings in {nc}.",
                "is_nearby": True,
                "nearby_city": nc,
            })
            nearby.append({
                "source": "Indeed (Nearby)",
                "link": f"https://{'in.' if 'india' in country.lower() else ''}indeed.com/jobs?q={quote_plus(role)}&l={enc_nc}",
                "title": f"{role} Jobs in {nc} (Nearby City)",
                "snippet": f"Similar {role} positions available in {nc}, near {city}.",
                "is_nearby": True,
                "nearby_city": nc,
            })

    return {
        "primary": primary,
        "nearby": nearby,
        "has_nearby": len(nearby) > 0,
        "city": city,
        "country": country,
    }


def _get_nearby_cities(city: str, country: str) -> list[str]:
    """Return nearby major cities based on known geography."""
    city_lower = city.lower()
    country_lower = country.lower()

    india_nearby = {
        "chennai": ["Bengaluru", "Hyderabad", "Coimbatore", "Pune"],
        "bengaluru": ["Chennai", "Hyderabad", "Pune", "Mumbai"],
        "bangalore": ["Chennai", "Hyderabad", "Pune", "Mumbai"],
        "mumbai": ["Pune", "Bengaluru", "Surat", "Nashik"],
        "hyderabad": ["Bengaluru", "Chennai", "Pune", "Visakhapatnam"],
        "delhi": ["Noida", "Gurgaon", "Faridabad", "Ghaziabad"],
        "noida": ["Delhi", "Gurgaon", "Faridabad", "Agra"],
        "gurgaon": ["Delhi", "Noida", "Faridabad", "Chandigarh"],
        "pune": ["Mumbai", "Bengaluru", "Nashik", "Aurangabad"],
        "kolkata": ["Bhubaneswar", "Patna", "Ranchi", "Siliguri"],
        "ahmedabad": ["Surat", "Vadodara", "Rajkot", "Mumbai"],
        "jaipur": ["Delhi", "Kota", "Jodhpur", "Ajmer"],
        "coimbatore": ["Chennai", "Bengaluru", "Madurai", "Salem"],
        "kochi": ["Bengaluru", "Chennai", "Kozhikode", "Thiruvananthapuram"],
    }

    us_nearby = {
        "new york": ["Jersey City", "Newark", "Brooklyn", "Boston"],
        "san francisco": ["Oakland", "San Jose", "Berkeley", "Palo Alto"],
        "los angeles": ["Irvine", "San Diego", "Long Beach", "Burbank"],
        "chicago": ["Evanston", "Naperville", "Aurora", "Milwaukee"],
        "austin": ["San Antonio", "Houston", "Dallas", "Round Rock"],
        "seattle": ["Bellevue", "Redmond", "Tacoma", "Portland"],
    }

    if "india" in country_lower:
        return india_nearby.get(city_lower, ["Mumbai", "Bengaluru", "Delhi"])
    elif "united states" in country_lower or "usa" in country_lower or "us" == country_lower:
        return us_nearby.get(city_lower, ["New York", "San Francisco", "Austin"])
    else:
        return []