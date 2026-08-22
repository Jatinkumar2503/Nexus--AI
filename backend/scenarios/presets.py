"""Curated, reusable disruption presets for demonstrations."""
PRESETS = {
    "signal_failure": {"edge_id": "SUR->BHA", "duration": 45, "severity": "HIGH", "description": "Track circuit signal failure"},
    "monsoon_washout": {"edge_id": "VAP->BIL", "duration": 120, "severity": "CRITICAL", "description": "Monsoon washout inspection block"},
    "substation_failure": {"edge_id": "MUM->TNA", "duration": 60, "severity": "HIGH", "description": "Traction substation failure"},
    "severe_weather": {"edge_id": "VAP->BIL", "duration": 90, "severity": "MEDIUM", "description": "Severe weather speed restriction and visibility check"},
    "maintenance_window": {"node_id": "VAD", "duration": 60, "severity": "MEDIUM", "description": "Planned maintenance window closes station approaches"},
    "rolling_stock_failure": {"node_id": "BHA", "duration": 75, "severity": "HIGH", "description": "Rolling-stock failure requires rescue and platform protection"},
    "network_partition": {"node_id": "TNA", "duration": 90, "severity": "CRITICAL", "description": "Control network partition isolates the junction"},
    "cascading_incident": {"edge_id": "SUR->BHA", "duration": 105, "severity": "CRITICAL", "description": "Signal and traction incident causes cascading corridor restrictions"},
}
