
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from search_api.cricket_queries import (
    get_events_by_match,
    get_events_by_team,
    get_events_by_player,
    get_events_by_status,
    get_events_by_type,
)

print("MATCH001:", len(get_events_by_match("MATCH001")))
print("Team A:", len(get_events_by_team("Team A")))
print("Player 11:", len(get_events_by_player("Player 11")))
print("Verified:", len(get_events_by_status("verified")))
print("LBW given:", len(get_events_by_type("LBW given")))
