# Industrial Equipment Event Log Analysis and Reporting System

A modular Python 3 implementation of Question 4 (Industrial Equipment
Event Log Analysis and Reporting System).

## Running it

```
python src/main.py <machine_master.csv> <machine_events.csv> <output_dir>
```

All three arguments are optional. Defaults: `machine_master.csv` and
`machine_events.csv` in the current directory, output written to `.`.
Example, using the bundled sample data (section 24 of the spec):

```
python src/main.py sample_data/machine_master.csv sample_data/machine_events.csv output
```

This writes `machine_summary.csv`, `anomalies.csv` and
`rejected_records.csv` into `output/` and prints the console summary.
If an input file cannot be opened, the program prints an error to
stderr and exits with status 1 without processing anything.

## Layout

```
src/
  models.py       data classes: raw/validated records, structured results, per-machine stats
  parsing.py      parseMachineRecord / parseEventRecord (structural CSV parsing)
  validation.py   validateMachine / validateEvent + duplicate-id frequency counting
  anomaly.py      detectAnomalies
  processing.py   file reading, orchestration, sequential event processing
  reporting.py    CSV writers + console summary formatting
  main.py         CLI entry point, file-open error handling
tests/
  test_pipeline.py   50 pytest cases: every reason code, priority-order edge cases,
                      anomaly boundaries, far-apart duplicate detection
  conftest.py         puts src/ on the path for the test run
scripts/
  check_consistency.py   verifies the section-30 cross-file consistency rules against a run's output
sample_data/      the worked example from section 24/25, plus the section-25 expected outputs
testcases/        the 9 supplied test-case folders, plus testcases/custom_edge_cases (see below)
testrun_output/   generated output + captured console text for every test case
output/           generated output for sample_data (the worked example)
dashboard.html    a standalone, presentation-only results dashboard (see below) -- not part
                   of the graded pipeline; the system itself has no GUI, per section 4's scope
```

## Automated tests

```
python -m pytest tests/ -v
```

50 unit tests in `tests/test_pipeline.py`, calling `parseMachineRecord`,
`parseEventRecord`, `validateMachine`, `validateEvent`, `detectAnomalies`
and `build_duplicate_id_set` directly (no file I/O). They cover:

* every one of the 19 reason codes in sections 17.1/17.2, individually
* the full priority order in sections 18.1/18.2 -- e.g. a record that
  is both a duplicate *and* has an invalid status is asserted to come
  back `DUPLICATE_EVENT_ID`, not `INVALID_STATUS`, proving the chain is
  actually ordered and not just individually correct
* the `OUT_OF_ORDER_TIMESTAMP` check sitting at its required position
  between `INVALID_TIMESTAMP` and `INVALID_STATUS`
* every anomaly boundary in section 10.4 (temperature/vibration exactly
  at the limit is not an anomaly) and the multi-anomaly ordering rule
  in section 10.5
* duplicate IDs that are far apart in the input, confirming every
  occurrence is flagged, not just the second one

## Results dashboard

Live at **https://nikhilmamilla.github.io/Coding-Marathon/** (served from
`docs/index.html` via GitHub Pages; `docs/index.html` is a copy of
`dashboard.html` kept in sync with it).

`dashboard.html` is a separate, static visualization of one run's
output (the section-24 worked example): machine health cards, an
accepted-event timeline, a rejection-reason breakdown, and the
rejection log, in both a light and a dark theme. It is presentation
only -- every number on it is read from this program's own generated
`machine_summary.csv` / `anomalies.csv` / `rejected_records.csv`, not
hand-entered, and it does not replace or wrap the CLI pipeline in any
way. It exists because a results dashboard is a reasonable thing to
hand an evaluator alongside raw CSVs, not because the assignment asked
for one; section 4 explicitly excludes GUIs from the system's own
scope, so this file is kept outside `src/` and has no bearing on how
the pipeline itself is built, run, or graded.

## Data-modelling decisions (section 12)

