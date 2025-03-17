from typing import Dict, List, Optional


def filter_events(
    event: Dict, hint: Dict, events_to_filter: List[str]
) -> Optional[Dict]:
    try:
        event_type: str | None = event.get("exception").get("values")[0].get("type")
        if event_type in events_to_filter:
            return None
        return event
    except IndexError:
        return event
