def test_person_not_found_returns_semantic_envelope(people_client):
    resp = people_client.get("/people/person_doesnt_exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "person_not_found"
    # _try_instead is a descriptive string pointing to GET /people
    assert "/people" in body["_try_instead"]
    assert isinstance(body["_related"], list)


def test_patch_unknown_person_returns_semantic_envelope(people_client):
    resp = people_client.patch("/people/nope", json={"available": False})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "person_not_found"


def test_invalid_current_load_returns_validation_error(people_client):
    r = people_client.post("/people", json={"name": "A", "role": "r", "skills": []})
    person_id = r.json()["data"]["id"]

    resp = people_client.patch(f"/people/{person_id}", json={"current_load": -1})
    assert resp.status_code == 422


def test_create_with_empty_name_returns_validation_error(people_client):
    resp = people_client.post("/people", json={"name": "", "role": "r", "skills": []})
    assert resp.status_code == 422
