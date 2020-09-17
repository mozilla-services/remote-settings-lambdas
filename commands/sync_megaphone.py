import asyncio
import json
import logging
import os
import random

import requests.auth
import websockets

from . import KintoClient


logger = logging.getLogger(__name__)


BROADCASTER_ID = "remote-settings"
CHANNEL_ID = "monitor_changes"


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __eq__(self, rhs):
        return self.token == rhs.token

    def __call__(self, r):
        r.headers["Authorization"] = "Bearer {}".format(self.token)
        return r


class Megaphone:
    def __init__(self, host, api_key, broadcaster_id):
        self.host = host.rstrip("/")
        self.auth = BearerAuth(api_key)
        self.broadcaster_id = broadcaster_id

    def send_version(self, version):
        rest_url = f"https://{self.host}/v1/broadcasts/{self.broadcaster_id}"
        resp = requests.put(rest_url, auth=self.auth, data=version)
        resp.raise_for_status()
        logger.info(
            "Sent version {} to megaphone. Response was {}".format(
                version, resp.status_code
            )
        )

    def get_version(self):
        ws_url = f"wss://{self.host}"

        async def _get_version():
            async with websockets.connect(ws_url) as websocket:
                logging.info(f"Send hello handshake to {ws_url}")
                data = {
                    "messageType": "hello",
                    "broadcasts": {self.broadcaster_id: "v0"},
                    "use_webpush": True,
                }
                await websocket.send(json.dumps(data))
                body = await websocket.recv()
                response = json.loads(body)

            etag = response["broadcasts"][self.broadcaster_id]
            return etag[1:-1]  # strip quotes.

        # async to sync
        return asyncio.run(_get_version())


def get_remotesettings_timestamp(uri):
    client = KintoClient(server_url=uri)
    random_cache_bust = random.randint(999999000000, 999999999999)
    entries = client.get_records(
        bucket="monitor", collection="changes", _expected=random_cache_bust
    )
    # Some collections are excluded (eg. preview)
    # https://github.com/mozilla-services/cloudops-deployment/blob/master/projects/kinto/puppet/modules/kinto/templates/kinto.ini.erb
    matched = [e for e in entries if "preview" not in e["bucket"]]
    return str(matched[0]["last_modified"])


def sync_megaphone(event, context):
    rs_server = event.get("server") or os.getenv("SERVER")
    rs_timestamp = get_remotesettings_timestamp(rs_server)

    megaphone_host = event.get("megaphone_host") or os.getenv("MEGAPHONE_HOST")
    megaphone_auth = event.get("megaphone_auth") or os.getenv("MEGAPHONE_AUTH")
    broadcaster_id = event.get("broadcaster_id") or os.getenv(
        "BROADCASTER_ID", BROADCASTER_ID
    )
    channel_id = event.get("channel_id") or os.getenv("CHANNEL_ID", CHANNEL_ID)
    broadcast_id = f"{broadcaster_id}/{channel_id}"

    megaphone_client = Megaphone(megaphone_host, megaphone_auth, broadcast_id)
    megaphone_timestamp = megaphone_client.get_version()
    logger.info(f"Remote Settings: {rs_timestamp}; Megaphone: {megaphone_timestamp}")

    if rs_timestamp == megaphone_timestamp:
        logger.info("Timestamps are in sync. Nothing to do.")
        return

    megaphone_client.send_version(rs_timestamp)
