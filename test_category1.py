# note to self: run with "pytest -W ignore::DeprecationWarning" in terminal
from flask import session
import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            yield client


def test_server_connection(client):
    """Test ID 1: Frontend to backend server connection"""
    response = client.get("/")
    assert response.status_code == 200


def test_logout_functionality(client):
    """Test ID 2: User logout functionality"""
    client.post("/login", data={"email": "admin1@gmail.com", "password": "1234"})
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "UserID" not in sess


def test_session_persistence(client):
    """Test ID 3: Session persistence after page refresh"""
    client.post("/login", data={"email": "admin1@gmail.com", "password": "1234"})
    client.get("/")  # Simulate a page refresh
    with client.session_transaction() as sess:
        assert "UserID" in sess


def test_client_side_routing(client):
    """Test ID 4: Client-side routing"""
    response = client.post(
        "/login",
        data={"email": "admin1@gmail.com", "password": "1234"},
        follow_redirects=True,
    )
    print("Login response:", response.data.decode())  # Debug: Print login response

    with client.session_transaction() as sess:
        print("Session after login:", dict(sess))  # Debug: Print session data

    response = client.get(
        "/add_user", follow_redirects=False
    )  # Check if there's an immediate redirect
    print(
        "Response to /add_user:", response.status_code, response.data.decode()
    )  # Debug: Print status code and page content

    assert (
        response.status_code == 200
    ), f"Expected 200, got {response.status_code} with response: {response.data.decode()}"

    # Check for specific elements in the HTML content
    html_content = response.data.decode()
    assert (
        "Add New User" in html_content
    ), "Page title 'Add New User' not found in response"
    assert (
        '<label for="email">Email:</label>' in html_content
    ), "Email label not found in response"
    assert (
        '<select id="role" name="role" required>' in html_content
    ), "Role selection not found in response"


def test_api_endpoint_availability(client):
    """Test ID 7: API endpoint availability"""
    response = client.get(
        "/documentation"
    )  # Assuming '/documentation' is a valid endpoint
    assert response.status_code == 200, "API endpoint '/documentation' is not available"


def test_routing_to_non_existent_route(client):
    """Test ID 8: Routing to non-existent route"""
    response = client.get("/nonexistent")
    assert response.status_code == 404, "Non-existent route did not return 404"


def test_session_isolation(client):
    """Test ID 11: Session isolation test"""
    # Log in with the first set of credentials and check session
    client.post("/login", data={"email": "admin1@gmail.com", "password": "1234"})
    with client.session_transaction() as sess:
        assert "UserID" in sess, "Session not established for first user"

    # Using a new client to simulate another browser
    with app.test_client() as new_client:
        new_client.post(
            "/login", data={"email": "veterinarian1@gmail.com", "password": "1234"}
        )
        with new_client.session_transaction() as new_sess:
            assert "UserID" in new_sess, "Session not established for second user"
            assert (
                new_client.get("/").status_code == 200
            ), "Second user cannot access the home page"

    # Ensure the original client still has the first user's session intact
    with client.session_transaction() as sess:
        assert (
            "UserID" in sess
        ), "Session for first user got terminated after second login"