* **Raw vs. validated records.** Parsing produces `RawMachineRecord` /
  `RawEventRecord`, whose numeric fields are `Optional` (`None` means
  "did not convert to the expected type"). Validation consumes these
  and only ever promotes a record to the strict `MachineRecord` /
  `EventRecord` (non-optional fields) once it has fully passed the
  rule chain. This keeps "the value couldn't be parsed" and "the value
  failed a business rule" as two distinct, always-reachable states,
  instead of collapsing missing/invalid fields to a sentinel like 0.
* **Per-machine processing state** (`MachineStats`) is the only state
  that must persist across the whole event file: running totals,
  status counts, the latest production/defect counts, and the
  anomaly counters. It is a dict keyed by `machine_id`, seeded with
  one entry per valid machine *before* event processing starts, so a
  machine with zero accepted events still appears in the summary.
* **Sequential out-of-order state** (`last_accepted_timestamp`, a
  plain `dict[machine_id, timestamp]`) is separate from `MachineStats`
  because it is purely transient processing context, not a reported
  statistic.
* **Duplicate detection** uses a `Counter` frequency map built in a
  single pass over the parsed rows (see below) -- not stored per
  record, since it is only needed once, up front.
* **Collections:** `dict` for O(1) machine lookup and stats
  accumulation; plain `list` for anomalies and rejected records,
  since both must preserve encounter order for their output files;
  `set`/`Counter` for duplicate-ID detection.

## Duplicate detection (section 16)

Both machine IDs and event IDs are duplicate-checked with the same
approach: after parsing every row in the file into memory, a
`Counter` is built over every **structurally parseable, positive
integer** ID (`build_duplicate_id_set` in `validation.py`). Any ID
with a frequency greater than 1 is added to a `set`. This is computed
**before** the main per-record validation pass, so by the time
`validateMachine` / `validateEvent` looks at a specific row, it
already knows -- via an `is_duplicate` flag -- whether that row's ID
occurs elsewhere in the file, no matter how far apart. This correctly
rejects *every* occurrence of a duplicated ID (verified against the
worked example, machine 104, and against testcase9's machine 9001,
which repeats 500 rows apart), not just the second-and-later ones.

The input file is still read from disk only once; the frequency count
and the validation pass both operate on the same in-memory list of
already-parsed rows, so this remains a single-I/O-pass design even
though duplicate detection is logically "a separate step".

## Mandatory logical interfaces (section 14)

`parseMachineRecord`, `parseEventRecord`, `validateMachine`,
`detectAnomalies` are implemented with the exact signatures given in
the spec. Two deliberate, documented extensions were made where the
spec itself says the extra information "may be handled separately":

* `validateMachine(machineRecord, is_duplicate=False)` -- the spec
  notes duplicate-machine detection needs cross-record information
  (section 14.3). Rather than splitting the priority chain across two
  functions and risking the checks running out of order, the
  precomputed duplicate flag is passed in as one extra argument, and
  `validateMachine` still applies the complete, correctly ordered
  priority chain (section 18.1) in one place.
* `validateEvent(eventRecord, validMachines, is_duplicate=False, previous_timestamp=None)` --
  same reasoning, extended to cover both duplicate-event detection and
  the out-of-order check (section 14.4 explicitly calls out both as
  separable). `previous_timestamp` is the timestamp of the last
  *accepted* event for that machine, owned by the sequential processor
  in `processing.py`. Passing it in lets `OUT_OF_ORDER_TIMESTAMP` sit
  at its required priority position 7 (between `INVALID_TIMESTAMP` at
  6 and `INVALID_STATUS` at 8) instead of being checked after the
  function returns, which would silently misorder it against status/
  temperature/vibration/production/defect checks.

All four functions are pure: they read their arguments and return a
structured result (`ValidationResult`, `AnomalyResult`, ...); none of
them mutate shared/global state. Global variables are not used to
pass results between modules anywhere in the codebase.

## Verification performed

