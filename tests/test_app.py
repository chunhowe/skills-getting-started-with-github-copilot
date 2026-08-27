from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app


@pytest.fixture(autouse=True)
def restore_participants():
    original_participants = {
        activity_name: deepcopy(activity["participants"])
        for activity_name, activity in activities.items()
    }

    yield

    for activity_name, participants in original_participants.items():
        activities[activity_name]["participants"] = participants


@pytest.fixture
def client():
    return TestClient(app)


def test_root_redirects_to_static_index(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_get_activities_returns_seeded_activity_data(client):
    response = client.get("/activities")

    assert response.status_code == 200
    data = response.json()
    assert set(data) == set(activities)
    assert data["Chess Club"] == {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    }


def test_signup_adds_participant(client):
    response = client.post(
        "/activities/Chess%20Club/signup",
        params={"email": "new.student@mergington.edu"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Signed up new.student@mergington.edu for Chess Club"
    }
    assert "new.student@mergington.edu" in client.get("/activities").json()["Chess Club"]["participants"]


def test_unregister_removes_participant(client):
    response = client.delete(
        "/activities/Chess%20Club/signup",
        params={"email": "michael@mergington.edu"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Unregistered michael@mergington.edu from Chess Club"
    }
    assert "michael@mergington.edu" not in client.get("/activities").json()["Chess Club"]["participants"]


def test_duplicate_signup_returns_bad_request(client):
    response = client.post(
        "/activities/Chess%20Club/signup",
        params={"email": "michael@mergington.edu"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Student is already signed up for this activity"
    }


def test_unknown_activity_returns_not_found_for_signup_and_unregister(client):
    signup_response = client.post(
        "/activities/Unknown%20Club/signup",
        params={"email": "student@mergington.edu"},
    )
    unregister_response = client.delete(
        "/activities/Unknown%20Club/signup",
        params={"email": "student@mergington.edu"},
    )

    assert signup_response.status_code == 404
    assert signup_response.json() == {"detail": "Activity not found"}
    assert unregister_response.status_code == 404
    assert unregister_response.json() == {"detail": "Activity not found"}


def test_unregistering_unknown_participant_returns_not_found(client):
    response = client.delete(
        "/activities/Chess%20Club/signup",
        params={"email": "unknown@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Student is not signed up for this activity"
    }


@pytest.mark.parametrize("method", ["post", "delete"])
def test_mutation_requires_email(client, method):
    response = getattr(client, method)("/activities/Chess%20Club/signup")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "email"]


def test_signup_accepts_non_email_text_as_current_behavior(client):
    response = client.post(
        "/activities/Art%20Club/signup",
        params={"email": "not-an-email"},
    )

    assert response.status_code == 200
    assert "not-an-email" in activities["Art Club"]["participants"]


def test_signup_does_not_enforce_capacity_as_current_behavior(client):
    activity = activities["Art Club"]
    activity["participants"] = [f"student-{index}@mergington.edu" for index in range(activity["max_participants"])]

    response = client.post(
        "/activities/Art%20Club/signup",
        params={"email": "over-capacity@mergington.edu"},
    )

    assert response.status_code == 200
    assert "over-capacity@mergington.edu" in activity["participants"]
