from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_register_login_and_create_course_flow():
    register = client.post(
        "/api/auth/register",
        json={
            "full_name": "Instructor One",
            "email": "inst@example.com",
            "password": "password123",
            "role": "instructor",
        },
    )
    assert register.status_code in (200, 400)

    login = client.post(
        "/api/auth/login",
        data={"username": "inst@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    course = client.post(
        "/api/courses",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Python 101", "description": "Basics"},
    )
    assert course.status_code == 200

    list_courses = client.get("/api/courses")
    assert list_courses.status_code == 200
    assert any(c["title"] == "Python 101" for c in list_courses.json())
