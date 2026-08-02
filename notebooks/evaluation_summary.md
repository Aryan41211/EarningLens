# Evaluation Summary — Evasiveness Dimension

> Tracker for human review of all evasiveness-scored transcripts.
> Fill in "Human Reviewed" and "Agreement" after completing your review.

---

## Summary Table

| Company | Quarter | Year | LLM Score | Keyword Count | Supporting Quotes | Human Reviewed | Agreement |
|---------|---------|------|-----------|---------------|-------------------|----------------|-----------|
| INFY | Q1 | 2023 | 7 | 5 | 3 | ❌ | |
| INFY | Q1 | 2024 | 6 | 14 | 3 | ❌ | |
| INFY | Q2 | 2024 | 6 | 19 | 3 | ❌ | |
| INFY | Q4 | 2025 | 6 | 18 | 3 | ❌ | |
| TCS | Q2 | 2023 | 6 | 2 | 3 | ❌ | |
| TCS | Q3 | 2023 | 6 | 4 | 3 | ❌ | |
| TCS | Q1 | 2024 | 7 | 5 | 3 | ❌ | |
| TCS | Q2 | 2024 | 4 | 3 | 3 | ❌ | |
| TCS | Q3 | 2024 | 6 | 5 | 3 | ❌ | |
| TCS | Q1 | 2025 | 6 | 2 | 3 | ❌ | |
| TCS | Q4 | 2025 | 4 | 8 | 3 | ❌ | |

---

## Score Distribution

| Score Range | Count | Transcripts |
|-------------|-------|-------------|
| 1–3 (LOW) | 0 | — |
| 4–6 (MODERATE) | 9 | INFY Q1 2024, INFY Q2 2024, INFY Q4 2025, TCS Q2 2023, TCS Q3 2023, TCS Q2 2024, TCS Q3 2024, TCS Q1 2025, TCS Q4 2025 |
| 7–9 (HIGH) | 2 | INFY Q1 2023, TCS Q1 2024 |
| 10 (EXTREME) | 0 | — |

---

## Keyword vs. LLM Score Comparison

| Transcript | LLM Score | Keyword Count | Notable Pattern |
|------------|-----------|---------------|-----------------|
| INFY Q1 2023 | 7 | 5 | High score, low keyword count — LLM detected evasion beyond keywords |
| INFY Q1 2024 | 6 | 14 | Moderate score, high keyword count — keywords align with score |
| INFY Q2 2024 | 6 | 19 | Moderate score, highest keyword count — "at this point" dominates |
| INFY Q4 2025 | 6 | 18 | Moderate score, high keyword count — "difficult to say" frequent |
| TCS Q2 2023 | 6 | 2 | Moderate score, very low keyword count — LLM-driven scoring |
| TCS Q3 2023 | 6 | 4 | Moderate score, low keyword count — LLM-driven scoring |
| TCS Q1 2024 | 7 | 5 | High score, low keyword count — LLM detected evasion beyond keywords |
| TCS Q2 2024 | 4 | 3 | Low-moderate score, low keyword count — relatively direct answers |
| TCS Q3 2024 | 6 | 5 | Moderate score, moderate keyword count — balanced signal |
| TCS Q1 2025 | 6 | 2 | Moderate score, very low keyword count — LLM-driven scoring |
| TCS Q4 2025 | 4 | 8 | Low-moderate score, moderate keyword count — mixed signal |

---

## Priority Review

### 1. High-Score Transcripts (Score ≥ 7)

| Transcript | Score | Why Review |
|------------|-------|------------|
| **INFY Q1 2023** | 7 | Highest INFY score. Management refuses to quantify guidance factors ("not in a position to quantify"). Refuses to share internal leading indicators ("not typically data we share externally"). Verify if this is justified caution or genuine evasion. |
| **TCS Q1 2024** | 7 | Highest TCS score. Krithivasan refuses to confirm bottom in North America ("I don't want to say this now"). Defers analyst request ("we'll have an internal discussion"). Verify if this reflects actual evasiveness or appropriate caution during volatile period. |

### 2. Low-Score Transcripts (Score ≤ 4)

| Transcript | Score | Why Review |
|------------|-------|------------|
| **TCS Q2 2024** | 4 | Lowest TCS score. Management provides specific margin target (26-28%), acknowledges uncertainty directly, gives conditional growth outlook. Verify if this is genuinely less evasive or if the model under-scored. |
| **TCS Q4 2025** | 4 | Lowest TCS score (tied). Management openly discusses TCV unpredictability, acknowledges global monitoring. Verify if closing remarks optimism ("cautious optimism") should have increased evasiveness score. |

### 3. Keyword/LLM Divergence (High keyword count, moderate score or vice versa)

| Transcript | LLM Score | Keyword Count | Divergence |
|------------|-----------|---------------|------------|
| **INFY Q2 2024** | 6 | 19 | Highest keyword count but moderate LLM score. "At this point" appears 12 times — verify if LLM correctly assessed this as moderate rather than high evasiveness. |
| **TCS Q2 2023** | 6 | 2 | Very low keyword count but moderate LLM score. Only 2 dodge phrases found — verify if LLM correctly identified evasion beyond keyword patterns. |
| **TCS Q1 2025** | 6 | 2 | Very low keyword count but moderate LLM score. Only 2 dodge phrases found — verify if LLM correctly identified evasion beyond keyword patterns. |
| **TCS Q4 2025** | 4 | 8 | Moderate keyword count but low LLM score. 8 dodge phrases including 3 "going forward" — verify if LLM correctly down-scored despite keyword presence. |

### 4. "At This Point" Frequency

The phrase "at this point" is the most frequent dodge phrase across all transcripts:

| Transcript | Count |
|------------|-------|
| INFY Q2 2024 | 12 |
| INFY Q1 2024 | 11 |
| INFY Q4 2025 | 9 |
| TCS Q1 2024 | 2 |
| TCS Q4 2025 | 2 |
| INFY Q1 2023 | 1 |
| TCS Q2 2023 | 1 |
| TCS Q3 2024 | 1 |

**Review question:** Is "at this point" a genuine evasion marker or a common speech filler in Indian English?

### 5. "Going Forward" Frequency

| Transcript | Count |
|------------|-------|
| TCS Q4 2025 | 3 |
| INFY Q2 2024 | 3 |
| INFY Q1 2024 | 2 |
| TCS Q2 2024 | 2 |
| TCS Q3 2024 | 2 |
| TCS Q1 2025 | 1 |

**Review question:** Is "going forward" a genuine evasion marker or standard corporate language?

---

## Files Created

| File | Purpose |
|------|---------|
| `notebooks/reading-notes.md` | Human evaluation worksheet with all quotes and context |
| `notebooks/findings.md` | Empty templates for documenting evaluation findings |
| `notebooks/evaluation_summary.md` | This file — summary table, priority review, distribution |

---

## Data Verification

- **Total transcripts scored:** 11
- **Total supporting quotes:** 33
- **Companies:** TCS (7), INFY (4)
- **Score range:** 4–7
- **No files modified** outside `notebooks/`
- **No database rows changed**
- **No scores changed**
- **No prompts changed**
- **No LLM calls executed**
