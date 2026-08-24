"""vm106 hosting entrypoint for svarkor-ai/cad (MC#2317).

The vm106 renderer runs `python serve.py` with NO PORT env; nginx proxies
sibbamala.com/cad/ -> 127.0.0.1:8125. server/api.py only DEFINES the ASGI `app`;
this shim binds the manifest PORT (default 8125) on 0.0.0.0. Named serve.py (not
server.py) to avoid clashing with the repo's server/ package on `import server.api`.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8125"))
    uvicorn.run("server.api:app", host="0.0.0.0", port=port)