0. **Unit tests.** `python -m pytest tests/ -v` -- 50 tests, all
   passing, covering every reason code, both validation priority
   chains in full order, every anomaly boundary, and far-apart
   duplicate detection. See "Automated tests" above.
1. **Worked example (sections 24/25).** `sample_data/` holds the
   spec's own sample input; `output/` is this program's output against
   it. All three output files match section 25's expected content
   exactly (verified with `diff --strip-trailing-cr`), and the console
   summary matches section 25.4 exactly.
2. **Supplied test cases.** All 9 folders from `testcase.zip`
   (referenced by the assignment) were run; see the analysis table
   below. `scripts/check_consistency.py` additionally re-derives every
   section-30 cross-file identity (valid+rejected == total, sum of
   `accepted_event_count` == accepted events, anomaly row count ==
   `Total anomaly records`, etc.) from each run's own output, and all
   9 runs pass every check -- i.e. every run is internally consistent
   with the written spec, independent of whether it matches the
   supplied expected console text.
3. **Custom edge cases** (`testcases/custom_edge_cases/`), written to
   exercise the reason codes none of the 9 supplied cases hit:
   `INCOMPLETE_MACHINE_RECORD`, `MISSING_MACHINE_TYPE`,
   `INVALID_VIBRATION_LIMIT`, `MISSING_LOCATION`,
   `INCOMPLETE_EVENT_RECORD`, `INVALID_MACHINE_ID` (event-side),
   `INVALID_TIMESTAMP`, `INVALID_TEMPERATURE`,
   `INVALID_PRODUCTION_COUNT`, a blank line in the middle of the file,
   and a valid machine with zero accepted events. All produced the
   expected reason code / output row. `INVALID_MACHINE_ID` for the
   machine file (zero, negative, non-numeric ID) was checked directly
   against `validateMachine`. Every one of the 19 reason codes in
   sections 17.1/17.2 was exercised and confirmed correct at least
   once across the supplied and custom cases.
4. **Performance.** testcase8 (200,000 event rows, 500 machines) runs
   in ~5.7s end to end off local disk (the ~10-16s figures seen when
   running directly against a OneDrive-synced path are sync/I-O
   overhead, not processing time). The design reads each input file
   from disk exactly once.

## Test-case analysis table (section 29)

9 test-case folders were supplied (not 6); the table below covers all
of them.

