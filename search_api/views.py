



import logging
import os
import re

import requests
from dotenv import load_dotenv
from django.conf import settings
from qdrant_client import QdrantClient
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from sentence_transformers import SentenceTransformer

from .serializers import CricketSearchSerializer
from .cricket_queries import (
    get_highest_runs_event,
    get_events_by_match,
    get_events_by_team,
    get_events_by_player,
    get_events_by_status,
    get_events_by_type,
)



# --------------------------------------------------
# 1. Configuration and logging
# --------------------------------------------------

logger = logging.getLogger(__name__)

load_dotenv(settings.BASE_DIR / ".env")

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "cricket_events",
)

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b",
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)


# --------------------------------------------------
# 2. Initialize search clients and embedding model
# --------------------------------------------------

try:
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info("Embedding model initialized successfully")

except Exception:
    logger.exception("Failed to initialize embedding model")
    raise


try:
    qdrant_client = QdrantClient(
        url=os.getenv(
            "QDRANT_URL",
            "http://localhost:6333",
        )
    )
    logger.info("Qdrant client initialized successfully")

except Exception:
    logger.exception("Failed to initialize Qdrant client")
    raise



def build_event_summary(events, description):
    """Summarize returned records using only fields in the data."""

    if not events:
        return f"No matching cricket events were found {description}."

    lines = [f"Found {len(events)} cricket events {description}:"]

    for event in events:
        parts = []

        if event.get("event"):
            parts.append(str(event["event"]))

        if event.get("player"):
            parts.append(f"Player: {event['player']}")

        if event.get("team"):
            parts.append(str(event["team"]))

        if event.get("over") is not None:
            parts.append(f"Over: {event['over']}")

        if event.get("runs") is not None:
            parts.append(f"Runs field: {event['runs']}")

        if event.get("status"):
            parts.append(f"Status: {event['status']}")

        if parts:
            lines.append("- " + " | ".join(parts))

    return "\n".join(lines)


# --------------------------------------------------
# 3. Exact-query routing
# --------------------------------------------------

def route_exact_query(query, limit):
    """Route recognized structured questions to MongoDB."""

    text = query.lower().strip()

    # Highest numeric runs value
    if any(phrase in text for phrase in [
        "highest runs",
        "most runs",
        "maximum runs",
        "max runs",
        "highest run value",
        "highest number of runs",
    ]):
        event = get_highest_runs_event()

        return {
            "type": "exact",
            "answer": (
                f"The maximum runs field value is {event['runs']}."
                if event else "No numeric runs values were found."
            ),
            "results": [event] if event else [],
        }

    # Match ID, e.g. MATCH001
    match = re.search(r"\bmatch\s*0*(\d+)\b", query, re.IGNORECASE)

    if match:
        match_id = f"MATCH{int(match.group(1)):03d}"
        events = get_events_by_match(match_id, limit=limit)

        return {
            "type": "exact",
            "answer": f"Found {len(events)} returned events for {match_id}.",
            "results": events,
        }

    # Team name, e.g. Team A
    team = re.search(r"\bteam\s+([A-D])\b", query, re.IGNORECASE)

    if team and any(word in text for word in [
        "event", "show", "find", "list", "records"
    ]):
        team_name = f"Team {team.group(1).upper()}"
        events = get_events_by_team(team_name, limit=limit)

        return {
            "type": "exact",
            "answer": f"Found {len(events)} returned events for {team_name}.",
            "results": events,
        }

    # Player name, e.g. Player 11
    player = re.search(r"\bplayer\s+(\d+)\b", query, re.IGNORECASE)

    if player and any(word in text for word in [
        "event", "show", "find", "list", "record"
    ]):
        player_name = f"Player {int(player.group(1))}"
        events = get_events_by_player(player_name, limit=limit)

        return {
            "type": "exact",
            "answer": f"Found {len(events)} returned events for {player_name}.",
            "results": events,
        }

    # Event status
    status_match = re.search(
        r"\b(confirmed|verified|pending review|disputed)\b",
        query,
        re.IGNORECASE,
    )

    if status_match and any(word in text for word in [
        "event", "show", "find", "list", "record"
    ]):
        event_status = status_match.group(1)
        events = get_events_by_status(event_status, limit=limit)

        return {
            "type": "exact",
            "answer": (
                f"Found {len(events)} returned events with status "
                f"'{event_status}'."
            ),
            "results": events,
        }

    # Exact event type
    event_types = [
        "LBW given",
        "six hit",
        "catch taken",
        "stumping",
        "run scored",
        "over completed",
        "wicket taken",
        "boundary hit",
    ]

    if any(word in text for word in ["event", "show", "find", "list"]):
        for event_type in event_types:
            if event_type.lower() in text:
                events = get_events_by_type(event_type, limit=limit)

                return {
                        "type": "exact",
                        "answer": build_event_summary(
                        events, f"for {match_id}"
                        ),
                        "results": events,
                        }

    # No recognized structured query
    return None


