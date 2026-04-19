def test_create_get_patch_person(people_client):
    create_resp = people_client.post(
        "/people",
        json={"name": "Alice Chen", "role": "senior engineer", "skills": ["python", "langgraph"]},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["data"]["name"] == "Alice Chen"
    assert created["data"]["available"] is True
    assert created["data"]["current_load"] == 0
    person_id = created["data"]["id"]
    assert created["_self"].endswith(f"/people/{person_id}")
    assert any(s["rel"] == "update_person" for s in created["_suggested_next"])

    get_resp = people_client.get(f"/people/{person_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == person_id

    patch_resp = people_client.patch(
        f"/people/{person_id}",
        json={"available": False, "current_load": 3},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["available"] is False
    assert patch_resp.json()["data"]["current_load"] == 3


def test_list_people_returns_envelope(people_client):
    people_client.post("/people", json={"name": "A", "role": "r", "skills": []})
    people_client.post("/people", json={"name": "B", "role": "r", "skills": []})

    list_resp = people_client.get("/people")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert len(body["data"]) == 2
    assert body["_self"] == "http://testserver/people"
    assert isinstance(body["_related"], list)
