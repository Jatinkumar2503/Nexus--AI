from typing import Dict, Any, List

# Indian Railways Premium Service Types:
# - Vande Bharat (Super-Fast, stops only at major hubs: MUM, TNA, SUR, VAD, ADI, SAB)
# - Tejas Express (Semi-Fast, stops at MUM, TNA, VAP, SUR, VAD, ANA, ADI, SAB)
# - Indian Rail Local (Local, stops at every station)

VANDE_BHARAT_STOPS = ["MUM", "TNA", "SUR", "VAD", "ADI", "SAB"]
TEJAS_STOPS = ["MUM", "TNA", "VAP", "SUR", "VAD", "ANA", "ADI", "SAB"]
LOCAL_STOPS = ["MUM", "TNA", "VIR", "BOI", "VAP", "BIL", "SUR", "BHA", "VAD", "ANA", "ADI", "SAB"]

# Initial mock train schedule definitions (Indian Train Numbers/Names)
MOCK_SCHEDULES: List[Dict[str, Any]] = [
    # Outbound Trains (Mumbai -> Sabarmati)
    {
        "train_id": "VB-20901",
        "service_type": "Vande Bharat",
        "stops": VANDE_BHARAT_STOPS,
        "direction": "outbound",
        "departure_time_mins": 0,
        "passenger_count": 940
    },
    {
        "train_id": "TJ-12009",
        "service_type": "Tejas Express",
        "stops": TEJAS_STOPS,
        "direction": "outbound",
        "departure_time_mins": 10,
        "passenger_count": 680
    },
    {
        "train_id": "LC-901",
        "service_type": "Local",
        "stops": LOCAL_STOPS,
        "direction": "outbound",
        "departure_time_mins": 15,
        "passenger_count": 1150
    },
    {
        "train_id": "VB-20903",
        "service_type": "Vande Bharat",
        "stops": VANDE_BHARAT_STOPS,
        "direction": "outbound",
        "departure_time_mins": 30,
        "passenger_count": 980
    },
    # Inbound Trains (Sabarmati -> Mumbai)
    {
        "train_id": "VB-20902",
        "service_type": "Vande Bharat",
        "stops": list(reversed(VANDE_BHARAT_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 5,
        "passenger_count": 920
    },
    {
        "train_id": "TJ-12010",
        "service_type": "Tejas Express",
        "stops": list(reversed(TEJAS_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 12,
        "passenger_count": 650
    },
    {
        "train_id": "LC-902",
        "service_type": "Local",
        "stops": list(reversed(LOCAL_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 20,
        "passenger_count": 1080
    },
    {
        "train_id": "VB-20904",
        "service_type": "Vande Bharat",
        "stops": list(reversed(VANDE_BHARAT_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 35,
        "passenger_count": 960
    }
]

def get_train_schedule(train_id: str) -> Dict[str, Any]:
    """Retrieve schedule metadata for a specific train."""
    for schedule in MOCK_SCHEDULES:
        if schedule["train_id"] == train_id:
            return schedule
    raise ValueError(f"Train {train_id} not found in schedule database.")
