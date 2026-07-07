"""Send a basic event to the general channel."""

from trigv import Trigv

trigv = Trigv()

result = trigv.send_event(
    {
        "channel": "general",
        "title": "Hello from Python",
    }
)

print(result.event.public_id)
