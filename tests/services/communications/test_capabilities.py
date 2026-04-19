def test_root_lists_all_capabilities(communications_client):
    resp = communications_client.get("/")
    assert resp.status_code == 200
    body = resp.json()

    assert body["data"]["service"] == "communications"
    capability_ids = {c["id"] for c in body["data"]["capabilities"]}
    assert capability_ids == {
        "list_messages",
        "find_message",
        "send_message",
        "filter_by_recipient",
        "filter_by_project",
    }
    assert "_generated_at" in body
    assert isinstance(body["_related"], list)
