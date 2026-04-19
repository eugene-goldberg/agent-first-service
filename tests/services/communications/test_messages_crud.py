def test_send_and_get_message(communications_client):
    send_resp = communications_client.post(
        "/messages",
        json={
            "recipient_id": "person_alice",
            "project_id": "proj_alpha",
            "subject": "Assignment",
            "body": "You've been assigned to milestone #2.",
        },
    )
    assert send_resp.status_code == 201
    body = send_resp.json()
    assert body["data"]["recipient_id"] == "person_alice"
    assert body["data"]["status"] == "sent"
    assert body["_self"].endswith(f"/messages/{body['data']['id']}")
    suggested_rels = {s["rel"] for s in body["_suggested_next"]}
    assert "list_messages" in suggested_rels
    assert "filter_by_recipient" in suggested_rels

    message_id = body["data"]["id"]
    get_resp = communications_client.get(f"/messages/{message_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["subject"] == "Assignment"


def test_list_messages_returns_envelope(communications_client):
    communications_client.post(
        "/messages",
        json={"recipient_id": "person_a", "subject": "s", "body": "b"},
    )
    communications_client.post(
        "/messages",
        json={"recipient_id": "person_b", "subject": "s", "body": "b"},
    )

    resp = communications_client.get("/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["_self"] == "http://testserver/messages"
