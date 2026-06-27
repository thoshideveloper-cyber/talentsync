"""
Synthetic "raw manager input" seeds — grounded in how managers ACTUALLY
communicate job requirements to HR in real companies.

Research finding: managers almost never write a full JD.
The real input arrives as one of four formats:
  A) 2-4 line email / Slack message
  B) Sparse intake form answers (fields mostly blank or vague)
  C) Copy-paste of an old JD ("same as last time, add Kafka")
  D) Notes from a verbal intake call (recruiter writes these up)

These seeds replicate those formats. They are SHORT, FRAGMENTED, and MISSING
key information — because that is what HR actually receives.

Ground truth fields (used by the eval harness):
  actual_seniority  — the TRUE level the text signals (not what the title says)
  skills_present    — skills actually mentioned
  has_bias          — biased / exclusionary language present
  salary_mentioned  — compensation info present
  input_format      — which of the 4 real-world formats this replicates
  mismatch          — True if stated/implied title contradicts text signals
"""

SEEDS = [

    # ── FORMAT A: short email / Slack ──────────────────────────────────────

    {
        "id": "seed_001",
        "role": "Backend Developer",
        "input_format": "slack_message",
        "actual_seniority": "Uncertain",
        "mismatch": False,
        "has_bias": True,
        "salary_mentioned": False,
        "skills_present": ["python"],
        "raw_jd": (
            "need someone for the data team, knows python and stuff, "
            "good attitude, rockstar mentality, will report to me, "
            "fast paced startup"
        ),
        # No years. No responsibilities. No scope. "Rockstar" bias.
        # This is the canonical example of what HR actually receives.
    },

    {
        "id": "seed_002",
        "role": "Frontend Developer",
        "input_format": "slack_message",
        "actual_seniority": "Entry-Level",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["react", "css", "html"],
        "raw_jd": (
            "hi we need a frontend person, freshers ok, "
            "react preferred, will build screens from figma. "
            "send cv to me directly"
        ),
    },

    {
        "id": "seed_003",
        "role": "Data Engineer",
        "input_format": "email",
        "actual_seniority": "Mid-Level",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": True,
        "skills_present": ["python", "spark", "airflow", "sql"],
        "raw_jd": (
            "Rahul - can you open a req for a data engineer? "
            "2-4 yrs, python spark airflow, they'll maintain our pipelines. "
            "budget is around 12-18 LPA. "
            "not a lead role, just an IC."
        ),
        # Email to HR. Has budget. Clear scope. IC = Individual Contributor,
        # signals no people management = Mid.
    },

    {
        "id": "seed_004",
        "role": "ML Engineer",
        "input_format": "slack_message",
        "actual_seniority": "Senior",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["pytorch", "python", "mlops", "llm"],
        "raw_jd": (
            "need a strong ml engineer, 6+ yrs, "
            "pytorch mlops experience, ideally llm background. "
            "will own the model infra and mentor the junior ml folks. "
            "report to vp eng."
        ),
        # Short but clear: 6+ yrs + mentoring + owns infra = Senior.
    },

    {
        "id": "seed_005",
        "role": "Product Manager",
        "input_format": "email",
        "actual_seniority": "Uncertain",
        "mismatch": False,
        "has_bias": True,
        "salary_mentioned": False,
        "skills_present": ["product", "agile"],
        "raw_jd": (
            "we need a pm, someone senior or mid we are flexible, "
            "good product sense, agile background, "
            "must be a go-getter who can hustle. "
            "young team, startup culture."
        ),
        # "Senior or mid we are flexible" + "young team" age signal = Uncertain + bias.
    },

    # ── FORMAT B: sparse intake form answers ───────────────────────────────

    {
        "id": "seed_006",
        "role": "DevOps Engineer",
        "input_format": "intake_form",
        "actual_seniority": "Senior",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": True,
        "skills_present": ["kubernetes", "terraform", "aws", "ci/cd"],
        "raw_jd": (
            "Job Title: DevOps / Infra (senior level)\n"
            "Key skills: k8s, terraform, AWS\n"
            "Experience: 5+ years\n"
            "Responsibilities: own the infra, set up SRE practices, "
            "lead infra migrations\n"
            "Reports to: CTO\n"
            "Salary: 25-35 LPA\n"
            "Team size: small, 2-3 people under this person\n"
            "Nice to have: python scripting"
        ),
        # Form format. Structured but sparse. Clear signals: 5+yrs, leads
        # migrations, people under = Senior.
    },

    {
        "id": "seed_007",
        "role": "UX Designer",
        "input_format": "intake_form",
        "actual_seniority": "Entry-Level",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["figma", "user research"],
        "raw_jd": (
            "Role: Designer (UI/UX)\n"
            "Experience: 0-1 year or fresher ok\n"
            "Tools: figma\n"
            "What they'll do: support the senior designer, "
            "make screens from wireframes\n"
            "Salary: not decided yet\n"
            "Other: good eye for design, eager to learn"
        ),
    },

    {
        "id": "seed_008",
        "role": "Data Scientist",
        "input_format": "intake_form",
        "actual_seniority": "Uncertain",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["python", "machine learning", "sql"],
        "raw_jd": (
            "Role: Data Scientist\n"
            "Skills needed: python, ML, sql\n"
            "Experience: experienced preferred\n"
            "What they do: analytics and models\n"
            "Salary: competitive\n"
            "Anything else: smart, independent"
        ),
        # "experienced preferred" + "competitive" = no real signals.
        # Classic underfilled intake form.
    },

    # ── FORMAT C: copy-paste of old JD ─────────────────────────────────────

    {
        "id": "seed_009",
        "role": "Android Developer",
        "input_format": "old_jd_copypaste",
        "actual_seniority": "Mid-Level",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["android", "java", "kotlin", "rest api"],
        "raw_jd": (
            "Android Developer (SDE 1 & 2)\n"
            "We are looking for an Android Developer with 2-4 years of "
            "experience in building consumer Android applications.\n"
            "Requirements:\n"
            "- Java/Kotlin\n"
            "- REST API integration\n"
            "- MVVM architecture\n"
            "[NOTE FROM MANAGER: same as last year's posting, "
            "please also add Flutter if possible, "
            "and remove the BlackBerry reference lol]"
        ),
        # Old JD with manager inline note. Common real-world format.
        # "Remove BlackBerry" shows how outdated copy-pastes get.
    },

    {
        "id": "seed_010",
        "role": "Backend Developer",
        "input_format": "old_jd_copypaste",
        "actual_seniority": "Senior",
        "mismatch": True,           # Old JD says "associate", role is now Senior
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["node.js", "mongodb", "aws", "system design"],
        "raw_jd": (
            "Associate Software Engineer - Backend\n"
            "Looking for someone to join the backend team.\n"
            "3+ years node.js, mongodb, AWS.\n"
            "You will design the architecture for our new platform, "
            "lead the backend squad of 4 engineers, "
            "and make technical hiring decisions.\n\n"
            "[Manager note: Priya said just reuse last year's JD but "
            "this is actually a senior IC role now, the title is wrong]"
        ),
        # Title says Associate. Text demands architecture, team lead,
        # hiring decisions. Classic mismatch. Even the manager knows
        # the title is wrong but didn't fix it.
    },

    # ── FORMAT D: recruiter notes from verbal intake call ──────────────────

    {
        "id": "seed_011",
        "role": "Engineering Manager",
        "input_format": "verbal_call_notes",
        "actual_seniority": "Executive",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": True,
        "skills_present": ["people management", "roadmap", "system design", "hiring"],
        "raw_jd": (
            "-- Notes from intake call with Ananya (CTO), 14 June --\n"
            "Looking for head of engineering, 10+ yrs, "
            "has managed managers before (not just ICs). "
            "Will define eng culture and own the technical roadmap. "
            "Reports directly to CEO. "
            "Has scaled team from 10 to 50+ before ideally. "
            "Budget: ESOPs + 60-80L. "
            "Ananya said: 'this is basically a co-founder level hire'"
        ),
        # Notes format with timestamp and attribution. Common when
        # recruiter documents what was said on a call.
    },

    {
        "id": "seed_012",
        "role": "Full Stack Developer",
        "input_format": "verbal_call_notes",
        "actual_seniority": "Mid-Level",
        "mismatch": False,
        "has_bias": True,
        "salary_mentioned": False,
        "skills_present": ["react", "node.js", "postgresql"],
        "raw_jd": (
            "-- Call notes from Vikram (Product Lead) --\n"
            "Needs a fullstack dev, react + node, postgres. "
            "2-4 years. Not a senior, just someone who can ship. "
            "Young team, needs good energy, "
            "must be a cultural fit with startup hustle. "
            "Vikram said he'll know the right person when he sees them "
            "(no further clarity given on what that means)."
        ),
        # "Young team" bias. "I'll know when I see them" = vague beyond
        # the technical requirements. Real recruiter frustration moment.
    },

    # ── MISMATCH cases (title says X, text says Y) ─────────────────────────

    {
        "id": "seed_013",
        "role": "Software Engineer",
        "input_format": "slack_message",
        "actual_seniority": "Entry-Level",
        "mismatch": True,           # title says "senior", text is entry-level
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["java", "spring boot", "mysql"],
        "raw_jd": (
            "senior software engineer opening on our team. "
            "java spring boot mysql. "
            "1-2 yrs exp is fine. "
            "will get tasks from the tech lead and code them up. "
            "good for someone who wants to learn."
        ),
        # "Senior" title + "1-2 yrs" + "get tasks from tech lead"
        # + "wants to learn" = Entry-Level. Classic mismatch to
        # attract good people with an inflated title.
    },

    {
        "id": "seed_014",
        "role": "Data Scientist",
        "input_format": "intake_form",
        "actual_seniority": "Senior",
        "mismatch": True,           # form says "junior", text is Senior
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["python", "machine learning", "statistics", "deep learning"],
        "raw_jd": (
            "Role: Junior Data Scientist\n"
            "Experience: 7+ years in ML/data science\n"
            "Responsibilities: define ML strategy for the company, "
            "publish research, represent company at conferences, "
            "build and hire a team of 5 data scientists\n"
            "Reports to: CTO"
        ),
        # "Junior" + "7+ yrs" + "define strategy" + "build a team" = Senior.
        # Manager used "Junior" because they don't know the levels.
    },

    # ── GENUINELY UNCERTAIN (not enough signal either way) ─────────────────

    {
        "id": "seed_015",
        "role": "Backend Developer",
        "input_format": "slack_message",
        "actual_seniority": "Uncertain",
        "mismatch": False,
        "has_bias": False,
        "salary_mentioned": False,
        "skills_present": ["node.js", "mongodb"],
        "raw_jd": (
            "backend dev needed. "
            "node and mongo. "
            "salary negotiable. good culture. "
            "apply if interested."
        ),
        # Absolute minimum. No years, no scope, no reporting, no level.
        # Impossible to classify with confidence.
    },
]
