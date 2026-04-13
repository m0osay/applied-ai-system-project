# PawPal+

<a href="img.png" target="_blank"><img src="img.png" title="PawPal App" alt="PawPal App" width="900" /></a>

---

## Original Project

This project extends **PawPal+ (Module 2)**. The original project was a rule-based pet care task scheduler that helped busy pet owners manage daily care tasks across multiple pets. It let users add pets and tasks, generate a priority-sorted daily plan within a set time budget, detect scheduling conflicts, and view skipped tasks — all through a Streamlit web interface with no AI integration.

---

## Title and Summary

**PawPal+** is an AI-powered pet care assistant that schedules daily tasks and uses a Gemini Flash agentic workflow to identify care gaps your schedule may have missed. It matters because rule-based schedulers can only work with what you give them — the AI layer catches what you forgot, like the fact that your senior cat hasn't had any enrichment scheduled this week, and tells you whether there's still time to fit it in today.

---

## Architecture Overview

![PawPal+ System Architecture](assets/architecture.png)

The system has three layers:

1. **Input layer** — The user adds pets (name, species, age) and tasks (description, time, priority, duration) through the Streamlit UI.
2. **Scheduling layer** — `pawpal_system.py` runs a deterministic greedy scheduler: it filters pending tasks, sorts by time → priority → duration, allocates within the available time budget, and flags conflicts and skipped tasks.
3. **AI layer** — After the plan is built, `gemini_agent.py` runs a two-step Gemini Flash loop. The first call identifies care gaps not covered in the schedule. The second call validates each suggestion against remaining available time, marking suggestions as actionable today or deferred to tomorrow. Results are displayed in an expander below the schedule.

Logging runs throughout the AI layer. Three-layer error handling ensures the app never crashes — if the API key is missing or a call fails, it shows a warning and falls back gracefully.

| Component | File | Role |
|---|---|---|
| Streamlit UI | `app.py` | User input, schedule display, AI insights expander |
| Scheduler | `pawpal_system.py` | Rule-based task filtering, sorting, plan generation |
| AI Agent | `gemini_agent.py` | 2-step Gemini loop: identify gaps → validate suggestions |
| Tests | `tests/test_pawpal.py` | Scheduler logic + agent fallback behavior |

---

## Setup Instructions

### 1. Clone the repo and create a virtual environment

