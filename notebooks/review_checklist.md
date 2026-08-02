# Review Checklist — Evasiveness Dimension

> Check each box as you complete it. This is your task tracker.

---

## Phase 1: Data Verification

- [ ] Database has 11 evasiveness scores
- [ ] No orphaned scores (every score links to a valid transcript chunk)
- [ ] No duplicate scores (same transcript + dimension scored twice)
- [ ] All scores are between 1 and 10
- [ ] All scores are integers (not floats)

---

## Phase 2: Quote Verification

For each transcript, check that the supporting quotes:

- [ ] **INFY Q1 2023** — Quotes match actual transcript text
- [ ] **INFY Q1 2024** — Quotes match actual transcript text
- [ ] **INFY Q2 2024** — Quotes match actual transcript text
- [ ] **INFY Q4 2025** — Quotes match actual transcript text
- [ ] **TCS Q2 2023** — Quotes match actual transcript text
- [ ] **TCS Q3 2023** — Quotes match actual transcript text
- [ ] **TCS Q1 2024** — Quotes match actual transcript text
- [ ] **TCS Q2 2024** — Quotes match actual transcript text
- [ ] **TCS Q3 2024** — Quotes match actual transcript text
- [ ] **TCS Q1 2025** — Quotes match actual transcript text
- [ ] **TCS Q4 2025** — Quotes match actual transcript text

---

## Phase 3: Score Validation

For each transcript, check that the score is justified:

- [ ] **INFY Q1 2023** — Score 7 is ___ (justified / too high / too low)
- [ ] **INFY Q1 2024** — Score 6 is ___ (justified / too high / too low)
- [ ] **INFY Q2 2024** — Score 6 is ___ (justified / too high / too low)
- [ ] **INFY Q4 2025** — Score 6 is ___ (justified / too high / too low)
- [ ] **TCS Q2 2023** — Score 6 is ___ (justified / too high / too low)
- [ ] **TCS Q3 2023** — Score 6 is ___ (justified / too high / too low)
- [ ] **TCS Q1 2024** — Score 7 is ___ (justified / too high / too low)
- [ ] **TCS Q2 2024** — Score 4 is ___ (justified / too high / too low)
- [ ] **TCS Q3 2024** — Score 6 is ___ (justified / too high / too low)
- [ ] **TCS Q1 2025** — Score 6 is ___ (justified / too high / too low)
- [ ] **TCS Q4 2025** — Score 4 is ___ (justified / too high / too low)

---

## Phase 4: Pattern Checks

- [ ] INFY scores are consistent (all 6-7, no outliers)
- [ ] TCS scores show reasonable variation (4-7 range)
- [ ] "NOT FOUND in chunk" quotes were still evaluated correctly
- [ ] No false positives (transcript scored as evasive when it's transparent)
- [ ] No false negatives (transparent response scored as evasive)

---

## Phase 5: Summary

**Total transcripts reviewed:** ___ / 11

**Findings recorded in findings.md:** ___

**Overall assessment:**

- [ ] All scores are accurate — no changes needed
- [ ] Some scores need adjustment — list in findings.md
- [ ] Prompt needs updating — note specific issues in findings.md

---

## Final Sign-off

- [ ] I have reviewed all 11 transcripts
- [ ] I have reviewed all 33 supporting quotes (3 per transcript)
- [ ] I have filled in all blank fields in reading-notes.md
- [ ] I have documented all findings in findings.md
- [ ] I am confident in my assessment

**Reviewer:** ________________________

**Date:** ________________________

**Signature:** ________________________
