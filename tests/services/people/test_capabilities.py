def test_root_lists_all_capabilities(people_client):
    resp = people_client.get("/")
    assert resp.status_code == 200
    body = resp.json()

    assert body["data"]["service"] == "people"
    capability_ids = {c["id"] for c in body["data"]["capabilities"]}
    assert capability_ids == {
        "list_people",
        "find_person",
        "create_person",
        "update_person",
        "filter_by_skill",
        "filter_by_availability",
    }
    assert body["_self"] == "http://testserver/"
    assert isinstance(body["_related"], list)
    assert "_generated_at" in body
