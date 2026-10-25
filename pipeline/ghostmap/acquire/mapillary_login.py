#!/usr/bin/env python3
"""One-time Mapillary login: exchange an authorization code for a user access token.

Run it yourself in a terminal (it is interactive):

    PYTHONPATH=pipeline .venv/bin/python -m ghostmap.acquire.mapillary_login

It reads the app's client token from .secrets/mapillary.env, asks for the
client secret (hidden input), prints the authorization link, waits for the
address the browser is redirected to after you click Allow, and exchanges the
code at once (codes expire within minutes). The resulting user token is saved
to .secrets/mapillary-user.json (owner-only permissions; ignored by git).
"""
from __future__ import annotations

import getpass
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from ghostmap.paths import ROOT

SECRETS = ROOT / '.secrets'


def main():
    from ghostmap.acquire.mapillary_probe import token
    client_token = token()
    app_id = client_token.split('|')[1]
    secret = getpass.getpass('Mapillary client secret (from the "Client secret" View link; input is hidden): ').strip()
    print('\n1. Open this link in your browser and click Allow:\n')
    print(f'   https://www.mapillary.com/connect?client_id={app_id}\n')
    redirected = input('2. Paste the full address the browser lands on (it contains "code="): ').strip()
    match = re.search(r'code=([^&\s]+)', redirected)
    if not match: raise SystemExit('No "code=" found in that address.')
    body = urllib.parse.urlencode({'grant_type': 'authorization_code', 'code': urllib.parse.unquote(match.group(1)),
                                   'client_id': app_id}).encode()
    request = urllib.request.Request('https://graph.mapillary.com/token', data=body,
                                     headers={'Authorization': 'OAuth ' + secret, 'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response: payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f'Exchange failed ({error.code}): {error.read().decode()[:300]}')
    if 'access_token' not in payload: raise SystemExit('Unexpected reply: ' + json.dumps(payload)[:300])
    SECRETS.mkdir(mode=0o700, exist_ok=True)
    path = SECRETS / 'mapillary-user.json'
    path.write_text(json.dumps({**payload, 'obtained_utc': datetime.now(timezone.utc).isoformat()}) + '\n')
    os.chmod(path, 0o600)
    stale = SECRETS / 'mapillary-code.txt'
    if stale.exists(): stale.unlink()
    print('\nSaved a user access token to', path, '(expires in', payload.get('expires_in', '?'), 'seconds). Done.')


if __name__ == '__main__': main()
