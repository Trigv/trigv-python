"""Alert the ops channel when a scheduled job fails."""

from trigv import Trigv

trigv = Trigv()

trigv.send_event(
    {
        "channel": "ops",
        "title": "Nightly backup failed",
        "description": "pg_dump exited with code 1 on db-primary",
        "level": "error",
        "event_type": "cron.failed",
    }
)
