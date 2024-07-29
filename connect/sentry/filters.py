from typing import Dict, List


def filter_events(event: Dict, hint: Dict, events_to_filter: List[str]) -> Dict | None:
    try:
        event_type: str | None = event.get("exception").get("values")[0].get("type")
        if event_type in events_to_filter:
            return None
        return event
    except IndexError:
        return event
