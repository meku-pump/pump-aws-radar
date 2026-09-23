#!/usr/bin/env python3
"""
Push pump-aws-radar CSV output to Pump's self-serve onboarding endpoint.

This is the fork's only addition over upstream aws-radar. A Pump user mints a
short-lived upload token in the app; the customer pastes it into

    pump-aws-radar run --all-regions --tags --billing --upload-token <TOKEN>

and this module, after the inventory and billing CSVs are written, exchanges the
token for a presigned S3 PUT URL (one per file) and uploads each CSV directly to
Pump's bucket. The token carries no company id — the backend pins the company and
derives the S3 key server-side, so the token can only ever write its own upload's
prefix.

No AWS credentials of Pump's are involved on the client: the presigned URL already
carries everything the PUT needs. Only the two CSVs leave the customer's machine.
"""

import json
import urllib.error
import urllib.request

from pump_aws_radar import __version__

# A real User-Agent: Cloudflare in front of api.pump.co blocks the default
# urllib agent ("Python-urllib/..."), so the token exchange must identify itself.
_USER_AGENT = f"pump-aws-radar/{__version__}"

# The backend mounts its router under API_V1_STR (default "/api/v1"). The exchange
# route is service/api/endpoints/estimate_radar.py :: exchange_token_for_url.
_URLS_PATH = "/api/v1/estimate/radar/urls"

# Roles the backend recognizes, mapped to the local CSV each one carries.
_ROLES = ("inventory", "billing")

_HTTP_TIMEOUT_SECONDS = 60


class UploadError(RuntimeError):
    """Raised when the token exchange or the S3 PUT fails."""


def _exchange_token_for_url(api_base: str, token: str, role: str) -> str:
    """Exchange the upload token for a presigned PUT URL for *role*'s object."""
    url = api_base.rstrip("/") + _URLS_PATH
    body = json.dumps({"token": token, "role": role}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code == 401:
            raise UploadError(
                "Upload token was rejected (401). It may be wrong or expired — "
                "generate a fresh command in the Pump app."
            ) from e
        raise UploadError(f"Token exchange failed ({e.code}) for role '{role}': {detail}") from e
    except urllib.error.URLError as e:
        raise UploadError(f"Could not reach Pump at {url}: {e.reason}") from e

    upload_url = payload.get("upload_url")
    if not upload_url:
        raise UploadError(f"Exchange response for role '{role}' had no upload_url: {payload}")
    return upload_url


def _put_csv(upload_url: str, csv_path: str) -> None:
    """PUT the CSV at *csv_path* to the presigned *upload_url*.

    Content-Type must be text/csv: the presigned URL signs content-type, so a
    mismatched (or missing) type is rejected by S3 as a signature error.
    """
    with open(csv_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(
        upload_url,
        data=data,
        method="PUT",
        # User-Agent isn't required by S3, but keeping both requests identical avoids surprises.
        headers={"Content-Type": "text/csv", "User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
            if resp.status not in (200, 204):
                raise UploadError(f"S3 PUT of {csv_path} returned HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise UploadError(f"S3 PUT of {csv_path} failed ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise UploadError(f"S3 PUT of {csv_path} could not connect: {e.reason}") from e


def upload_csvs(api_base: str, token: str, files: dict[str, str]) -> None:
    """Upload each role's CSV to Pump.

    :param api_base: Pump API base, e.g. https://api.pump.co (no trailing /api).
    :param token:    the --upload-token minted in the Pump app.
    :param files:    {role: local_csv_path}; roles must be a subset of _ROLES.
    """
    unknown = set(files) - set(_ROLES)
    if unknown:
        raise UploadError(f"Unknown upload role(s): {sorted(unknown)}. Expected {list(_ROLES)}.")

    for role in _ROLES:
        csv_path = files.get(role)
        if not csv_path:
            continue
        print(f"  • {role}: requesting upload URL …")
        upload_url = _exchange_token_for_url(api_base, token, role)
        print(f"  • {role}: uploading {csv_path} …")
        _put_csv(upload_url, csv_path)
        print(f"  ✓ {role} uploaded")
