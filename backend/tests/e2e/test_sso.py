"""SSO login and SCIM provisioning through Polis, against an in-process fake Polis."""

import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import polis
from tests.e2e.helpers import auth_headers, login, register_tenant, unique_email
from tests.e2e.test_access_control import PASSWORD, create_user

pytestmark = pytest.mark.e2e

WEBHOOK_SECRET = "test-webhook-secret"


class FakePolis:
    def __init__(self):
        self.codes: dict[str, dict] = {}  # code -> profile
        self.tokens: dict[str, dict] = {}
        self.connections: list[dict] = []
        self.directories: list[dict] = []

    def issue_code(self, tenant_id: str, email: str, product: str = "doc-hub", first="Ada", last="Lovelace") -> str:
        code = uuid.uuid4().hex
        self.codes[code] = {
            "id": uuid.uuid4().hex,
            "email": email,
            "firstName": first,
            "lastName": last,
            "requested": {"tenant": tenant_id, "product": product},
        }
        return code

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/oauth/token":
            form = parse_qs(request.content.decode())
            if form.get("client_secret") != [settings.POLIS_CLIENT_SECRET_VERIFIER]:
                return httpx.Response(401, text="Invalid client_secret")
            profile = self.codes.pop(form["code"][0], None)
            if profile is None:
                return httpx.Response(401, text="Invalid code")
            token = uuid.uuid4().hex
            self.tokens[token] = profile
            return httpx.Response(200, json={"access_token": token, "token_type": "bearer"})
        if path == "/api/oauth/userinfo":
            token = request.headers["authorization"].split(" ", 1)[1]
            return httpx.Response(200, json=self.tokens[token])
        assert request.headers.get("authorization") == f"Api-Key {settings.POLIS_API_KEY}"
        if path == "/api/v1/sso":
            if request.method == "POST":
                self.connections.append(json.loads(request.content))
                return httpx.Response(200, json={"clientID": "x"})
            if request.method == "GET":
                return httpx.Response(200, json=self.connections)
            if request.method == "DELETE":
                self.connections.clear()
                return httpx.Response(204)
        if path == "/api/v1/dsync":
            if request.method == "POST":
                body = json.loads(request.content)
                directory = {**body, "id": "dir_1", "scim": {"endpoint": "https://polis/api/scim/v2.0/dir_1", "secret": "scim-token"}}
                self.directories.append(directory)
                return httpx.Response(201, json={"data": directory})
            return httpx.Response(200, json={"data": self.directories})
        return httpx.Response(404)


@pytest.fixture
def fake_polis(monkeypatch):
    fake = FakePolis()
    monkeypatch.setattr(settings, "POLIS_URL", "http://polis.test")
    monkeypatch.setattr(settings, "POLIS_PUBLIC_URL", "https://sso.example.com")
    monkeypatch.setattr(settings, "POLIS_API_KEY", "polis-admin-key")
    monkeypatch.setattr(settings, "POLIS_CLIENT_SECRET_VERIFIER", "verifier")
    monkeypatch.setattr(settings, "POLIS_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(
        polis,
        "_client",
        lambda: httpx.AsyncClient(base_url="http://polis.test", transport=httpx.MockTransport(fake.handler)),
    )
    return fake


def _fragment(location: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(location).fragment).items()}


async def _sso_tenant(client: AsyncClient, domain: str) -> dict:
    reg = await register_tenant(client, "SSO Co", unique_email("owner"), PASSWORD)
    r = await client.put("/sso/domains", headers=auth_headers(reg["access_token"]), json={"domains": [domain]})
    assert r.status_code == 200, r.text
    return reg


async def _sso_login(client: AsyncClient, fake: FakePolis, tenant_id: str, email: str, **profile):
    r = await client.get("/auth/sso/start", params={"email": email}, follow_redirects=False)
    assert r.status_code == 302, r.text
    authorize = urlparse(r.headers["location"])
    query = parse_qs(authorize.query)
    assert authorize.netloc == "sso.example.com" and query["tenant"] == [tenant_id]
    code = fake.issue_code(tenant_id, email, **profile)
    return await client.get(
        "/auth/sso/callback", params={"code": code, "state": query["state"][0]}, follow_redirects=False
    )


def _domain() -> str:
    return f"corp-{uuid.uuid4().hex[:8]}.example"


