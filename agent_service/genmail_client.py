"""HTTP client wrapping the GenMail Flask API.

The agent service NEVER touches GenMail's SQLite directly — all reads go through
this client. That keeps the boundary clean: GenMail is the source of truth for
emails; we are the source of truth for derived insights.
"""

from __future__ import annotations

from typing import Any

import httpx

from config import settings

PM_EMAIL = "pm@acme.com"


class GenMailClient:
    """Thin async wrapper over the GenMail REST API.

    All methods return plain dicts/lists matching what the Flask routes return.
    Keeping the response shapes raw (no DTOs here) means the agent layer above
    decides what schema it cares about per feature.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = (base_url or settings.genmail_api_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- read endpoints -----------------------------------------------------

    async def ping(self) -> bool:
        # Reachability check must never propagate — caller decides what to do
        # with `false`. Catching broadly is correct here, narrowly elsewhere.
        try:
            r = await self._client.get("/ping")
            return r.status_code == 200
        except Exception:
            return False

    async def list_emails(
        self,
        *,
        thread_id: str | None = None,
        is_read: bool | None = None,
        sender: str | None = None,
        recipient: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if thread_id is not None:
            params["thread_id"] = thread_id
        if is_read is not None:
            params["is_read"] = "true" if is_read else "false"
        if sender is not None:
            params["sender"] = sender
        if recipient is not None:
            params["recipient"] = recipient
        r = await self._client.get("/emails", params=params)
        r.raise_for_status()
        return r.json()

    async def get_email(self, email_id: int) -> dict[str, Any]:
        r = await self._client.get(f"/emails/{email_id}")
        r.raise_for_status()
        return r.json()

    async def list_threads(self) -> list[dict[str, Any]]:
        r = await self._client.get("/threads")
        r.raise_for_status()
        return r.json()

    async def get_thread_emails(self, thread_id: str) -> list[dict[str, Any]]:
        """Fetch every email in a thread, ordered oldest→newest (the API
        returns newest-first, so we reverse). Conversation reasoning is much
        easier with chronological order."""
        emails = await self.list_emails(thread_id=thread_id)
        return list(reversed(emails))

    async def get_stats(self) -> dict[str, Any]:
        r = await self._client.get("/stats")
        r.raise_for_status()
        return r.json()

    # --- convenience helpers ------------------------------------------------

    async def get_unread(self) -> list[dict[str, Any]]:
        return await self.list_emails(is_read=False)

    async def get_sent(self) -> list[dict[str, Any]]:
        """Emails sent BY the user (pm@acme.com)."""
        return await self.list_emails(sender=PM_EMAIL)

    async def get_received(self) -> list[dict[str, Any]]:
        """Emails sent TO the user."""
        return await self.list_emails(recipient=PM_EMAIL)
