def _send(client, recipient_id, project_id=None, subject="s", body="b"):
    return client.post(
        "/messages",
        json={
            "recipient_id": recipient_id,
            "project_id": project_id,
            "subject": subject,
            "body": body,
        },
    )


def test_filter_by_recipient(communications_client):
    _send(communications_client, "person_alice", project_id="proj_a")
    _send(communications_client, "person_bob", project_id="proj_a")
    _send(communications_client, "person_alice", project_id="proj_b")

    resp = communications_client.get("/messages?recipient_id=person_alice")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert all(m["recipient_id"] == "person_alice" for m in data)


def test_filter_by_project(communications_client):
    _send(communications_client, "person_alice", project_id="proj_a")
    _send(communications_client, "person_bob", project_id="proj_b")

    resp = communications_client.get("/messages?project_id=proj_b")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["recipient_id"] == "person_bob"


def test_combine_recipient_and_project(communications_client):
    _send(communications_client, "person_alice", project_id="proj_a")
    _send(communications_client, "person_alice", project_id="proj_b")
    _send(communications_client, "person_bob", project_id="proj_a")

    resp = communications_client.get("/messages?recipient_id=person_alice&project_id=proj_b")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["project_id"] == "proj_b"
