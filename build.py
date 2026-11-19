"""Build 24 dated snapshots from the released SQL, without future observations."""
import csv
import hashlib
import json
import math
import zipfile
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

ROOT = Path(__file__).resolve().parent
SCHEMAS = json.loads((ROOT / "schema.json").read_text())
TIMES = {
    "people.csv": "record_created_at", "transactions.csv": "occurred_at",
    "subscription_periods.csv": "renewal_due_at", "product_events.csv": "occurred_at",
    "feedback.csv": "submitted_at", "campaign_spend.csv": "spend_date",
    "acquisition_attribution.csv": "credited_at", "channel_holdouts.csv": "followup_end_at",
}


def rows(connection, sql):
    result = connection.execute(sql)
    names = [item[0] for item in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    return value


def snapshot(cutoff, data_dir):
    connection = duckdb.connect()
    connection.execute("SET threads=1; SET TimeZone='UTC'")
    connection.execute(f"CREATE VIEW lab_settings AS SELECT TIMESTAMP '{cutoff}' AS data_as_of")
    for filename, columns in SCHEMAS.items():
        path = str((data_dir / filename).resolve()).replace("'", "''")
        types = str(columns)
        field = TIMES[filename]
        comparator = "<=" if filename == "channel_holdouts.csv" else "<"
        extra = f" AND attributes_recorded_at < TIMESTAMP '{cutoff}'" if filename == "people.csv" else ""
        connection.execute(
            f"CREATE VIEW {Path(filename).stem} AS SELECT * FROM read_csv('{path}',"
            f" header=true, columns={types}, nullstr='', strict_mode=true)"
            f" WHERE {field} {comparator} TIMESTAMP '{cutoff}'{extra}"
        )
    connection.execute((ROOT / "01_views.sql").read_text())
    result = {
        "cutoff": cutoff,
        "cohorts": rows(connection, "SELECT * FROM cohort_cash_economics ORDER BY cohort_month,age_month"),
        "retention": rows(connection, "SELECT * FROM cohort_totals ORDER BY cohort_month,age_month"),
        "mix": rows(connection, "SELECT cohort_month,channel,primary_need,count(*) AS customers FROM acquired_customers GROUP BY ALL ORDER BY ALL"),
        "company": rows(connection, "SELECT * FROM company_totals ORDER BY calendar_month"),
        "tests": rows(connection, """SELECT * FROM channel_holdouts
            ORDER BY followup_end_at,channel,primary_need,arm"""),
        "observed_value": rows(connection, """SELECT cohort_month,
            sum(contribution/pow(1.01,age_month+1))/max(n_acquired) AS value,
            count(*) AS receipts FROM cohort_totals WHERE age_month<12 GROUP BY cohort_month ORDER BY cohort_month"""),
    }
    connection.close()
    return clean(result)


def verify_baseline():
    archive = ROOT / "baseline.zip"
    if archive.exists() and not (ROOT / "baseline/data").exists():
        lock = json.loads((ROOT / "baseline-lock.json").read_text())
        with zipfile.ZipFile(archive) as source:
            for filename in lock["files"]:
                if filename.startswith("baseline/"):
                    target = ROOT / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read(filename))
    lock = json.loads((ROOT / "baseline-lock.json").read_text())
    for filename, expected in lock["files"].items():
        actual = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Baseline changed: {filename}")
    return lock


def assert_reconciliation(latest):
    with (ROOT / "baseline/tables/cohort_totals.csv").open() as stream:
        expected = list(csv.DictReader(stream))
    assert len(expected) == len(latest["retention"])
    for actual, saved in zip(latest["retention"], expected):
        for key in ("n_acquired", "n_retained", "net_revenue", "contribution", "retained_share"):
            assert math.isclose(float(actual[key]), float(saved[key]), abs_tol=1e-7), (key, actual, saved)
    with (ROOT / "baseline/tables/cohort_cash_economics.csv").open() as stream:
        expected = list(csv.DictReader(stream))
    for actual, saved in zip(latest["cohorts"], expected):
        for key in ("cac", "balance_per_customer", "cumulative_contribution_per_customer"):
            assert math.isclose(float(actual[key]), float(saved[key]), abs_tol=1e-7)


def truncated_check(expected):
    """Independent source truncation must give identical June 2025 results."""
    cutoff = datetime.fromisoformat(expected["cutoff"])
    with TemporaryDirectory() as folder:
        destination = Path(folder)
        for filename in SCHEMAS:
            with (ROOT / "baseline/data" / filename).open() as stream:
                reader = csv.DictReader(stream)
                records = list(reader)
                fields = reader.fieldnames
            def available(record):
                instant = datetime.fromisoformat(record[TIMES[filename]])
                return instant <= cutoff if filename == "channel_holdouts.csv" else instant < cutoff
            with (destination / filename).open("w") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(record for record in records if available(record))
        assert snapshot(expected["cutoff"], destination) == expected


def main():
    lock = verify_baseline()
    snapshots = []
    for year in (2024, 2025):
        for month in range(1, 13):
            cutoff = date(year + month // 12, month % 12 + 1, 1).isoformat()
            snapshots.append(snapshot(cutoff, ROOT / "baseline/data"))
    assert_reconciliation(snapshots[-1])
    truncated_check(snapshots[17])
    with (ROOT / "baseline/tables/cohort_valuation.csv").open() as stream:
        forecasts = list(csv.DictReader(stream))
    with (ROOT / "baseline/tables/channel_value_decision.csv").open() as stream:
        decisions = list(csv.DictReader(stream))
    payload = {"snapshots": snapshots, "final_forecasts": forecasts, "final_decisions": decisions}
    template = (ROOT / "template.html").read_text()
    output = template.replace("__PAYLOAD__", json.dumps(payload, allow_nan=False).replace("</", "<\\/"))
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist/index.html").write_text(output)
    import shutil
    shutil.copyfile(ROOT / "baseline/report.pdf", ROOT / "dist/baseline-report.pdf")
    if (ROOT / "demo.mp4").exists():
        shutil.copyfile(ROOT / "demo.mp4", ROOT / "dist/demo.mp4")
    receipt = {"source_commit": lock["commit"], "months": 24, "latest_sql_reconciles": True,
               "june_2025_truncated_source_check": True, "baseline_report_sha256": lock["files"]["baseline/report.pdf"],
               "forecast_policy": "FAQ 4 fallback: original fit displayed only at December 2025; historical forecast unavailable.",
               "first_supported_recommendation": "December 2025, the first snapshot with an eligible forecast in this implementation. Earlier support is unknown."}
    (ROOT / "dist/verification.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
