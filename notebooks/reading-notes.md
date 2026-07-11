# Reading Notes — Manual Transcript Review (Week 1)

These notes become the **manual test cases** for validating LLM scores in Phase 2.
Read 5+ transcripts end-to-end. For each suspicious/evasive passage, log it here.
Later, the LLM's dimension scores (evasiveness, sentiment shift, etc.) are checked against these human labels.

---

## Template per Transcript

### Company: [e.g., TCS]
**Quarter:** [e.g., Q1 2025]  
**File:** [e.g., TCS_Q1_2025.pdf]

| # | Quote (with page/line if possible) | Why it felt evasive/off (1–2 lines) | Confidence (low/med/high) |
|---|-------------------------------------|--------------------------------------|----------------------------|
| 1 |                                     |                                      |                            |
| 2 |                                     |                                      |                            |
| 3 |                                     |                                      |                            |

---

### Company: [e.g., INFY]
**Quarter:** [e.g., Q3 2024]  
**File:** [e.g., INFY_Q3_2024.pdf]

| # | Quote (with page/line if possible) | Why it felt evasive/off (1–2 lines) | Confidence (low/med/high) |
|---|-------------------------------------|--------------------------------------|----------------------------|
| 1 |                                     |                                      |                            |
| 2 |                                     |                                      |                            |
| 3 |                                     |                                      |                            |

---

### Company: [e.g., HDFCBANK]
**Quarter:** [e.g., Q2 2025]  
**File:** [e.g., HDFCBANK_Q2_2025.pdf]

| # | Quote (with page/line if possible) | Why it felt evasive/off (1–2 lines) | Confidence (low/med/high) |
|---|-------------------------------------|--------------------------------------|----------------------------|
| 1 |                                     |                                      |                            |
| 2 |                                     |                                      |                            |
| 3 |                                     |                                      |                            |

---

### Company: [e.g., WIPRO]
**Quarter:** [e.g., Q4 2024]  
**File:** [e.g., WIPRO_Q4_2024.pdf]

| # | Quote (with page/line if possible) | Why it felt evasive/off (1–2 lines) | Confidence (low/med/high) |
|---|-------------------------------------|--------------------------------------|----------------------------|
| 1 |                                     |                                      |                            |
| 2 |                                     |                                      |                            |
| 3 |                                     |                                      |                            |

---

### Company: [e.g., RELIANCE]
**Quarter:** [e.g., Q1 2025]  
**File:** [e.g., RELIANCE_Q1_2025.pdf]

| # | Quote (with page/line if possible) | Why it felt evasive/off (1–2 lines) | Confidence (low/med/high) |
|---|-------------------------------------|--------------------------------------|----------------------------|
| 1 |                                     |                                      |                            |
| 2 |                                     |                                      |                            |
| 3 |                                     |                                      |                            |

---

## What to look for (quick cheat sheet)

| Dimension | Red-flag phrasing examples |
|-----------|----------------------------|
| **Evasiveness** | "We don't break that out", "It's too early to say", "I'd rather not comment on specifics" |
| **Sentiment shift** | Sudden drop in positive language vs prior quarter; hedging where confidence was high before |
| **Complexity spike** | Jargon density jumps; sentences >40 words; nested qualifiers ("broadly speaking, generally...") |
| **Overpromising** | "Best quarter ever" without numbers; "significant upside" with no quantifiable driver |
| **Forward guidance vagueness** | "We remain optimistic", "well positioned", "multiple levers" — no numbers, no timeline |

> **Tip:** Note the *section* (Prepared Remarks vs Q&A) — evasion in Q&A is stronger signal.