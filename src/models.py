"""Data models for the Industrial Equipment Event Log Analysis system.

Groups related values into dataclasses so processing state, parsed
records, and structured results are passed between modules as single
objects rather than loose variables.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict

PERMITTED_STATUSES = ("RUNNING", "IDLE", "MAINTENANCE", "STOPPED")


# ---------------------------------------------------------------------------
# Raw (post-split, partially-typed) records produced by the parsing stage.
# Numeric fields are Optional: None means the source text could not be
# converted to the expected type. Validation decides what that means.
# ---------------------------------------------------------------------------

@dataclass
class RawMachineRecord:
    machine_id: Optional[int]
    machine_type: str
    minimum_temperature: Optional[float]
    maximum_temperature: Optional[float]
    maximum_vibration: Optional[float]
    location: str


@dataclass
class RawEventRecord:
    event_id: Optional[int]
    machine_id: Optional[int]
    timestamp: Optional[int]
    status: str
    temperature: Optional[float]
    vibration: Optional[float]
    units_produced: Optional[int]
    defect_count: Optional[int]


# ---------------------------------------------------------------------------
# Fully validated / accepted records.
# ---------------------------------------------------------------------------

@dataclass
class MachineRecord:
    machine_id: int
    machine_type: str
    minimum_temperature: float
    maximum_temperature: float
    maximum_vibration: float
    location: str


@dataclass
class EventRecord:
    event_id: int
    machine_id: int
    timestamp: int
    status: str
    temperature: float
    vibration: float
    units_produced: int
    defect_count: int


# ---------------------------------------------------------------------------
# Structured results returned by the mandatory logical interfaces.
# ---------------------------------------------------------------------------

@dataclass
class MachineParseResult:
    success: bool
    machine: Optional[RawMachineRecord]
    machine_id: Optional[int]
    line_number: int
    reason_code: Optional[str] = None


@dataclass
class EventParseResult:
    success: bool
    event: Optional[RawEventRecord]
    event_id: Optional[int]
    line_number: int
    reason_code: Optional[str] = None


@dataclass
class ValidationResult:
    valid: bool
    reason_code: Optional[str] = None


@dataclass
class AnomalyRecord:
    event_id: int
    machine_id: int
    timestamp: int
    anomaly_code: str
    observed_value: float
    reference_value: float


@dataclass
class AnomalyResult:
    anomalies: List[AnomalyRecord] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.anomalies)

    @property
    def has_temperature_anomaly(self) -> bool:
        return any(a.anomaly_code in ("LOW_TEMPERATURE", "HIGH_TEMPERATURE") for a in self.anomalies)

    @property
    def has_vibration_anomaly(self) -> bool:
        return any(a.anomaly_code == "HIGH_VIBRATION" for a in self.anomalies)


@dataclass
class RejectedRecord:
    source_file: str
    line_number: int
    record_id: str
    reason_code: str


# ---------------------------------------------------------------------------
# Per-machine running processing state / statistics accumulator.
# ---------------------------------------------------------------------------

@dataclass
class MachineStats:
    machine: MachineRecord
    accepted_event_count: int = 0
    running_event_count: int = 0
    idle_event_count: int = 0
    maintenance_event_count: int = 0
    stopped_event_count: int = 0
    temperature_sum: float = 0.0
    maximum_vibration: float = 0.0
    latest_units_produced: int = 0
    latest_defect_count: int = 0
    temperature_anomaly_count: int = 0
    vibration_anomaly_count: int = 0
    last_accepted_timestamp: Optional[int] = None

    @property
    def average_temperature(self) -> float:
        if self.accepted_event_count == 0:
            return 0.0
        return self.temperature_sum / self.accepted_event_count

    def record_accepted_event(self, event: EventRecord) -> None:
        self.accepted_event_count += 1
        if event.status == "RUNNING":
            self.running_event_count += 1
        elif event.status == "IDLE":
            self.idle_event_count += 1
        elif event.status == "MAINTENANCE":
            self.maintenance_event_count += 1
        elif event.status == "STOPPED":
            self.stopped_event_count += 1

        self.temperature_sum += event.temperature
        if event.vibration > self.maximum_vibration:
            self.maximum_vibration = event.vibration

        self.latest_units_produced = event.units_produced
        self.latest_defect_count = event.defect_count
        self.last_accepted_timestamp = event.timestamp

    def record_anomalies(self, anomaly_result: AnomalyResult) -> None:
        if anomaly_result.has_temperature_anomaly:
            self.temperature_anomaly_count += 1
        if anomaly_result.has_vibration_anomaly:
            self.vibration_anomaly_count += 1


@dataclass
class ProcessingSummary:
    total_machine_records: int = 0
    valid_unique_machines: int = 0
    rejected_machine_records: int = 0
    total_event_records: int = 0
    accepted_event_records: int = 0
    rejected_event_records: int = 0
    temperature_anomaly_events: int = 0
    vibration_anomaly_events: int = 0
    total_anomaly_records: int = 0
