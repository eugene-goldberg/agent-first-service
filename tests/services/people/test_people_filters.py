def test_filter_by_skill_case_insensitive(people_client):
    people_client.post("/people", json={"name": "Alice", "role": "eng", "skills": ["Python", "LangGraph"]})
    people_client.post("/people", json={"name": "Bob", "role": "pm", "skills": ["figma"]})

    resp = people_client.get("/people?skill=python")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()["data"]}
    assert names == {"Alice"}


def test_filter_by_availability(people_client):
    r1 = people_client.post("/people", json={"name": "A", "role": "r", "skills": []})
    r2 = people_client.post("/people", json={"name": "B", "role": "r", "skills": []})
    id_a = r1.json()["data"]["id"]

    people_client.patch(f"/people/{id_a}", json={"available": False})

    resp = people_client.get("/people?available=true")
    assert [p["name"] for p in resp.json()["data"]] == ["B"]


def test_combine_skill_and_availability(people_client):
    r1 = people_client.post("/people", json={"name": "A", "role": "r", "skills": ["python"]})
    r2 = people_client.post("/people", json={"name": "B", "role": "r", "skills": ["python"]})
    id_a = r1.json()["data"]["id"]

    people_client.patch(f"/people/{id_a}", json={"available": False})

    resp = people_client.get("/people?skill=python&available=true")
    names = {p["name"] for p in resp.json()["data"]}
    assert names == {"B"}