| Test Case | Conditions Identified | Initial Status | First Mismatch | Correction Made | Regression Tests Performed | Final Status |
|---|---|---|---|---|---|---|
| 1 | Exactly the spec's worked example (section 24): duplicate machine ID, inverted temperature limits, out-of-order timestamp, unknown machine, duplicate event ID (x2), invalid status, defect > units. | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 2 | Minimal clean-path case: one machine, three accepted events, boundary temperature/vibration values on the last event (no anomaly). | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 3 | Two machines; boundary min/max temperature and max vibration on several events; one genuine HIGH_TEMPERATURE and one genuine HIGH_VIBRATION anomaly, on different events. | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 4 | Out-of-order timestamp, unknown machine, invalid status (`ACTIVE`), negative vibration, one temperature and one vibration anomaly. | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 5 | Five machines, boundary values on multiple machines, one event with *both* a temperature and a vibration anomaly, a separate event with only a vibration anomaly, out-of-order timestamp, unknown machine. | Pass (self-consistent) | Supplied `expected_console_output.txt` reports `Vibration anomaly events: 1`, but also reports `Total anomaly records: 3` with `Temperature anomaly events: 1`. Since only two anomaly codes exist (temperature, vibration) and the program's own output is internally consistent (`1 + 2 = 3` matches the 3 rows actually written to `anomalies.csv`: event 50009's HIGH_TEMPERATURE + HIGH_VIBRATION, and event 50010's HIGH_VIBRATION), a vibration count of 1 cannot arithmetically produce 3 total rows together with a temperature count of 1. Traced to event `50010` (`505,3,RUNNING,15.0,2.0,5,1`): vibration `2.0 > maximum_vibration 1.0` for machine 505, a HIGH_VIBRATION anomaly by section 10.3's rule, no exception applies. | None -- the implementation's anomaly-detection logic was re-verified against sections 10.1-10.5 and matches the spec's own worked example (section 25.2) exactly; the fixture's console text appears to undercount vibration-anomaly events by one. | All 9 cases, plus `scripts/check_consistency.py` (all checks pass using the program's own output) | Pass (spec-verified); flagged fixture discrepancy |
| 6 | Eight machines; boundary values on several; one temperature and one vibration anomaly; invalid status, negative vibration cases across machines, unknown machine, out-of-order timestamp, and a duplicate event ID repeated far apart (`60016`, lines 17 and 20). | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 7 | Scale/performance case: 100 machines, 10,000 events, no rejections and no anomalies -- exercises the accepted-event and statistics path at volume with a fully clean dataset. | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 8 | Scale/performance case: 500 machines, 200,000 events, no rejections and no anomalies -- the "large event file" efficiency scenario (section 4). | Pass | Not Applicable | Not Applicable | All 9 cases | Pass |
| 9 | 502 machines / 200,010 events at scale, combined with a duplicate machine ID (`9001`) repeated 500 rows apart (lines 2 and 502), an invalid-temperature-limits machine, a duplicate event ID, an invalid event ID, and an incomplete event record, plus ~400 events referencing the duplicated machine. | Pass (self-consistent) | Supplied file expects `Valid unique machines: 500`, `Rejected machine records: 2`. The program produces 499 valid / 3 rejected, because machine `9001` occurs on both line 2 and line 502 and section 6 is explicit: *"Every record containing that Machine ID must be treated as a duplicate... None of those records may be used for event processing... Every duplicate record must be written to rejected_records.csv."* That requires **both** occurrences of `9001` to be rejected (2 rows) plus machine `9999` (`min 70.0 >= max 30.0`, `INVALID_TEMPERATURE_LIMITS`) = 3 rejected, 499 valid -- exactly what this program outputs, and exactly the pattern the spec's own worked example uses for machine 104. The ~400-event swing in accepted/rejected events and the anomaly counts all cascade from this: this program correctly rejects the ~400 events referencing the now-invalid machine 9001 as `UNKNOWN_MACHINE_ID`; the supplied expected text implies machine 9001 was kept valid using one of its two occurrences. Section 16 explicitly names that exact behaviour as non-compliant ("A solution that rejects only the second and later occurrence of a duplicated identifier does not satisfy the requirements"). | None -- the implementation matches section 6 and the section 25 worked example precisely; the fixture's console text appears to reflect the "reject only one occurrence" bug the spec warns against. | All 9 cases, plus `scripts/check_consistency.py` (all checks pass using the program's own output) | Pass (spec-verified); flagged fixture discrepancy |

For test cases 5 and 9, this program's output was not altered to force
a match with the supplied `expected_console_output.txt`, since doing so
would mean deliberately reintroducing behaviour sections 6/16 (testcase9)
or basic anomaly-detection arithmetic (testcase5) explicitly rule out.
Both discrepancies are reproducible via `scripts/check_consistency.py`
and the worked line-by-line trace above.

## Deliverables

* Source code: `src/`
* Generated `machine_summary.csv`, `anomalies.csv`, `rejected_records.csv`
  for the section-24 worked example: `output/`
* Generated outputs and captured console summaries for all 9 supplied
  test cases and the custom edge-case file: `testrun_output/`
* Console processing summary (worked example): printed by
  `python src/main.py sample_data/machine_master.csv sample_data/machine_events.csv output`,
  also captured at `testrun_output/testcase1/console_output.txt` (identical scenario)
* Test-case analysis table: above
* Automated test suite: `tests/test_pipeline.py` (50 cases, see "Automated tests")
* Results dashboard (not a graded component; see "Results dashboard"): `dashboard.html`
