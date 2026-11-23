"""A2A registry client: register an agent and keep sending heartbeats."""

import logging
import threading
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class RegistryReporter(threading.Thread):
    """Background thread that registers an agent and refreshes its heartbeat."""

    def __init__(
        self,
        registry_url: str,
        name: str,
        url: str,
        description: str,
        skills: List[Dict[str, Any]],
        interval: int = 30,
    ) -> None:
        super().__init__(daemon=True, name=f"registry-{name}")
        self.registry_url = registry_url.rstrip("/")
        self.name = name
        self.url = url
        self.description = description
        self.skills = skills
        self.interval = max(5, int(interval))
        self._stop_event = threading.Event()

    def _payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "skills": self.skills,
            "interval": self.interval,
        }

    def run(self) -> None:
        endpoint = f"{self.registry_url}/register"
        while not self._stop_event.is_set():
            try:
                response = requests.post(
                    endpoint, json=self._payload(), timeout=3
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Registry register failed: HTTP %s %s",
                        response.status_code,
                        response.text[:200],
                    )
            except requests.RequestException as exc:
                logger.debug("Registry unavailable (%s): %s", endpoint, exc)
            self._stop_event.wait(self.interval)

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._stop_event.set()


def start_registration(
    registry_url: str,
    name: str,
    url: str,
    description: str,
    skills: List[Dict[str, Any]],
    interval: int = 30,
) -> Optional[RegistryReporter]:
    """Start a daemon heartbeat thread; returns ``None`` if disabled."""
    if not registry_url:
        return None
    reporter = RegistryReporter(
        registry_url, name, url, description, skills, interval
    )
    reporter.start()
    return reporter