# --------------------------------------------------
# 4. Search API endpoint
# --------------------------------------------------

@api_view(["POST"])
def search_cricket(request):
    """Handle exact search, semantic retrieval and RAG generation."""

    logger.info("Cricket search request received")

    # Validate request data
    serializer = CricketSearchSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("Invalid cricket search request")

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    query = serializer.validated_data["query"]
    limit = serializer.validated_data["limit"]

    # --------------------------------------------------
    # 5. Try exact MongoDB search first
    # --------------------------------------------------

    try:
        exact_result = route_exact_query(query, limit=limit)

        if exact_result is not None:
            logger.info("Exact MongoDB search completed successfully")

            return Response({
                "query": query,
                "answer": exact_result["answer"],
                "count": len(exact_result["results"]),
                "results": exact_result["results"],
                "method": "mongodb_exact_query",
            })

    except Exception:
        logger.exception("Exact MongoDB search failed")

        return Response(
            {"error": "Exact search failed. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # --------------------------------------------------
    # 6. Generate embedding and retrieve from Qdrant
    # --------------------------------------------------

    try:
        logger.info("Starting semantic retrieval")

        query_vector = embedding_model.encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        points = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
        ).points

        events = []

        for point in points:
            payload = point.payload or {}

            events.append({
                "score": round(point.score, 4),
                "match_id": payload.get("match_id"),
                "team": payload.get("team"),
                "player": payload.get("player"),
                "event": payload.get("event"),
                "runs": payload.get("runs"),
                "over": payload.get("over"),
                "status": payload.get("status"),
                "timestamp": payload.get("timestamp"),
                "commentary": payload.get("commentary"),
            })

        logger.info(
            "Semantic retrieval completed; retrieved %d events",
            len(events),
        )

    except Exception:
        logger.exception("Semantic retrieval failed")

        return Response(
            {"error": "Semantic search is temporarily unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # No matching vector results
    if not events:
        logger.info("No relevant cricket events found")

        return Response({
            "query": query,
            "answer": "No relevant cricket events were found.",
            "count": 0,
            "results": [],
            "method": "qdrant_rag",
        })

    # --------------------------------------------------
    # 7. Build context for the local LLM
    # --------------------------------------------------

    context = "\n".join(
        f"Event {index}: {event}"
        for index, event in enumerate(events, start=1)
    )

    prompt = f"""
You are a careful cricket log assistant.

Answer using the retrieved records and accurate cricket knowledge.
Do not invent players, runs, or events.
The runs field is an event field, not necessarily a player's total score.
If evidence is insufficient, say so.
Keep the answer concise.

Retrieved records:
{context}

Question: {query}
"""

    # --------------------------------------------------
    # 8. Generate the answer using Ollama
    # --------------------------------------------------

    try:
        logger.info("Sending retrieved context to Ollama")

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 120,
                },
            },
            timeout=(5, 90),
        )

        response.raise_for_status()

        ollama_data = response.json()
        answer = ollama_data["message"]["content"]

        logger.info("Ollama answer generated successfully")

        return Response({
            "query": query,
            "answer": answer,
            "count": len(events),
            "results": events,
            "method": "qdrant_rag",
        })

    except requests.RequestException:
        logger.exception("Ollama request failed")

        return Response(
            {"error": "Ollama is unavailable. Check that it is running."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except (ValueError, KeyError, TypeError):
        logger.exception("Invalid response received from Ollama")

        return Response(
            {"error": "Could not process the AI response. Please try again."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    except Exception:
        logger.exception("Unexpected error during RAG generation")

        return Response(
            {"error": "Answer generation failed. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )



