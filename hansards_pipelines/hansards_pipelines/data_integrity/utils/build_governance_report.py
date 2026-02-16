from datetime import datetime, timezone


def build_governance_report(summary: dict, matrix: dict) -> dict:

    rows = summary.get("rows", [])
    matrix_rows = matrix.get("rows", [])

    total_terms = len(rows)
    total_fail_terms = sum(1 for r in rows if r.get("status") == "FAIL")
    total_pass_terms = sum(1 for r in rows if r.get("status") == "PASS")

    total_mismatch_meetings = sum(
        1 for r in matrix_rows if r.get("status") == "MISMATCH"
    )

    overall_status = "FAIL" if total_fail_terms > 0 else "PASS"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "total_terms": total_terms,
        "total_fail_terms": total_fail_terms,
        "total_pass_terms": total_pass_terms,
        "total_mismatch_meetings": total_mismatch_meetings,
    }
