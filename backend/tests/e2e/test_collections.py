"""Collections and groups decide what each caller can retrieve, list, read and get cached answers from."""

import io

import pytest
from httpx import AsyncClient

from tests.e2e.helpers import api_key_headers, auth_headers, login, register_tenant, unique_email
from tests.e2e.test_access_control import PASSWORD, create_user

pytestmark = pytest.mark.e2e

GENERAL = "Office hours are 9 to 5. The cafeteria serves lunch at noon."
SALES = "The Q3 sales target is 4 million dollars across all regions."
HR = "Executive salaries: the CEO earns 410,000 dollars. Salary bands are confidential."


async def _upload(client, token, name, text, collection_id=None):
    data = {"collection_id": collection_id} if collection_id else {}
    r = await client.post(
        "/documents",
        headers=auth_headers(token),
        files={"file": (name, io.BytesIO(text.encode()), "text/plain")},
        data=data,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _setup(client: AsyncClient) -> dict:
    reg = await register_tenant(client, "Access Co", unique_email("owner"), PASSWORD)
    owner = reg["access_token"]
    h = auth_headers(owner)
    sales = (await client.post("/collections", headers=h, json={"name": "Sales", "visibility": "tenant"})).json()
    hr = (await client.post("/collections", headers=h, json={"name": "HR", "visibility": "restricted"})).json()
    hr_group = (await client.post("/groups", headers=h, json={"name": "HR team"})).json()
    r = await client.patch(f"/collections/{hr['id']}", headers=h, json={"group_ids": [hr_group["id"]]})
    assert r.status_code == 200 and r.json()["group_ids"] == [hr_group["id"]]

    docs = {
        "general": await _upload(client, owner, "office.txt", GENERAL),
        "sales": await _upload(client, owner, "sales.txt", SALES, sales["id"]),
        "hr": await _upload(client, owner, "salaries.txt", HR, hr["id"]),
    }
    member_email, hr_email = unique_email("member"), unique_email("hr")
    create_user(reg["tenant"]["id"], member_email, "member")
    create_user(reg["tenant"]["id"], hr_email, "member")
    await client.post(f"/groups/{hr_group['id']}/members", headers=h, json={"email": hr_email})
    return {
        **reg,
        "owner": owner,
        "member": (await login(client, member_email, PASSWORD))["access_token"],
        "hr_user": (await login(client, hr_email, PASSWORD))["access_token"],
        "hr_user_email": hr_email,
        "collections": {"sales": sales["id"], "hr": hr["id"]},
        "hr_group": hr_group["id"],
        "docs": docs,
    }


def _source_docs(response) -> set[str]:
    return {s["doc_id"] for s in response.json()["sources"]}


class TestVisibility:
    async def test_member_cannot_list_read_or_retrieve_restricted_documents(self, client: AsyncClient):
        t = await _setup(client)
        h = auth_headers(t["member"])

        listed = {d["id"] for d in (await client.get("/documents", headers=h)).json()}
        assert listed == {t["docs"]["general"], t["docs"]["sales"]}
        for path in (f"/documents/{t['docs']['hr']}", f"/documents/{t['docs']['hr']}/chunks"):
            assert (await client.get(path, headers=h)).status_code == 404

        r = await client.post("/query", headers=h, json={"question": "What does the CEO earn? salaries"})
        assert t["docs"]["hr"] not in _source_docs(r)
        assert "410,000" not in r.json()["answer"]

        names = {c["name"] for c in (await client.get("/collections", headers=h)).json()}
        assert names == {"Sales"}

    async def test_group_member_sees_restricted_collection_until_removed(self, client: AsyncClient):
        t = await _setup(client)
        h = auth_headers(t["hr_user"])
        q = {"question": "What does the CEO earn? salaries"}
        assert t["docs"]["hr"] in _source_docs(await client.post("/query", headers=h, json=q))
        assert (await client.get(f"/documents/{t['docs']['hr']}", headers=h)).status_code == 200

        users = (await client.get("/groups", headers=auth_headers(t["owner"]))).json()[0]["members"]
        hr_user_id = next(u["id"] for u in users if u["email"] == t["hr_user_email"])
        r = await client.delete(f"/groups/{t['hr_group']}/members/{hr_user_id}", headers=auth_headers(t["owner"]))
        assert r.status_code == 200

        assert t["docs"]["hr"] not in _source_docs(await client.post("/query", headers=h, json=q))
        assert (await client.get(f"/documents/{t['docs']['hr']}", headers=h)).status_code == 404

    async def test_owner_cached_answer_is_not_served_to_a_member(self, client: AsyncClient):
        t = await _setup(client)
        q = {"question": "What are the executive salaries?"}
        owner = await client.post("/query", headers=auth_headers(t["owner"]), json=q)
        assert t["docs"]["hr"] in _source_docs(owner)
        member = await client.post("/query", headers=auth_headers(t["member"]), json=q)
        assert member.json()["from_cache"] is False
        assert t["docs"]["hr"] not in _source_docs(member)

    async def test_collection_filter_narrows_but_never_widens(self, client: AsyncClient):
        t = await _setup(client)
        q = "sales target salaries office"
        r = await client.post(
            "/query",
            headers=auth_headers(t["member"]),
            json={"question": q, "collection_ids": [t["collections"]["sales"], t["collections"]["hr"]]},
        )
        assert _source_docs(r) <= {t["docs"]["sales"]}
        r = await client.post(
            "/query", headers=auth_headers(t["owner"]), json={"question": q, "collection_ids": ["general"]}
        )
        assert _source_docs(r) <= {t["docs"]["general"]}


class TestWidgetScope:
    async def test_unscoped_widget_key_never_sees_restricted(self, client: AsyncClient):
        t = await _setup(client)
        r = await client.post(
            "/query", headers=api_key_headers(t["widget_key"]), json={"question": "executive salaries CEO"}
        )
        assert t["docs"]["hr"] not in _source_docs(r)

    async def test_collection_scoped_widget_key_only_sees_its_collection(self, client: AsyncClient):
        t = await _setup(client)
        r = await client.post(
            "/api-keys",
            headers=auth_headers(t["owner"]),
            json={"name": "sales site", "kind": "publishable", "collection_id": t["collections"]["sales"]},
        )
        key = r.json()["api_key"]
        r = await client.post("/query", headers=api_key_headers(key), json={"question": "office hours sales target"})
        assert _source_docs(r) <= {t["docs"]["sales"]} and _source_docs(r)

    async def test_secret_keys_cannot_be_collection_scoped(self, client: AsyncClient):
        t = await _setup(client)
        r = await client.post(
            "/api-keys",
            headers=auth_headers(t["owner"]),
            json={"name": "x", "kind": "secret", "collection_id": t["collections"]["sales"]},
        )
        assert r.status_code == 422


class TestManagement:
    async def test_moving_a_document_changes_who_can_retrieve_it(self, client: AsyncClient):
        t = await _setup(client)
        r = await client.patch(
            f"/documents/{t['docs']['sales']}",
            headers=auth_headers(t["owner"]),
            json={"collection_id": t["collections"]["hr"]},
        )
        assert r.status_code == 200
        r = await client.post("/query", headers=auth_headers(t["member"]), json={"question": "Q3 sales target"})
        assert t["docs"]["sales"] not in _source_docs(r)

    async def test_non_empty_collection_cannot_be_deleted(self, client: AsyncClient):
        t = await _setup(client)
        r = await client.delete(f"/collections/{t['collections']['hr']}", headers=auth_headers(t["owner"]))
        assert r.status_code == 409
        assert (await client.get(f"/documents/{t['docs']['hr']}", headers=auth_headers(t["member"]))).status_code == 404

    async def test_members_cannot_manage_access(self, client: AsyncClient):
        t = await _setup(client)
        h = auth_headers(t["member"])
        assert (await client.post("/collections", headers=h, json={"name": "Mine"})).status_code == 403
        assert (await client.post("/groups", headers=h, json={"name": "Mine"})).status_code == 403
        assert (
            await client.patch(f"/collections/{t['collections']['hr']}", headers=h, json={"visibility": "tenant"})
        ).status_code == 403

    async def test_upload_into_another_tenants_collection_is_rejected(self, client: AsyncClient):
        t = await _setup(client)
        other = await register_tenant(client, "Other Co", unique_email("other"), PASSWORD)
        r = await client.post(
            "/documents",
            headers=auth_headers(other["access_token"]),
            files={"file": ("x.txt", io.BytesIO(b"hello there"), "text/plain")},
            data={"collection_id": t["collections"]["hr"]},
        )
        assert r.status_code == 404
