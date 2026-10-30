
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

JSON_FILE = PROJECT_ROOT / "data" / "processed" / "cricket_events.json"

USERNAME = os.getenv("MONGO_ROOT_USERNAME")
PASSWORD = os.getenv("MONGO_ROOT_PASSWORD")
HOST = os.getenv("MONGO_HOST", "localhost")
PORT = int(os.getenv("MONGO_PORT", "27018"))
DATABASE = os.getenv("MONGO_DATABASE", "cricket_db")

if not USERNAME or not PASSWORD:
    raise ValueError("Set MONGO_ROOT_USERNAME and MONGO_ROOT_PASSWORD in .env")

def main():
    if not JSON_FILE.exists():
        raise FileNotFoundError(f"JSON file not found: {JSON_FILE}")

    with JSON_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("Expected the JSON file to contain a list of records.")

    if not records:
        print("No records found. Nothing to import.")
        return

    # Use the normalized event fields to create a stable identifier.
    operations = []
    for record in records:
        required = [
            "timestamp", "match_id", "team", "player",
            "event", "runs", "over", "status", "commentary"
        ]
        missing = [field for field in required if field not in record]
        if missing:
            raise ValueError(f"Record is missing fields: {missing}")

        identity = {
            "timestamp": record["timestamp"],
            "match_id": record["match_id"],
            "team": record["team"],
            "player": record["player"],
            "event": record["event"],
            "over": record["over"],
            "commentary": record["commentary"],
        }

        operations.append(
            UpdateOne(
                identity,
                {"$setOnInsert": record},
                upsert=True,
            )
        )

    uri = (
        f"mongodb://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/"
        "?authSource=admin"
    )

    try:
        with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
            client.admin.command("ping")
            collection = client[DATABASE]["cricket_events"]

            result = collection.bulk_write(operations, ordered=False)

            print("MongoDB connection successful.")
            print(f"Input records: {len(records)}")
            print(f"New documents inserted: {result.upserted_count}")
            print(f"Existing documents matched: {result.matched_count}")
            print(f"Total documents now in collection: {collection.count_documents({})}")

    except PyMongoError as exc:
        print(f"MongoDB operation failed: {exc}")
        raise

if __name__ == "__main__":
    main()
