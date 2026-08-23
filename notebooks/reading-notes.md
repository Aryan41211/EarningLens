# Human Review — Evasiveness Scores

> **Goal**: Validate whether the LLM's evasiveness scores (4–7) are justified
> for each transcript. For each one, read the supporting quotes and context,
> then answer the review questions below.
>
> **Note (2026-08-23):** the per-transcript field below was originally labelled
> "Accuracy", which read as *how accurate was the LLM* but was in fact being
> used for *the reviewer's own evasiveness score*. Confirmed with the reviewer
> and relabelled. These 11 numbers are the project's ground truth and are
> exported to `notebooks/labels.csv`.
>
> **Scoring scale**: 1–10 (1 = fully transparent, 10 = extremely evasive)

---

## Summary

| Transcript | LLM Score | Your Score | Verdict |
|---|---|---|---|
| INFY Q1 2023 | 7 | ___ | ✓ / ✗ |
| INFY Q1 2024 | 6 | ___ | ✓ / ✗ |
| INFY Q2 2024 | 6 | ___ | ✓ / ✗ |
| INFY Q4 2025 | 6 | ___ | ✓ / ✗ |
| TCS Q2 2023 | 6 | ___ | ✓ / ✗ |
| TCS Q3 2023 | 6 | ___ | ✓ / ✗ |
| TCS Q1 2024 | 7 | ___ | ✓ / ✗ |
| TCS Q2 2024 | 4 | ___ | ✓ / ✗ |
| TCS Q3 2024 | 6 | ___ | ✓ / ✗ |
| TCS Q1 2025 | 6 | ___ | ✓ / ✗ |
| TCS Q4 2025 | 4 | ___ | ✓ / ✗ |

---

## INFY Q1 2023 — Score: 7/10

### Supporting Quotes

**Q1:** *"We will not be in a position to quantify that further between those two, unfortunately."*

**Q2:** *"So there, my sense is, again, some of the comments you might have heard earlier from Nilanjan, our utilization has gone up. Our total headcount number is reduced, and we believe, we have some headroom for the utilization to go up further. So that would be the context in which we are operating."*

**Q3:** *"So internally, we have several elements, that we look at. These are not typically data we share externally."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 3 / 10

**Justification:**

> Q1 is clearly a dodge with no reason given.
> Q2 is what i think is more clearer coz they have given reasons 
> In Q3 they have not directly dodged but they have given a valid reson i.e they don't share that info externally

**Key missed context:** (what the LLM may not have considered)

> Q1 is having a rude tonality and they are refusing it very straight forwardly. 
> Q2 sounds more professional and it clearly states the resons, the valid reasons and used professional language. 
> After reading Q3 i think they want to sound mysterious and they don't want to share more info abt themself and i also think they are neglecting it by not giving actual reasins

**Verdict:** ✓ Matches my read / ✗ Doesn't match / ⚠ Partially
Doesn't match
---

## INFY Q1 2024 — Score: 6/10

### Supporting Quotes

**Q1:** *"So, depending on which end of the guidance you are looking at, the seasonality will also change, uncertainty will also change. But outside of that, we are expecting normal seasonality."*

**Q2:** *"The reason that we gave a 3-point guidance band was because there is an uncertainty. So, at the lower end of the guidance, we have baked in some further deterioration in the environment. And at the top end of the guidance, we have baked in steady to marginally improving environment."*

**Q3:** *"We do not give quarterly guidance. So, we are going to stick to our overall guidance and that is what we see today."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 2 / 10

**Justification:**

> In Q1 they are trying to put out their opinion with the real facts and practical thinking.
> In Q2 they are essenitally defending why they gave the range instead of single forecast. Good justification, but somewhat vague. I'd want evidence behind the assumptions.
> In Q3 This one feels the most like management drawing a boundary.

**Key missed context:**

