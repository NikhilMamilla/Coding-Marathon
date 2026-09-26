"""Operating anomaly detection for accepted events (section 10)."""

from models import EventRecord, MachineRecord, AnomalyRecord, AnomalyResult


def detectAnomalies(eventRecord: EventRecord, machineRecord: MachineRecord) -> AnomalyResult:
    """Detect temperature/vibration anomalies for one accepted event.

    Boundary values (temperature == limit, vibration == limit) are not
    anomalies. When both a temperature and a vibration anomaly are
    present, the temperature anomaly is returned first.
    """
    anomalies = []

    if eventRecord.temperature < machineRecord.minimum_temperature:
        anomalies.append(
            AnomalyRecord(
                event_id=eventRecord.event_id,
                machine_id=eventRecord.machine_id,
                timestamp=eventRecord.timestamp,
                anomaly_code="LOW_TEMPERATURE",
                observed_value=eventRecord.temperature,
                reference_value=machineRecord.minimum_temperature,
            )
        )
    elif eventRecord.temperature > machineRecord.maximum_temperature:
        anomalies.append(
            AnomalyRecord(
                event_id=eventRecord.event_id,
                machine_id=eventRecord.machine_id,
                timestamp=eventRecord.timestamp,
                anomaly_code="HIGH_TEMPERATURE",
                observed_value=eventRecord.temperature,
                reference_value=machineRecord.maximum_temperature,
            )
        )

    if eventRecord.vibration > machineRecord.maximum_vibration:
        anomalies.append(
            AnomalyRecord(
                event_id=eventRecord.event_id,
                machine_id=eventRecord.machine_id,
                timestamp=eventRecord.timestamp,
                anomaly_code="HIGH_VIBRATION",
                observed_value=eventRecord.vibration,
                reference_value=machineRecord.maximum_vibration,
            )
        )

    return AnomalyResult(anomalies=anomalies)
