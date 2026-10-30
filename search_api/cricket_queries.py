

import os

from django.conf import settings
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv(settings.BASE_DIR / ".env")

username = os.getenv("MONGO_ROOT_USERNAME")
password = os.getenv("MONGO_ROOT_PASSWORD")
host = os.getenv("MONGO_HOST", "localhost")
port = os.getenv("MONGO_PORT", "27018")
database_name = os.getenv("MONGO_DATABASE", "cricket_db")

mongo_uri = (
    f"mongodb://{username}:{password}@{host}:{port}/"
    "?authSource=admin"
)

mongo_client = MongoClient(
    mongo_uri,
    serverSelectionTimeoutMS=3000
)

db = mongo_client[database_name]
events_collection = db["cricket_events"]



def serialize_event(event):
    """Convert a MongoDB document to a JSON-friendly dictionary."""

    return {
        "match_id": event.get("match_id"),
        "team": event.get("team"),
        "player": event.get("player"),
        "role": event.get("role"),
        "event": event.get("event"),
        "runs": event.get("runs"),
        "over": event.get("over"),
        "status": event.get("status"),
        "timestamp": event.get("timestamp"),
        "commentary": event.get("commentary"),
    }



def get_highest_runs_event():
    """Find one event with the highest numeric runs value."""

    event = events_collection.find_one(
        {"runs": {"$type": "number"}},
        sort=[("runs", DESCENDING)]
    )

    return serialize_event(event) if event else None


def get_events_by_match(match_id, limit=20):
    """Find events belonging to an exact match ID."""

    cursor = events_collection.find(
        {"match_id": match_id}
    ).sort("timestamp", 1).limit(limit)

    return [serialize_event(event) for event in cursor]


def get_events_by_team(team, limit=20):
    """Find events belonging to a team."""

    cursor = events_collection.find(
        {"team": {"$regex": f"^{team}$", "$options": "i"}}
    ).sort("timestamp", 1).limit(limit)

    return [serialize_event(event) for event in cursor]


def get_events_by_player(player, limit=20):
    """Find events involving a player."""

    cursor = events_collection.find(
        {"player": {"$regex": f"^{player}$", "$options": "i"}}
    ).sort("timestamp", 1).limit(limit)

    return [serialize_event(event) for event in cursor]


def get_events_by_status(event_status, limit=20):
    """Find events with a particular status."""

    cursor = events_collection.find(
        {"status": {"$regex": f"^{event_status}$", "$options": "i"}}
    ).sort("timestamp", 1).limit(limit)

    return [serialize_event(event) for event in cursor]


def get_events_by_type(event_type, limit=20):
    """Find events by exact event type, case-insensitively."""

    cursor = events_collection.find(
        {"event": {"$regex": f"^{event_type}$", "$options": "i"}}
    ).sort("timestamp", 1).limit(limit)

    return [serialize_event(event) for event in cursor]

