"""Use idempotency keys to safely retry event delivery."""

from trigv import Trigv

trigv = Trigv()

idempotency_key = "deploy-prod-42"

result = trigv.send_event(
    {
        "channel": "deploys",
        "title": "Production deploy complete",
        "description": "Build #42 succeeded in 38s (commit abc1234)",
        "level": "success",
        "event_type": "deploy.completed",
        "idempotency_key": idempotency_key,
    }
)

if result.duplicate:
    print("Event already accepted:", result.event.public_id)
else:
    print("New event queued:", result.event.public_id)
