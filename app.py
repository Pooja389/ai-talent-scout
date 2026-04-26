"""
AI Talent Scouting Agent - Using GROQ 
===================================================
Get free API key at: https://console.groq.com

How to run:
  Step 1: pip install flask groq
  Step 2: Get free key from https://console.groq.com → API Keys
  Step 3: paste your key in the GROQ_API_KEY variable below
  Step 4: python app.py
  Step 5: Open http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify
from groq import Groq
import json

import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ══════════════════════════════════════════════════════
#  PASTE YOUR FREE GROQ API KEY HERE
#  Get it free at: https://console.groq.com → API Keys
# ══════════════════════════════════════════════════════
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)


# ════════════════════════════════════════════════════════════════════
# HELPER FUNCTION: call_groq()
# This single function handles ALL our AI calls.
# We use llama-3.3-70b-versatile — it's free and very powerful.
# ════════════════════════════════════════════════════════════════════
def call_groq(system_prompt: str, user_message: str) -> str:
    """
    Calls Groq AI and returns the response text.
    
    system_prompt = instructions we give AI (what role to play)
    user_message  = the actual data/question
    returns       = AI's text response
    """
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",   
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ],
        temperature=0.7,     # creativity level (0=robotic, 1=creative)
        max_tokens=1024,     # max length of response
    )
    return response.choices[0].message.content


def safe_json_parse(text: str):
    """
    AI sometimes wraps JSON in ```json ... ``` markdown.
    This strips that and safely parses the JSON.
    Returns None if parsing fails.
    """
    cleaned = text.strip()

    # Remove ```json or ``` fences if present
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except:
                continue

    # Try parsing directly
    try:
        return json.loads(cleaned)
    except:
        # Try finding JSON array or object inside the text
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            start = cleaned.find(start_char)
            end = cleaned.rfind(end_char)
            if start != -1 and end != -1:
                try:
                    return json.loads(cleaned[start:end+1])
                except:
                    continue
        return None


# ════════════════════════════════════════════════════════════════════
# ROUTE 1: Home Page
# ════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ════════════════════════════════════════════════════════════════════
# ROUTE 2: Parse Job Description
# MODULE 1 — JD Parser
# ════════════════════════════════════════════════════════════════════

@app.route("/parse_jd", methods=["POST"])
def parse_jd():
    """
    Receives raw JD text → AI extracts structured requirements.
    
    Input:  { "jd_text": "We are hiring a Senior Engineer..." }
    Output: { role, seniority, skills[], experience_years, ... }
    """
    data     = request.get_json()
    jd_text  = data.get("jd_text", "").strip()

    if not jd_text:
        return jsonify({"error": "No job description provided"}), 400

    system_prompt = """You are an expert HR analyst. 
Extract structured hiring criteria from the job description.

Return ONLY a valid JSON object with exactly these keys:
{
  "role": "job title",
  "seniority": "Junior/Mid/Senior/Lead",
  "skills": ["skill1", "skill2"],
  "experience_years": 5,
  "domain": "Backend/Frontend/Data/etc",
  "location": "Remote or city name",
  "must_haves": ["requirement1", "requirement2"],
  "nice_to_haves": ["bonus1", "bonus2"]
}

Rules:
- skills: maximum 8 items
- must_haves: maximum 4 items  
- nice_to_haves: maximum 3 items
- No explanation, no markdown, ONLY the JSON object"""

    raw      = call_groq(system_prompt, f"Parse this job description:\n\n{jd_text}")
    parsed   = safe_json_parse(raw)

    if not parsed:
        return jsonify({"error": "AI could not parse the JD. Please try again."}), 500

    return jsonify({"success": True, "parsed": parsed})


# ════════════════════════════════════════════════════════════════════
# ROUTE 3: Discover & Score Candidates
# MODULE 2 — Candidate Discovery + Matching
# ════════════════════════════════════════════════════════════════════
@app.route("/discover_candidates", methods=["POST"])
def discover_candidates():
    """
    Step A: Generate 6 realistic candidate profiles
    Step B: Score each candidate against the JD (match score + explainability)
    """
    data       = request.get_json()
    parsed_jd  = data.get("parsed_jd", {})

    # ── Step A: Generate 6 candidate profiles ──────────────────────
    discovery_prompt = """You are a recruiter with a large candidate database.