> In Q1, they are trying to make us correct by real facts. They don't see an unusual seasonal pattern as the main risk. This sounds fairly reasonable, but also a little carefully worded.They aren't blaming seasonality for everything.
> In Q2, they have created two scenarios and they are giving guidance to cover both off them.In this they are trying to say "Our underlying business expectations are reasonably clear, but the external operating environment can move our results up or down"
> Q3, This one feels the most like management drawing a boundary. Reasonable policy, but it limits transparency on the near term. I don't see it as inherently negative, but it means investors have to rely on the broader guidance rather than getting visibility into the next quarter.

**Verdict:** ✓ Matches my read / ✗ Doesn't match / ⚠ Partially
Doesn't match
---

## INFY Q2 2024 — Score: 6/10

### Supporting Quotes

**Q1:** *"We do not really break up that cost further."*

**Q2:** *"We have not really spelled out the quantum of the wage hike at this point in time."*

**Q3:** *"We do not share specific data on what is in the pipeline and not."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 9 / 10

**Justification:**

> In Q1 they are saying that they will not give further breakdown of the price(Detailed breakdown of price) that they have said
> In Q2 Yes, there will be a wage increase, but we're not telling you the percentage/amount yet.
> In Q3 THey are clearly rejecting what have being asked to them. 

**Key missed context:**

> In Q1, they are hiding smthing that they think that we should not know. they are being more direct in this. Sounds very Unprofessional. Not necessarily suspicious, but low transparency.
> In Q2, Lack of transparency. Won't disclose wage-hike magnitude.
> In Q3, Clearly rejecting abt what have been asked to them, creating strong boundries and rejecting in professional terms and trying to creat the mystery abt themselfs

**Verdict:** ✓ Matches my read / ✗ Doesn't match / ⚠ Partially
Doesn't match
---

## INFY Q4 2025 — Score: 6/10

### Supporting Quotes

**Q1:** *"So, there the view we have is what we saw, and we have highlighted so far. The shift in Financial Services in the U.S. shows that some of that type of demand is coming now. We will wait and see across all the industries, whether it is what you are describing, or whether tech services project discretionary work also comes back or whether there will be transformation programs in tech which will also come."*

**Q2:** *"That is difficult to say. So again, it is just this year, one quarter, what we saw was that in Financial Services U.S. some of that discretionary work is there. Whether it was decoupled or following on from something, difficult to say but we did see some evidence of that."*

**Q3:** *"So, the way this quarter has gone, what we have seen is the volumes have been strong. We have then seen that change in the Financial Services in the U.S. which has given us more positive outcome for the quarter. Then some of the work that we are doing in terms of working with our clients on value and pricing has also translated overall into the mix for our revenue."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 3 / 10

**Justification:**

> Q1 they are actually giving a proper answer, not dodging, just saying they'll wait and watch across industries.
> Q2 "That is difficult to say" sounds evasive at first but then they still give the actual color (Financial Services US), so it's not a real dodge.
> Q3 this is a full answer, volumes, FS shift, pricing work, all explained. No dodge here at all.

**Key missed context:**

> In Q1 and Q3 they are actually being pretty open, giving real reasons and real business detail, not just boundary lines like in the INFY Q1/Q2 2024 examples.
> In Q2 the "difficult to say" is more of a genuine hedge on cause (decoupled or not) than refusing to answer, they still answer the main question.
> I think LLM is reading "difficult to say" phrases as evasive by default without checking if info was still given after that line.

**Verdict:** ✓ Matches my read / ✗ Doesn't match / ⚠ Partially
Doesn't match
---

## TCS Q2 2023 — Score: 6/10

### Supporting Quotes

**Q1:** *"All these factors are at play, but how long this will last is not a question that we can answer at this time."*

**Q2:** *"We manage margins at an overall portfolio level, and don't call out deal-specific headwinds."*

**Q3:** *"I think all directions indicate that this is something that will mature and the potential for embedding it and embracing it all across our IT services value chain is huge."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 4 / 10

**Justification:**

> Q1 "how long this will last is not a question we can answer" sounds like genuine uncertainty, not really them hiding something.
> Q2 "we manage margins at overall portfolio level and don't call out deal-specific headwinds" this is a clear policy line, similar to INFY saying they don't share data externally.
> Q3 this is them actually giving their opinion/view on GenAI maturing, so this is more transparent, not evasive.