class TestSsoLogin:
    async def test_first_login_creates_member_and_issues_working_tokens(self, client: AsyncClient, fake_polis):
        domain = _domain()
        t = await _sso_tenant(client, domain)
        assert (await client.get("/auth/sso/discover", params={"email": f"x@{domain}"})).json() == {"sso": True}
        r = await _sso_login(client, fake_polis, t["tenant"]["id"], f"ada@{domain}")
        assert r.status_code == 302
        tokens = _fragment(r.headers["location"])
        assert "access_token" in tokens and "error" not in tokens
        me = await client.get("/documents", headers=auth_headers(tokens["access_token"]))
        assert me.status_code == 200

    async def test_state_cannot_be_replayed(self, client: AsyncClient, fake_polis):
        domain = _domain()
        t = await _sso_tenant(client, domain)
        r = await client.get("/auth/sso/start", params={"email": f"a@{domain}"}, follow_redirects=False)
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        for expected in (None, "sso_expired"):
            code = fake_polis.issue_code(t["tenant"]["id"], f"a@{domain}")
            r = await client.get("/auth/sso/callback", params={"code": code, "state": state}, follow_redirects=False)
            assert _fragment(r.headers["location"]).get("error") == expected

    async def test_profile_for_another_tenant_is_rejected(self, client: AsyncClient, fake_polis):
        domain = _domain()
        await _sso_tenant(client, domain)
        r = await client.get("/auth/sso/start", params={"email": f"a@{domain}"}, follow_redirects=False)
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        code = fake_polis.issue_code(str(uuid.uuid4()), f"a@{domain}")
        r = await client.get("/auth/sso/callback", params={"code": code, "state": state}, follow_redirects=False)
        assert _fragment(r.headers["location"]) == {"error": "sso_failed"}

    async def test_idp_asserting_unclaimed_domain_is_rejected(self, client: AsyncClient, fake_polis):
        domain = _domain()
        t = await _sso_tenant(client, domain)
        r = await client.get("/auth/sso/start", params={"email": f"a@{domain}"}, follow_redirects=False)
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        code = fake_polis.issue_code(t["tenant"]["id"], "ceo@victim.example")
        r = await client.get("/auth/sso/callback", params={"code": code, "state": state}, follow_redirects=False)
        assert "not linked" in _fragment(r.headers["location"])["error"]

    async def test_sso_cannot_take_over_an_account_in_another_workspace(self, client: AsyncClient, fake_polis):
        domain = _domain()
        victim_email = f"shared@{domain}"
        await register_tenant(client, "Victim Co", victim_email, PASSWORD)
        attacker = await register_tenant(client, "Attacker Co", unique_email("attacker"), PASSWORD)
        # The attacker cannot claim a domain someone else already claimed, but even an
        # unclaimed one must not hand them an existing account elsewhere.
        r = await client.put("/sso/domains", headers=auth_headers(attacker["access_token"]), json={"domains": [domain]})
        assert r.status_code == 200
        r = await _sso_login(client, fake_polis, attacker["tenant"]["id"], victim_email)
        assert "another workspace" in _fragment(r.headers["location"])["error"]


class TestSsoAdmin:
    async def test_public_and_already_claimed_domains_are_refused(self, client: AsyncClient, fake_polis):
        domain = _domain()
        await _sso_tenant(client, domain)
        other = await register_tenant(client, "Other", unique_email("o"), PASSWORD)
        h = auth_headers(other["access_token"])
        assert (await client.put("/sso/domains", headers=h, json={"domains": ["gmail.com"]})).status_code == 422
        assert (await client.put("/sso/domains", headers=h, json={"domains": [domain]})).status_code == 409

    async def test_enforced_sso_blocks_member_password_login_but_not_owner(self, client: AsyncClient, fake_polis):
        domain = _domain()
        owner_email = f"owner@{domain}"
        reg = await register_tenant(client, "Enforced Co", owner_email, PASSWORD)
        member_email = f"member@{domain}"
        create_user(reg["tenant"]["id"], member_email, "member")
        r = await client.put(
            "/sso/domains", headers=auth_headers(reg["access_token"]), json={"domains": [domain], "enforced": True}
        )
        assert r.json()["enforced"] is True
        r = await client.post("/auth/login", json={"email": member_email, "password": PASSWORD})
        assert r.status_code == 403
        assert (await login(client, owner_email, PASSWORD))["access_token"]

    async def test_connection_and_directory_setup(self, client: AsyncClient, fake_polis):
        reg = await _sso_tenant(client, _domain())
        h = auth_headers(reg["access_token"])
        r = await client.post("/sso/connection", headers=h, json={"metadata_url": "https://idp.example/metadata"})
        assert r.status_code == 200
        sent = fake_polis.connections[0]
        assert sent["tenant"] == reg["tenant"]["id"] and sent["metadataUrl"] == "https://idp.example/metadata"
        assert sent["redirectUrl"] == [polis.callback_url()]
        assert (await client.post("/sso/connection", headers=h, json={})).status_code == 422

        r = await client.post("/sso/directory", headers=h, json={"type": "okta-scim-v2"})
        assert r.json() == {"scim_endpoint": "https://polis/api/scim/v2.0/dir_1", "scim_token": "scim-token", "type": "okta-scim-v2"}
        assert fake_polis.directories[0]["webhook_secret"] == WEBHOOK_SECRET
        assert (await client.post("/sso/directory", headers=h, json={"type": "okta-scim-v2"})).status_code == 409

        config = (await client.get("/sso/config", headers=h)).json()
        assert config["connections"] == [{"name": "Company SSO", "type": "saml"}]
        assert config["directory"]["type"] == "okta-scim-v2"

    async def test_members_cannot_configure_sso(self, client: AsyncClient, fake_polis):
        reg = await _sso_tenant(client, _domain())
        email = unique_email("m")
        create_user(reg["tenant"]["id"], email, "member")
        h = auth_headers((await login(client, email, PASSWORD))["access_token"])
        assert (await client.put("/sso/domains", headers=h, json={"domains": ["x.example"]})).status_code == 403
        assert (await client.post("/sso/connection", headers=h, json={"metadata_url": "https://x"})).status_code == 403


