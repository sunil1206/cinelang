"""Vocabulary CRUD tests."""


def test_list_vocab_empty(client, auth_headers):
    r = client.get("/api/vocabulary", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_upsert_and_list(client, auth_headers):
    payload = {
        "word": "époustouflant",
        "source_lang": "en",
        "target_lang": "fr",
        "translation": "breathtaking",
        "pos": "Adjective",
        "status": "new",
        "count": 1,
        "contexts": ["La scène était époustouflante."],
        "timestamps": [],
    }
    r = client.post("/api/vocabulary", json=payload, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["word"] == "époustouflant"
    assert data["translation"] == "breathtaking"
    assert data["status"] == "new"

    # List should return the entry
    r2 = client.get("/api/vocabulary?target_lang=fr", headers=auth_headers)
    assert r2.status_code == 200
    words = [w["word"] for w in r2.json()]
    assert "époustouflant" in words


def test_upsert_increments_count(client, auth_headers):
    # Insert once
    payload = {"word": "kiffer", "target_lang": "fr", "count": 1, "contexts": [], "timestamps": []}
    client.post("/api/vocabulary", json=payload, headers=auth_headers)
    # Insert again with higher count
    payload["count"] = 5
    r = client.post("/api/vocabulary", json=payload, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["count"] == 5


def test_update_status(client, auth_headers):
    payload = {"word": "chelou", "target_lang": "fr", "count": 1, "contexts": [], "timestamps": []}
    entry = client.post("/api/vocabulary", json=payload, headers=auth_headers).json()
    vid = entry["id"]

    r = client.patch(f"/api/vocabulary/{vid}/status", json={"status": "learning"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "learning"


def test_delete_vocab(client, auth_headers):
    payload = {"word": "dépaysement", "target_lang": "fr", "count": 1, "contexts": [], "timestamps": []}
    entry = client.post("/api/vocabulary", json=payload, headers=auth_headers).json()
    vid = entry["id"]

    r = client.delete(f"/api/vocabulary/{vid}", headers=auth_headers)
    assert r.status_code == 204

    words = [w["word"] for w in client.get("/api/vocabulary", headers=auth_headers).json()]
    assert "dépaysement" not in words


def test_cannot_delete_other_users_vocab(client, db_session, auth_headers):
    # Create a second user's entry directly in the DB
    from app.models.user import User
    from app.models.vocabulary import VocabEntry
    other = User(google_id="other-id", email="other@x.com", name="Other")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    entry = VocabEntry(user_id=other.id, word="flic", target_lang="fr", count=1)
    db_session.add(entry)
    db_session.commit()

    r = client.delete(f"/api/vocabulary/{entry.id}", headers=auth_headers)
    assert r.status_code == 403
