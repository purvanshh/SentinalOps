import httpx

from core.config import get_settings


class SlackClient:
    def __init__(self, webhook_url: str | None = None) -> None:
        settings = get_settings()
        self.webhook_url = webhook_url or settings.slack_webhook_url

    async def send_message(self, text: str) -> None:
        if not self.webhook_url:
            return
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(self.webhook_url, json={"text": text})