Generate exactly 6 diverse, realistic candidate profiles for a job opening.

IMPORTANT - vary the quality deliberately:
- 2 candidates: strong match (they have most required skills)
- 2 candidates: partial match (they have some skills, missing others)
- 2 candidates: weak match (missing several key requirements)

Return ONLY a valid JSON array of exactly 6 objects:
[
  {
    "name": "Full Name",
    "current_role": "Their current job title",
    "years_exp": 5,
    "skills": ["skill1", "skill2", "skill3"],
    "location": "City, Country",
    "availability": "Immediate",
    "actively_looking": true,
    "summary": "One sentence about this person"
  }
]

Rules:
- availability must be one of: "Immediate", "2 weeks", "1 month", "3 months"
- skills: 6 to 8 items per candidate
- Use Indian names only (mix of Hindu, Muslim, Sikh names)
- No explanation, ONLY the JSON array"""

    raw        = call_groq(discovery_prompt, f"Job to hire for:\n{json.dumps(parsed_jd, indent=2)}")
    candidates = safe_json_parse(raw)

    if not candidates or not isinstance(candidates, list):
        return jsonify({"error": "AI could not generate candidates. Please try again."}), 500

    # ── Step B: Score each candidate ───────────────────────────────
    scoring_prompt = """You are a technical recruiter scoring candidates.

Return ONLY a valid JSON object:
{
  "match_score": 75,
  "matched_skills": ["Python", "AWS"],
  "missing_skills": ["Kubernetes"],
  "rationale": "Two sentences explaining why this score was given."
}

Rules:
- match_score: integer from 0 to 100
- Be honest — partial matches should score 40-65, weak matches 20-45
- No explanation, ONLY the JSON object"""

    for i, candidate in enumerate(candidates):
        user_msg = f"""Job Requirements:
{json.dumps(parsed_jd, indent=2)}

Candidate:
{json.dumps(candidate, indent=2)}

Score this candidate against the job."""

        raw2       = call_groq(scoring_prompt, user_msg)
        score_data = safe_json_parse(raw2)

        if score_data:
            candidate["match_score"]    = score_data.get("match_score", 50)
            candidate["matched_skills"] = score_data.get("matched_skills", [])
            candidate["missing_skills"] = score_data.get("missing_skills", [])
            candidate["rationale"]      = score_data.get("rationale", "")
        else:
            candidate["match_score"]    = 50
            candidate["matched_skills"] = []
            candidate["missing_skills"] = []
            candidate["rationale"]      = "Score unavailable."

        candidate["idx"] = i

    return jsonify({"success": True, "candidates": candidates})


# ════════════════════════════════════════════════════════════════════
# ROUTE 4: Simulate Outreach Conversations
# MODULE 3 — Conversational Outreach Simulation
# ════════════════════════════════════════════════════════════════════
@app.route("/run_outreach", methods=["POST"])
def run_outreach():
    """
    Simulates a recruiter messaging each candidate.
    Extracts an interest score from how they respond.
    
    Signals that increase interest score:
    + Actively job hunting
    + Excited, asks good questions
    + Available soon
    
    Signals that lower interest score:
    - Not looking / passive
    - Vague responses
    - Long notice period
    """
    data       = request.get_json()
    candidates = data.get("candidates", [])
    parsed_jd  = data.get("parsed_jd", {})

    outreach_prompt = """You are simulating a recruiter reaching out to a job candidate on LinkedIn.

Create a realistic conversation that naturally reveals how interested the candidate is.
Make it feel human — not scripted.

Vary interest levels:
- Some candidates are excited and actively looking
- Some are open but not urgently searching
- Some are politely uninterested or passive

Return ONLY a valid JSON object:
{
  "messages": [
    {"role": "agent", "text": "Hi [name], I came across your profile..."},
    {"role": "candidate", "text": "Thanks for reaching out..."},
    {"role": "agent", "text": "..."},
    {"role": "candidate", "text": "..."}
  ],
  "interest_score": 75,
  "interest_rationale": "Two sentences explaining the interest score based on the conversation."
}

