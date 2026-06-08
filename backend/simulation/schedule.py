from typing import Dict, Any, List

# Basic Shinkansen Service Types on Tokaido Shinkansen:
# - Nozomi (Express, stops only at major stations: TYO, SYO, NGO, KYT, OSA)
# - Hikari (Semi-Express, stops at TYO, SYO, ODW, SZO, HMM, NGO, MBR, KYT, OSA)
# - Kodama (Local, stops at every station)

NOZOMI_STOPS = ["TYO", "SYO", "NGO", "KYT", "OSA"]
HIKARI_STOPS = ["TYO", "SYO", "ODW", "SZO", "HMM", "NGO", "MBR", "KYT", "OSA"]
KODAMA_STOPS = ["TYO", "SYO", "ODW", "ATM", "MSM", "SFJ", "SZO", "KKG", "HMM", "TYH", "MKA", "NGO", "GFH", "MBR", "KYT", "OSA"]

# Initial mock train schedule definitions
MOCK_SCHEDULES: List[Dict[str, Any]] = [
    # Outbound Trains (Tokyo -> Shin-Osaka)
    {
        "train_id": "N101",
        "service_type": "Nozomi",
        "stops": NOZOMI_STOPS,
        "direction": "outbound",
        "departure_time_mins": 0,  # minutes from simulation start
        "passenger_count": 850
    },
    {
        "train_id": "H201",
        "service_type": "Hikari",
        "stops": HIKARI_STOPS,
        "direction": "outbound",
        "departure_time_mins": 10,
        "passenger_count": 620
    },
    {
        "train_id": "K301",
        "service_type": "Kodama",
        "stops": KODAMA_STOPS,
        "direction": "outbound",
        "departure_time_mins": 15,
        "passenger_count": 410
    },
    {
        "train_id": "N103",
        "service_type": "Nozomi",
        "stops": NOZOMI_STOPS,
        "direction": "outbound",
        "departure_time_mins": 30,
        "passenger_count": 910
    },
    # Inbound Trains (Shin-Osaka -> Tokyo)
    {
        "train_id": "N102",
        "service_type": "Nozomi",
        "stops": list(reversed(NOZOMI_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 5,
        "passenger_count": 820
    },
    {
        "train_id": "H202",
        "service_type": "Hikari",
        "stops": list(reversed(HIKARI_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 12,
        "passenger_count": 590
    },
    {
        "train_id": "K302",
        "service_type": "Kodama",
        "stops": list(reversed(KODAMA_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 20,
        "passenger_count": 380
    },
    {
        "train_id": "N104",
        "service_type": "Nozomi",
        "stops": list(reversed(NOZOMI_STOPS)),
        "direction": "inbound",
        "departure_time_mins": 35,
        "passenger_count": 890
    }
]

def get_train_schedule(train_id: str) -> Dict[str, Any]:
    """Retrieve schedule metadata for a specific train."""
    for schedule in MOCK_SCHEDULES:
        if schedule["train_id"] == train_id:
            return schedule
    raise ValueError(f"Train {train_id} not found in schedule database.")
