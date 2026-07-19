import json
import sqlite3

DB_PATH = "data/earningslens.db"
COMPANY = "TCS"


def _extract_evasiveness_score(raw_llm_response: str):
    """
    raw_llm_response is expected to be a JSON string containing:
      { "evasiveness_score": <number>, "supporting_quotes": [...] , ... }
    Returns (has_score: bool, score_or_none)
    """
    if not raw_llm_response:
        return (False, None)
    try:
        parsed = json.loads(raw_llm_response)
    except Exception:
        return (False, None)

    score = parsed.get("evasiveness_score", None)
    # treat int/float as set; everything else as null/missing
    has = isinstance(score, (int, float))
    return (has, score if has else None)


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scoring_runs'"
    )
    row = cur.fetchone()
    if not row:
        print("has_scoring_runs_table=False")
        conn.close()
        return

    print("has_scoring_runs_table=True")

    cur.execute("PRAGMA table_info(scoring_runs)")
    cols = cur.fetchall()
    col_names = [c[1] for c in cols]
    print("scoring_runs_columns=" + ", ".join(col_names))

    # Ensure transcripts table exists and has expected columns
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts'")
    if not cur.fetchone():
        print("has_transcripts_table=False")
        conn.close()
        return
    cur.execute("PRAGMA table_info(transcripts)")
    tcols = cur.fetchall()
    tcol_names = [c[1] for c in tcols]
    print("transcripts_columns=" + ", ".join(tcol_names))

    # Join scoring_runs -> transcripts to get quarter/year
    # Note: company may be stored in transcripts.company (case-sensitive).
    cur.execute(
        """
        SELECT t.company, t.year, t.quarter, r.raw_llm_response
        FROM scoring_runs r
        JOIN transcripts t ON t.id = r.transcript_id
        WHERE t.company = ?
        ORDER BY t.year, t.quarter
        """,
        (COMPANY,),
    )
    rows = cur.fetchall()

    # Print a checkpoint line per (year, quarter)
    # If multiple scoring_runs exist for a quarter, we summarize.
    by_yq = {}
    for company, year, quarter, raw in rows:
        has, score = _extract_evasiveness_score(raw)
        key = (year, quarter)
        by_yq.setdefault(key, {"has_score": False, "scores": []})
        by_yq[key]["has_score"] = by_yq[key]["has_score"] or has
        if has:
            by_yq[key]["scores"].append(score)

    keys_sorted = sorted(by_yq.keys())
    print("tcs_scoring_runs_join_rows_total=" + str(len(rows)))
    print("tcs_distinct_quarters_scored_total=" + str(len(keys_sorted)))

    for year, quarter in keys_sorted:
        info = by_yq[(year, quarter)]
        # if multiple scores exist, show count and the list
        score_list = info["scores"]
        if score_list:
            # keep output compact
            preview = score_list if len(score_list) <= 5 else score_list[:5] + ["..."]
            print(f"TCS {quarter} {year}: evasiveness_score=SET (n={len(score_list)} sample={preview})")
        else:
            print(f"TCS {quarter} {year}: evasiveness_score=NULL")


    conn.close()


if __name__ == "__main__":
    main()
