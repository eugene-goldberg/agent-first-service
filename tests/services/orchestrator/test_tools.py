import pytest
import httpx

from services.orchestrator.tools import HTTPToolbox


@pytest.mark.asyncio
async def test_http_get_returns_parsed_json():
    handler = httpx.MockTransport(lambda req: httpx.Response(
        200, json={"data": {"service": "projects"}}
    ))
    async with httpx.AsyncClient(transport=handler) as client:
        tb = HTTPToolbox(client=client)
        result = await tb.http_get("http://fake/")
        assert result["status_code"] == 200
        assert result["body"]["data"]["service"] == "projects"


@pytest.mark.asyncio
async def test_http_post_sends_body():
    captured: dict = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(201, json={"data": {"id": "proj_1"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        tb = HTTPToolbox(client=client)
        result = await tb.http_post("http://fake/projects", body={"name": "P"})
        assert captured["method"] == "POST"
        assert '"name": "P"' in captured["body"] or '"name":"P"' in captured["body"]
        assert result["status_code"] == 201


@pytest.mark.asyncio
async def test_http_get_returns_error_envelope_on_404():
    def handler(request):
        return httpx.Response(404, json={
            "error": "project_not_found",
            "_try_instead": {"href": "/projects", "verb": "GET"},
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        tb = HTTPToolbox(client=client)
        result = await tb.http_get("http://fake/projects/unknown")
        assert result["status_code"] == 404
        assert result["body"]["error"] == "project_not_found"


@pytest.mark.asyncio
async def test_http_patch_and_delete():
    methods: list[str] = []

    def handler(request):
        methods.append(request.method)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        tb = HTTPToolbox(client=client)
        await tb.http_patch("http://fake/x/1", body={"status": "done"})
        await tb.http_delete("http://fake/x/1")

    assert methods == ["PATCH", "DELETE"]
