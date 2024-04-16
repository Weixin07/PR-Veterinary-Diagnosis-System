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
    client.post(
        "/login", data={"email": "admin1@gmail.com", "password": "1234"}
    )  
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "UserID" not in sess


def test_session_persistence(client):
    """Test ID 3: Session persistence after page refresh"""
    client.post(
        "/login", data={"email": "admin1@gmail.com", "password": "1234"}
    )  
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
