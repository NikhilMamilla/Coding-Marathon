"""Verify the section-30 output consistency requirements against a
generated output directory."""
import csv
import sys


def load_summary_counts(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def main(outdir, console_text):
    lines = console_text.strip().splitlines()
    values = {}
    for line in lines:
        key, val = line.rsplit(":", 1)
        values[key.strip()] = int(val.strip())

    summary_rows = load_summary_counts(f"{outdir}/machine_summary.csv")
    with open(f"{outdir}/anomalies.csv", newline="") as f:
        anomaly_rows = list(csv.DictReader(f))
    with open(f"{outdir}/rejected_records.csv", newline="") as f:
        rejected_rows = list(csv.DictReader(f))

    checks = []
    checks.append(("valid+rejected machines == total",
                    values["Valid unique machines"] + values["Rejected machine records"] == values["Total machine records"]))
    checks.append(("accepted+rejected events == total",
                    values["Accepted event records"] + values["Rejected event records"] == values["Total event records"]))
    checks.append(("sum(accepted_event_count) == accepted events",
                    sum(int(r["accepted_event_count"]) for r in summary_rows) == values["Accepted event records"]))
    checks.append(("anomalies.csv rows == total anomaly records",
                    len(anomaly_rows) == values["Total anomaly records"]))
    checks.append(("rejected_records.csv rows == rejected machines + rejected events",
                    len(rejected_rows) == values["Rejected machine records"] + values["Rejected event records"]))
    checks.append(("machine_summary rows == valid unique machines",
                    len(summary_rows) == values["Valid unique machines"]))

    ok = True
    for name, passed in checks:
        status = "OK" if passed else "FAIL"
        if not passed:
            ok = False
        print(f"  [{status}] {name}")
    return ok


if __name__ == "__main__":
    outdir = sys.argv[1]
    console_path = sys.argv[2]
    with open(console_path) as f:
        console_text = f.read()
    ok = main(outdir, console_text)
    sys.exit(0 if ok else 1)