```bash
git clone <repo-url>
cd applied-ai-system-project
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Gemini API key

Get a free key from [aistudio.google.com](https://aistudio.google.com), then:

```bash
cp .env.example .env
# Open .env and replace "your_key_here" with your actual key
```

### 4. Run the app

```bash
streamlit run app.py
```

Open the local URL shown in your terminal. Add a pet, add tasks, and click **Generate schedule** to see the rule-based plan and AI care gap analysis.

> **No API key?** The app still runs fully — it shows a graceful warning in the AI section instead of crashing.

---

## Sample Interactions

### Example 1 — Dog with only feeding scheduled

**Input:**
- Pet: Luna, dog, 4 years old
- Task: Morning feeding (08:00, 10 min, high priority)
- Available time: 90 minutes

**AI output (Plan call → Check call):**
> *"Luna's schedule only includes feeding, with no physical activity. A 4-year-old dog typically needs 30–60 minutes of exercise daily to maintain healthy weight and behavior."*
>
> **Actionable today:** "Take Luna for a 30-minute walk" — fits within remaining 80 minutes.
> **Overall note:** Luna's basic needs are met but physical activity is missing from today's plan.

---

### Example 2 — Senior cat with a full but narrow schedule

**Input:**
- Pet: Mochi, cat, 9 years old
- Tasks: Feeding (08:00, 10 min), Medication (09:00, 5 min)
- Available time: 20 minutes

**AI output:**
> *"Mochi's schedule covers nutrition and medication but no mental stimulation. Senior cats benefit greatly from enrichment to slow cognitive decline."*
>
> **Deferred to tomorrow:** "10-minute interactive play session" — only 5 minutes remain after scheduling, not enough time today.
> **Overall note:** Mochi's medical and nutritional needs are covered. Enrichment should be added to tomorrow's plan.

---

### Example 3 — Multiple pets, time budget exceeded

**Input:**
- Pet 1: Rex, dog, 2 years old — Walk (08:00, 45 min), Training (09:00, 30 min)
- Pet 2: Bella, cat, 3 years old — Feeding (08:30, 10 min)
- Available time: 60 minutes (training skipped — ran out of time)

**AI output:**
> *"Rex's training session was skipped due to time constraints. Young dogs benefit from consistent daily training to reinforce positive behavior."*
>
> **Actionable today:** "5-minute obedience training refresher" — a shorter version fits in the 15 remaining minutes.
> **Overall note:** Core care for both pets is covered. Rex's training gap is the priority to address — even a shortened session helps with consistency.

---

## Design Decisions

**Why Gemini Flash over a larger model?**
This is a course project running on a free API tier. Flash is fast, capable enough for structured JSON output, and keeps latency low so the UI doesn't feel slow after hitting "Generate schedule."

**Why two separate Gemini calls instead of one?**
Splitting into a Plan call and a Check call improves output quality. A single prompt asking Gemini to both identify gaps and validate them against time constraints produces less reliable results. Separating the concerns gives each call a focused task and makes the agentic loop easier to debug.

**Why not RAG?**
RAG would require building and maintaining a vector knowledge base of pet care information. For a scheduler that already knows the pet's species and age, the Gemini model's built-in knowledge is sufficient — adding a retrieval layer would increase complexity without meaningfully improving output quality for this use case.

**Why keep the rule-based scheduler?**
Letting the AI fully own scheduling would make the system a black box and harder to debug. The deterministic scheduler handles the allocation logic reliably, and the AI layer adds value on top by reasoning about what's missing — a clear separation of concerns.

**Trade-off: Greedy scheduling vs. optimal packing**
The scheduler allocates tasks in sorted order and skips any that don't fit. A proper bin-packing algorithm could fit more tasks in, but it adds complexity for marginal gain on small task sets typical of a household pet schedule.

---

## Testing Summary

**What worked:**
- All 8 tests pass, including 2 new offline agent tests that verify fallback behavior without needing a real API key.
- The three-layer error handling (missing key, API failure, malformed JSON) all behave as expected — the app never crashes.
- The JSON fence-stripping in `_parse_json` handles Gemini's tendency to wrap responses in markdown code blocks.

**What didn't work initially:**
- `google-generativeai` (the original SDK) is fully deprecated — switched to `google-genai`.
- `gemini-1.5-flash` model IDs are no longer valid in the new SDK — now using `models/gemini-2.0-flash-lite`.
- Free tier quota limits can block calls during heavy testing — the fallback prevents this from breaking the UI.

**What I learned:**
- Testing AI fallback paths is more important than testing the happy path — the happy path depends on an external API you don't control.
- Structured JSON prompts are fragile: even small wording changes can cause the model to add prose or omit required keys. Defensive parsing (stripping fences, using `.get()` with defaults) is essential.

---

## Reflection

Building PawPal+ taught me that AI works best as a reasoning layer on top of reliable deterministic logic — not as a replacement for it. The scheduler handles what it's good at (sorting, time allocation, conflict detection), and the AI handles what it's good at (open-ended reasoning about what's missing and why it matters).

The hardest part wasn't the code — it was writing prompts that consistently return structured output. Getting Gemini to return clean JSON required iteration: separating the two calls, being explicit about format, and building parsing that handles malformed responses without crashing.

It also reinforced that reliability engineering matters as much as the feature itself. The three-layer error handling and offline tests mean the app works even when the API doesn't — which is exactly the kind of robustness a real system needs.