def _signed(events, secret: str = WEBHOOK_SECRET, ts_ms: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(events).encode()
    ts = str(ts_ms if ts_ms is not None else int(time.time() * 1000))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Ory-Polis-Signature": f"t={ts},s={sig}", "Content-Type": "application/json"}


def _event(tenant_id: str, event: str, data: dict) -> dict:
    return {"directory_id": "dir_1", "event": event, "data": data, "tenant": tenant_id, "product": "doc-hub"}


class TestScim:
    async def test_unsigned_stale_or_forged_webhooks_are_rejected(self, client: AsyncClient, fake_polis):
        reg = await _sso_tenant(client, _domain())
        ev = _event(reg["tenant"]["id"], "user.created", {"email": "x@x.example", "active": True})
        body, headers = _signed(ev)
        assert (await client.post("/webhooks/polis/dsync", content=body)).status_code == 401
        _, stale = _signed(ev, ts_ms=int((time.time() - 3600) * 1000))
        assert (await client.post("/webhooks/polis/dsync", content=body, headers=stale)).status_code == 401
        _, forged = _signed(ev, secret="wrong")
        assert (await client.post("/webhooks/polis/dsync", content=body, headers=forged)).status_code == 401
        assert (await client.post("/webhooks/polis/dsync", content=body, headers=headers)).status_code == 200

    async def test_scim_provisions_users_groups_and_access(self, client: AsyncClient, fake_polis):
        domain = _domain()
        reg = await _sso_tenant(client, domain)
        tid, owner = reg["tenant"]["id"], auth_headers(reg["access_token"])
        email = f"grace@{domain}"
        events = [
            _event(tid, "user.created", {"id": "u1", "email": email, "first_name": "Grace", "last_name": "H", "active": True}),
            _event(tid, "group.created", {"id": "g1", "name": "Finance"}),
            _event(tid, "group.user_added", {"id": "u1", "email": email, "group": {"id": "g1", "name": "Finance"}}),
        ]
        body, headers = _signed(events)
        r = await client.post("/webhooks/polis/dsync", content=body, headers=headers)
        assert r.json() == {"applied": 3}

        groups = (await client.get("/groups", headers=owner)).json()
        finance = next(g for g in groups if g["name"] == "Finance")
        assert finance["source"] == "scim" and [m["email"] for m in finance["members"]] == [email]
        assert (await client.delete(f"/groups/{finance['id']}", headers=owner)).status_code == 409

        # The provisioned user signs in through SSO and gets the group's restricted collection.
        coll = (await client.post("/collections", headers=owner, json={"name": "Finance docs", "visibility": "restricted"})).json()
        await client.patch(f"/collections/{coll['id']}", headers=owner, json={"group_ids": [finance["id"]]})
        r = await _sso_login(client, fake_polis, tid, email)
        token = _fragment(r.headers["location"])["access_token"]
        names = {c["name"] for c in (await client.get("/collections", headers=auth_headers(token))).json()}
        assert "Finance docs" in names

        # Deprovisioning in the IdP cuts access immediately.
        body, headers = _signed([_event(tid, "user.updated", {"id": "u1", "email": email, "active": False})])
        await client.post("/webhooks/polis/dsync", content=body, headers=headers)
        assert (await client.get("/documents", headers=auth_headers(token))).status_code == 401

        body, headers = _signed([_event(tid, "group.deleted", {"id": "g1", "name": "Finance"})])
        await client.post("/webhooks/polis/dsync", content=body, headers=headers)
        assert "Finance" not in {g["name"] for g in (await client.get("/groups", headers=owner)).json()}

    async def test_scim_cannot_touch_other_tenants_or_the_owner(self, client: AsyncClient, fake_polis):
        reg = await _sso_tenant(client, _domain())
        victim = await register_tenant(client, "Victim", unique_email("victim"), PASSWORD)
        owner_email = reg["user"]["email"]
        body, headers = _signed(
            [
                _event(reg["tenant"]["id"], "user.updated", {"email": victim["user"]["email"], "active": False}),
                _event(reg["tenant"]["id"], "user.updated", {"email": owner_email, "active": False}),
            ]
        )
        await client.post("/webhooks/polis/dsync", content=body, headers=headers)
        assert (await login(client, victim["user"]["email"], PASSWORD))["access_token"]
        assert (await login(client, owner_email, PASSWORD))["access_token"]
