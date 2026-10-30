
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# MongoDB configuration
MONGO_USERNAME = os.getenv("MONGO_ROOT_USERNAME")
MONGO_PASSWORD = os.getenv("MONGO_ROOT_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27018"))
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "cricket_db")

# Qdrant configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "cricket_events"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 32


def event_to_text(event: dict) -> str:
    """Convert a cricket event into descriptive text for embedding."""
    return (
        f"Match: {event.get('match_id', '')}. "
        f"Team: {event.get('team', '')}. "
        f"Player: {event.get('player', '')}. "
        f"Event: {event.get('event', '')}. "
        f"Runs: {event.get('runs', '')}. "
        f"Over: {event.get('over', '')}. "
        f"Status: {event.get('status', '')}. "
        f"Commentary: {event.get('commentary', '')}"
    )


def main():
    if not MONGO_USERNAME or not MONGO_PASSWORD:
        raise ValueError("MongoDB credentials are missing from .env")

    mongo_uri = (
        f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}"
        f"@{MONGO_HOST}:{MONGO_PORT}/?authSource=admin"
    )

    print("Connecting to MongoDB...")
    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as mongo:
        mongo.admin.command("ping")
        collection = mongo[MONGO_DATABASE]["cricket_events"]
        events = list(collection.find({}, {"_id": 1, "timestamp": 1,
                                           "match_id": 1, "team": 1,
                                           "player": 1, "event": 1,
                                           "runs": 1, "over": 1,
                                           "status": 1, "commentary": 1}))

    if not events:
        raise RuntimeError("No cricket events found in MongoDB.")

    print(f"Loaded {len(events)} records from MongoDB.")
    print(f"Loading embedding model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)
    vector_size = model.get_sentence_embedding_dimension()

    print(f"Embedding dimension: {vector_size}")

    print("Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL, timeout=30)

    # Create the collection if it doesn't exist.
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"Created Qdrant collection: {COLLECTION_NAME}")
    else:
        info = qdrant.get_collection(COLLECTION_NAME)
        print(f"Using existing collection: {COLLECTION_NAME}")
        print(f"Existing vector count: {info.points_count}")

    # Stable point IDs allow repeatable upserts.
    total = len(events)

    for start in range(0, total, BATCH_SIZE):
        batch = events[start:start + BATCH_SIZE]
        texts = [event_to_text(event) for event in batch]

        vectors = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        points = []
        for event, vector in zip(batch, vectors):
            mongo_id = str(event["_id"])

            points.append(
                models.PointStruct(
                    id=mongo_id_to_point_id(mongo_id),
                    vector=vector.tolist(),
                    payload={
                        "mongo_id": mongo_id,
                        "timestamp": event.get("timestamp"),
                        "match_id": event.get("match_id"),
                        "team": event.get("team"),
                        "player": event.get("player"),
                        "event": event.get("event"),
                        "runs": event.get("runs"),
                        "over": event.get("over"),
                        "status": event.get("status"),
                        "commentary": event.get("commentary"),
                        "text": event_to_text(event),
                    },
                )
            )

        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )

        print(f"Indexed {min(start + len(batch), total)}/{total} records")

    print("\nEmbedding ingestion complete.")
    print("Qdrant collection:", COLLECTION_NAME)
    print("Points:", qdrant.count(COLLECTION_NAME, exact=True).count)


def mongo_id_to_point_id(mongo_id: str) -> str:
    """Convert MongoDB's ObjectId string into a stable UUID for Qdrant."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mongo-cricket-event:{mongo_id}"))


if __name__ == "__main__":
    main()