**Key missed context:**

> Q2 is the only real "boundary" quote here, feels like a company policy reason, not rude, fairly professional.
> Q1 and Q3 are them actually engaging with the question and giving their honest take, so overall this whole set feels less evasive than a 6.
> I think LLM is scoring the whole transcript based on Q2 alone and carrying that score onto Q1 and Q3 which don't deserve it.

**Verdict:** ✗ Doesn't match

---

## TCS Q3 2023 — Score: 6/10

### Supporting Quotes

**Q1:** *"We don't see current quarter's TCV as a great big variation from what we had in the previous quarter."*

**Q2:** *"We have not heard any specific color. And two, given the overall uncertainty, we find our clients are also very agile, even though they may have some thought in terms of what they want to spend, but we find that they also keep reacting to the market sentiment."*

**Q3:** *"We have not started to give that out, and let's hope that this year, augurs well for us to give you more color on all of this."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 5 / 10

**Justification:**

> Q1 direct comparison answer, no dodge, they are actually comparing TCV quarter on quarter.
> Q2 they are explaining client behaviour (agile, reacting to sentiment) which is a real reason, feels honest.
> Q3 "we have not started to give that out, let's hope this year augurs well" this is the real dodge here, boundary + soft hope statement to cushion it.

**Key missed context:**

> Q3 is doing the same thing as INFY Q1 2023's "not typically data we share" line, drawing a boundary but wrapped in a hopeful tone so it doesn't sound rude.
> Q1 and Q2 are genuinely answering, so only 1 out of 3 quotes here is a real dodge.
> I think this transcript is a bit less evasive than INFY Q1 2023 because tone is softer and only one quote is a clear non-answer.

**Verdict:** ⚠ Partially

---

## TCS Q1 2024 — Score: 7/10

### Supporting Quotes

**Q1:** *"We don't know, overall situation remains volatile. So, that is the reason we are continuing to stay cautious on our outlook for the next few quarters."*

**Q2:** *"I don't want to say this now because it's the first quarter of broad-based growth we have seen after few quarters."*

**Q3:** *"We will consider your request and we'll have an internal discussion and come back to you."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 6 / 10

**Justification:**

> Q1 they give an actual reason (situation remains volatile) for staying cautious, this is more explanation than dodge.
> Q2 "I don't want to say this now" is a real dodge, feels like they don't want to jinx the good quarter, kind of superstitious reasoning but still a non-answer.
> Q3 "we will consider your request and have internal discussion and come back to you" this is classic corporate deflection, no commitment, no timeline.

**Key missed context:**

> Q2 and Q3 together feel like a real pattern of avoiding commitment, this is why this transcript deserves a higher score than the TCS Q2/Q3 2023 ones.
> Q1 is not really evasive on its own, so the 7 score is being carried mostly by Q2 and Q3.
> Q3 in particular is a "we'll get back to you" line which basically means no answer at all right now.

**Verdict:** ⚠ Partially

---

## TCS Q2 2024 — Score: 4/10

### Supporting Quotes

**Q1:** *"We don't expect the dynamics to change considerably."*

**Q2:** *"We'd like to get to 26% to 28% or nearer to 26% as soon as possible. Given how the macros are stacked up we can't tell you whether it is in the immediate quarter or two quarters or three quarters or four, but we'd like to get to it."*

**Q3:** *"We believe that once the uncertainties are clear and once we enter a more stable situation, we believe the growth should also return."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 4 / 10

**Justification:**

> Q1 simple direct answer, no real dodge.
> Q2 this one actually gives the target range (26-28%) and is honest that they can't predict timing because of macros, this is transparent even though it sounds hesitant.
> Q3 general forward looking statement, but it's tied to a real condition (uncertainty clearing), not just vague fluff.

**Key missed context:**

