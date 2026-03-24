# CourseHub - Learning Management System

A complete LMS starter with:

- Course creation and management for instructors
- Video lesson streaming endpoints
- Quiz authoring and quiz submission
- Progress tracking per lesson
- Certificate issuance when completion criteria are met
- Separate student and instructor dashboards
- JWT-secured role-based access control

## Tech Stack

- FastAPI + Jinja templates
- SQLite + SQLAlchemy ORM
- JWT authentication

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/` - login/register
- `http://127.0.0.1:8000/dashboard/instructor`
- `http://127.0.0.1:8000/dashboard/student`
- `http://127.0.0.1:8000/docs` - API docs

## API Highlights

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/courses` (instructor)
- `POST /api/courses/{course_id}/enroll` (student)
- `POST /api/courses/{course_id}/lessons` (instructor)
- `GET /api/lessons/{lesson_id}/stream`
- `POST /api/courses/{course_id}/quizzes` (instructor)
- `POST /api/quizzes/{quiz_id}/submit` (student)
- `POST /api/lessons/{lesson_id}/complete` (student)
- `GET /api/courses/{course_id}/progress` (student)
- `GET /api/certificates` (student)

## Notes

- For video streaming, set `video_path` to a file path under `app/` (e.g., `static/sample.mp4`).
- The app creates `app/coursehub.db` automatically on startup.
