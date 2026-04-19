def test_message_not_found_returns_semantic_envelope(communications_client):
    resp = communications_client.get("/messages/msg_unknown")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "message_not_found"
    # _try_instead is a descriptive string pointing to GET /messages
    assert "/messages" in body["_try_instead"]
    assert isinstance(body["_related"], list)


def test_missing_required_fields_returns_validation_error(communications_client):
    resp = communications_client.post("/messages", json={"recipient_id": "person_a"})
    assert resp.status_code == 422


def test_blank_subject_returns_validation_error(communications_client):
    resp = communications_client.post(
        "/messages",
        json={"recipient_id": "person_a", "subject": "", "body": "hi"},
    )
    assert resp.status_code == 422