> Q2 looks evasive on the surface ("can't tell you") but they immediately explain why (macro dependent) and still give the actual target number, so this is more honest than it first appears.
> None of these 3 quotes are a hard boundary line or a flat refusal like "we don't share that info."
> I think this is genuinely one of the lower evasiveness transcripts, so LLM got this one about right.

**Verdict:** ✓ Matches

---

## TCS Q3 2024 — Score: 6/10

### Supporting Quotes

**Q1:** *"I don't think the discretionary spend will be visibly resistant to macro change. The comment I made is based on what we are seeing today, based on the discussions we are having and the pipeline that we are seeing in front of us."*

**Q2:** *"Too early to call out, Manik. At this time, most of the deals are all in the traditional models only, while people are discussing what options could exist."*

**Q3:** *"We are not guiding to a double-digit growth, but we are expecting a stronger growth."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 5 / 10

**Justification:**

> Q1 they actually explain their reasoning (based on discussions, pipeline), feels honest.
> Q2 "too early to call out" is a soft dodge but they still give context (deals still in traditional models), so it's not a full refusal.
> Q3 "we are not guiding to double digit but expecting stronger growth" this is actually decent transparency, they give direction even without exact number.

**Key missed context:**

> Q2 is the closest to a real dodge here but even that comes with some explanation, so tone feels more "genuinely too early" than "hiding something."
> Q1 and Q3 are both fairly open answers, so overall this feels a bit less evasive than a straight 6.
> This transcript feels similar in pattern to TCS Q3 2023, one soft dodge plus two honest answers.

**Verdict:** ⚠ Partially

---

## TCS Q1 2025 — Score: 6/10

### Supporting Quotes

**Q1:** *"Whatever delays that we had have been to a great extent factored into our Q1 numbers. Of course, there will be some small residual effect in Q2 as well. And if there are no further delays, Q2 should be at least better than Q1, but we need to wait and watch based on what happens in the market."*

**Q2:** *"Going forward, we should be able to further tighten our operating leverage."*

**Q3:** *"We are closely monitoring developments worldwide and remain committed to maintaining strong client relationships, positioning ourselves as a strategic partner."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 6 / 10

**Justification:**

> Q1 this is actually a detailed, honest answer, delays factored in, residual effect in Q2, wait and watch caveat, feels transparent.
> Q2 "we should be able to further tighten operating leverage" is vague, no numbers, no timeline, feels like a soft non-answer.
> Q3 "closely monitoring developments... strategic partner" this is pure corporate boilerplate, doesn't answer anything specific.

**Key missed context:**

> Q3 especially feels like filler language, this is the kind of generic statement companies use when they don't want to commit to anything real.
> Q1 pulls the score down (it's genuinely transparent) but Q2 and Q3 pull it back up, so net it balances out close to a 6.
> I think LLM caught the boilerplate tone correctly here even though Q1 shouldn't really count against them.

**Verdict:** ✓ Matches

---

## TCS Q4 2025 — Score: 4/10

### Supporting Quotes

**Q1:** *"I don't want to read too much into something change, okay? But what happened is we were able to close more deals compared to before."*

**Q2:** *"TCV is very difficult to predict because it changes based on even the customer delays a decision by a week or two, it can cross over a quarter."*

**Q3:** *"We are monitoring the global situation very closely. We continue to stay close to our clients and strive to be the partner of relevance at all times."*

### HUMAN REVIEW

**Your evasiveness score (1-10):** 4 / 10

**Justification:**

> Q1 they give an actual, honest answer (closed more deals than before), even with a hedge at the start.
> Q2 they explain clearly why TCV is hard to predict (customer delays shifting quarters), this is a real explanation not a dodge.
> Q3 "monitoring global situation... partner of relevance" is generic boilerplate, doesn't say anything concrete.

**Key missed context:**

> Same pattern as TCS Q1 2025, one boilerplate line (Q3) dragging down an otherwise pretty transparent set of answers.
> Q1 and Q2 are both genuinely informative, so overall evasiveness here is low.
> I think LLM is right to score this low, the boilerplate alone isn't enough to push it higher.

**Verdict:** ✓ Matches