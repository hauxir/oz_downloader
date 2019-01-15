import argparse
import datetime
import json
import os
import sys
from subprocess import Popen

import click
import requests

CLIENT_SECRET = "PHb7Aw7KZXGMYvgfEz"
CLIENT_ID = "ClubWebClient"
OZ_CORE_URL = "https://core.oz.com"
OZ_PLAYLIST_URL = "https://playlist.oz.com"
CHANNELS_URL = OZ_CORE_URL + "/users/me/channels"
CHANNEL_URL = OZ_CORE_URL + "/channels/%s/now?include=streamUrl,video,collection"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36"


@click.group()
def cli():
    pass


class OZ:
    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._renew_token()
        self._cookies = {}
        self._channels = {
            x["slug"]: x for x in json.loads(self._get2(CHANNELS_URL))["data"]
        }

    def _token_expired(self):
        return (
            not self._access_token
            or not self._token_expires
            or self._token_expires < datetime.datetime.now()
        )

    def _renew_token(self):
        request = requests.post(
            OZ_CORE_URL + "/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "password",
                "username": self._username,
                "password": self._password,
            },
            headers={"User-Agent": USER_AGENT},
        )
        now = datetime.datetime.now()
        response = request.json()
        try:
            self._access_token = response["access_token"]
            self._token_expires = now + datetime.timedelta(
                seconds=response["expires_in"] / 1000
            )
        except KeyError:
            raise Exception("Invalid login credentials!")

    def _get2(self, url):
        if not self._access_token or self._token_expired():
            self._renew_token()
        headers = {
            "Authorization": "Bearer " + self._access_token,
            "User-Agent": USER_AGENT,
        }
        request = requests.get(url, headers=headers)
        return request.content

    def _get_channel_json(self, name):
        c = self._channels[name]
        channel_url = CHANNEL_URL % c["id"]
        return json.loads(self._get2(channel_url))

    def _renew_cookie(self, channel, channel_json=None):
        if not channel_json:
            channel_json = self._get_channel_json(channel)
        streamUrl = channel_json["data"][0]["streamUrl"]
        cookie_name, cookie_token, cookie_url = (
            streamUrl.get("cookieName"),
            streamUrl.get("token"),
            streamUrl.get("cookieUrl"),
        )
        if cookie_name and cookie_token and cookie_url:
            cookie_response = requests.post(
                cookie_url,
                json=dict(name=str(cookie_name), value=str(cookie_token)),
                headers={"content-type": "application/json"},
            )
            self._cookies[channel] = dict(
                key=cookie_name, value=cookie_response.cookies.get(cookie_name)
            )

    def _get(self, url):
        if not self._access_token or self._token_expired():
            self._renew_token()
        headers = {
            "Authorization": "Bearer " + self._access_token,
            "User-Agent": USER_AGENT,
        }
        request = requests.get(url, headers=headers)
        return request

    def channels(self):
        return self._get("https://core.oz.com/channels?org=sjonvarp.365.is").json()[
            "data"
        ]

    def get_videos_collections(self, channel_id):
        return [
            d.get("collection") if d.get("collection") else d.get("video")
            for d in self._get(
                f"https://ddpk8as099jdd.cloudfront.net/v2/channels/{channel_id}/videos_collections"
            ).json()["data"]
        ]

    def get_parent_collection(self, channel_id, parent_id):
        return [
            d.get("collection") if d.get("collection") else d.get("video")
            for d in self._get(
                f"https://ddpk8as099jdd.cloudfront.net/v2/channels/{channel_id}/videos_collections?parentId={parent_id}"
            ).json()["data"]
        ]

    def get_collection(self, channel_id, collection_id):
        return [
            d.get("collection") if d.get("collection") else d.get("video")
            for d in self._get(
                f"https://core.oz.com/channels/{channel_id}/collections/{collection_id}"
            ).json()["data"]
        ]


def extract_streamUrl(streamUrl):
    streamData = oz._get(streamUrl).json()["data"]
    url = streamData["cdnUrl"]
    cookie = streamData["cookieName"]
    token = streamData["token"]
    # requests.post("https://playlist.oz.com/cookie", dict(name=cookie, value=token))
    return url, cookie, token


if __name__ == "__main__":
    oz = OZ(sys.argv[1], sys.argv[2])
    channels = oz.channels()
    click.echo("*************************")
    for i, channel in enumerate(channels):
        title = channel.get("name")
        click.echo(f"[{i}] {title}")
    channel_index = click.prompt("Choose", type=int)
    channel_id = channels[channel_index]["id"]
    slug = next(c["slug"] for c in oz.channels() if c["id"] == channel_id)
    collections = oz.get_videos_collections(channel_id)
    click.echo("*************************")
    for i, collection in enumerate(collections):
        title = collection.get("name") or collection.get("title")
        click.echo(f"[{i}] {title}")
    collection_index = click.prompt("Choose", type=int)
    collection_id = collections[collection_index]["id"]
    parent_collection = oz.get_parent_collection(channel_id, collection_id)
    click.echo("*************************")
    for i, collection in enumerate(parent_collection):
        title = collection.get("name") or collection.get("title")
        click.echo(f"[{i}] {title}")
    subcollection_index = click.prompt("Choose", type=int)
    subcollection = parent_collection[subcollection_index]
    name = subcollection.get("name") or subcollection.get("title")
    filename = name
    try:
        streamUrl = subcollection["_links"]["streamUrl"]
        url, cookie, token = extract_streamUrl(streamUrl)
        filename += f'_{subcollection["id"]}'
    except KeyError:
        parent_collection = oz.get_parent_collection(channel_id, subcollection["id"])
        click.echo("*************************")
        for i, collection in enumerate(parent_collection):
            title = collection.get("name") or collection.get("title")
            click.echo(f"[{i}] {title}")
        subcollection_index = click.prompt("Choose", type=int)
        subcollection = parent_collection[subcollection_index]
        name = subcollection.get("name") or subcollection.get("title")
        filename += f"_{name}"
        try:
            streamUrl = subcollection["_links"]["streamUrl"]
            url, cookie, token = extract_streamUrl(streamUrl)
            filename += f'_{subcollection["id"]}'
        except KeyError:
            parent_collection = oz.get_parent_collection(
                channel_id, subcollection["id"]
            )
            click.echo("*************************")
            for i, collection in enumerate(parent_collection):
                title = collection.get("name") or collection.get("title")
                click.echo(f"[{i}] {title}")
            subcollection_index = click.prompt("Choose", type=int)
            subcollection = parent_collection[subcollection_index]
            title = subcollection.get("name") or subcollection.get("title")
            filename += f"_{title}"
            streamUrl = subcollection["_links"]["streamUrl"]
            url, cookie, token = extract_streamUrl(streamUrl)
            filename += f'_{subcollection["id"]}'
    os.system(
        " ".join(
            [
                "streamlink",
                "--http-header",
                '"User-Agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36"',
                f"hls://{url}?ssl=true",
                "best",
                "-o",
                f'"{filename}.ts"',
                "--http-cookie",
                f'"{cookie}={token}; Domain=oz.com; Path=/"',
            ]
        )
    )