Rules:
- messages: between 6 and 8 messages total, alternating agent/candidate
- interest_score: integer 0-100
  * 80-100 = very excited, actively looking, asks great questions
  * 60-79  = interested but has concerns
  * 40-59  = lukewarm, not actively searching
  * 0-39   = polite but not really interested
- No explanation, ONLY the JSON object"""

    outreach_results = {}

    for candidate in candidates:
        user_msg = f"""Job being offered:
{json.dumps(parsed_jd, indent=2)}

Candidate being contacted:
Name: {candidate.get('name')}
Current Role: {candidate.get('current_role')}
Availability: {candidate.get('availability')}
Actively Looking: {candidate.get('actively_looking')}
Summary: {candidate.get('summary')}

Simulate the recruiter outreach conversation."""

        raw    = call_groq(outreach_prompt, user_msg)
        result = safe_json_parse(raw)

        idx = str(candidate.get("idx", 0))

        if result and isinstance(result, dict):
            outreach_results[str(idx)] = {
                "messages":           result.get("messages", []),
                "interest_score":     result.get("interest_score", 50),
                "interest_rationale": result.get("interest_rationale", "")
            }
        else:
            outreach_results[idx] = {
                "messages":           [],
                "interest_score":     50,
                "interest_rationale": "Could not simulate conversation."
            }

    return jsonify({"success": True, "outreach": outreach_results})


# ════════════════════════════════════════════════════════════════════
# ROUTE 5: Build Final Ranked Shortlist
# MODULE 4 — Ranking Engine
# ════════════════════════════════════════════════════════════════════
@app.route("/build_shortlist", methods=["POST"])
def build_shortlist():
    """
    THE SCORING FORMULA:
    Final Score = (Match Score × 0.6) + (Interest Score × 0.4)
    
    Why 60/40?
    - Match Score weighted more: skills gaps are hard/slow to fix
    - Interest Score still matters a lot: 40% because a perfect-match
      candidate who doesn't care wastes everyone's time
    """
    data       = request.get_json()
    candidates = data.get("candidates", [])
    outreach   = data.get("outreach", {})
    parsed_jd  = data.get("parsed_jd", {})

    # ── Calculate final scores for all candidates ───────────────────
    for candidate in candidates:
        idx  = str(candidate.get("idx", 0)  )
        match_score    = candidate.get("match_score", 0)
        interest_score = outreach.get(idx, {}).get("interest_score", 0)

        # THE MAIN FORMULA
        final_score = round((match_score * 0.6) + (interest_score * 0.4))

        candidate["interest_score"] = interest_score
        candidate["final_score"]    = final_score

    # ── Sort by final score, highest first ──────────────────────────
    sorted_candidates = sorted(
        candidates,
        key=lambda c: c["final_score"],
        reverse=True
    )

    # ── Asking AI to write a recruiter recommendation ──────────────────
    rec_prompt = """You are a senior technical recruiter.
Given this ranked candidate shortlist, write a direct 3-sentence action plan:
1. Who to interview immediately and exactly why
2. Who to keep as backup
3. Any specific red flag or risk to watch

Be specific with names. No filler words."""

    shortlist_summary = [
        {
            "rank":         i + 1,
            "name":         c["name"],
            "role":         c["current_role"],
            "match":        c["match_score"],
            "interest":     c["interest_score"],
            "final":        c["final_score"],
            "availability": c["availability"]
        }
        for i, c in enumerate(sorted_candidates)
    ]

    user_msg = f"""Job: {parsed_jd.get('role')} ({parsed_jd.get('seniority')})

Ranked shortlist:
{json.dumps(shortlist_summary, indent=2)}

Write the 3-sentence recruiter action plan."""

    recommendation = call_groq(rec_prompt, user_msg)

    return jsonify({
        "success":        True,
        "shortlist":      sorted_candidates,
        "recommendation": recommendation
    })


# ════════════════════════════════════════════════════════════════════
# Start the server
# ════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  AI Talent Scout Agent (FREE - Powered by Groq)")
    print("  Open this in your browser:")
    print("  http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
