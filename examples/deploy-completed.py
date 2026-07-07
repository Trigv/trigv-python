"""Notify the deploys channel when a production deploy completes."""

from trigv import Trigv

trigv = Trigv()

result = trigv.send_event(
    {
        "channel": "deploys",
        "title": "Production deploy complete",
        "description": "Build #42 succeeded in 38s (commit abc1234)",
        "level": "success",
        "delivery_urgency": "standard",
        "event_type": "deploy.completed",
        "idempotency_key": "deploy-prod-42",
    }
)

label = "duplicate" if result.duplicate else "new"
print(result.event.public_id, f"({label})")
