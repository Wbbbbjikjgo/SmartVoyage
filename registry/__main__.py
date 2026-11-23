"""Run the A2A registry with ``python -m registry``."""

import uvicorn

from configs.settings import settings
from registry.server import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.registry_port)
