from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'coursehub.db'}"
SECRET_KEY = "coursehub-dev-secret-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Role(str, Enum):
    instructor = "instructor"
    student = "student"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    role = Column(SqlEnum(Role), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    instructor = relationship("User")
    lessons = relationship("Lesson", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_course"),)

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    video_path = Column(String(255), nullable=False)
    position = Column(Integer, default=1, nullable=False)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)

    questions = relationship("QuizQuestion", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_index = Column(Integer, nullable=False)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson"),)

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    completed = Column(Boolean, default=True, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_cert_student_course"),)

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: str
    password: str = Field(min_length=6)
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CourseCreate(BaseModel):
    title: str
    description: str


class LessonCreate(BaseModel):
    title: str
    video_path: str
    position: int = 1


class QuizQuestionInput(BaseModel):
    prompt: str
    options: list[str]
    correct_index: int


class QuizCreate(BaseModel):
    title: str
    questions: list[QuizQuestionInput]


class QuizSubmit(BaseModel):
    answers: list[int]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = db.get(User, int(user_id))
    if not user:
        raise credentials_exception
    return user


def require_role(role: Role):
    def _require(user: User = Depends(get_current_user)):
        if user.role != role:
            raise HTTPException(status_code=403, detail=f"{role.value} role required")
        return user

    return _require


def issue_certificate_if_eligible(student_id: int, course_id: int, db: Session):
    lessons = db.scalars(select(Lesson).where(Lesson.course_id == course_id)).all()
    if not lessons:
        return None

    lesson_ids = [l.id for l in lessons]
    completed_count = db.query(Progress).filter(
        Progress.student_id == student_id,
        Progress.lesson_id.in_(lesson_ids),
        Progress.completed.is_(True),
    ).count()
    lesson_completion = completed_count / len(lessons)

    quiz_ids = [q.id for q in db.scalars(select(Quiz).where(Quiz.course_id == course_id)).all()]
    quiz_passed = True
    if quiz_ids:
        latest_score = db.query(QuizAttempt).filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id.in_(quiz_ids),
        ).order_by(QuizAttempt.created_at.desc()).first()
        quiz_passed = bool(latest_score and latest_score.score >= 70)

    cert = db.query(Certificate).filter_by(student_id=student_id, course_id=course_id).first()
    if lesson_completion >= 0.8 and quiz_passed and not cert:
        cert = Certificate(student_id=student_id, course_id=course_id)
        db.add(cert)
        db.commit()
        db.refresh(cert)
    return cert


app = FastAPI(title="CourseHub LMS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard/instructor", response_class=HTMLResponse)
def instructor_dashboard(request: Request):
    return templates.TemplateResponse("instructor.html", {"request": request})


@app.get("/dashboard/student", response_class=HTMLResponse)
def student_dashboard(request: Request):
    return templates.TemplateResponse("student.html", {"request": request})


@app.post("/api/auth/register", response_model=Token)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token)


@app.post("/api/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token)


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.full_name, "role": user.role.value, "email": user.email}


@app.post("/api/courses")
def create_course(
    payload: CourseCreate,
    user: User = Depends(require_role(Role.instructor)),
    db: Session = Depends(get_db),
):
    course = Course(title=payload.title, description=payload.description, instructor_id=user.id)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@app.get("/api/courses")
def list_courses(db: Session = Depends(get_db)):
    courses = db.scalars(select(Course)).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "instructor_id": c.instructor_id,
        }
        for c in courses
    ]


@app.post("/api/courses/{course_id}/enroll")
def enroll(
    course_id: int,
    user: User = Depends(require_role(Role.student)),
    db: Session = Depends(get_db),
):
    if not db.get(Course, course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    if db.query(Enrollment).filter_by(student_id=user.id, course_id=course_id).first():
        return {"message": "Already enrolled"}
    enrollment = Enrollment(student_id=user.id, course_id=course_id)
    db.add(enrollment)
    db.commit()
    return {"message": "Enrolled"}


@app.post("/api/courses/{course_id}/lessons")
def create_lesson(
    course_id: int,
    payload: LessonCreate,
    user: User = Depends(require_role(Role.instructor)),
    db: Session = Depends(get_db),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != user.id:
        raise HTTPException(status_code=403, detail="Only the course instructor can edit this course")

    lesson = Lesson(course_id=course_id, title=payload.title, video_path=payload.video_path, position=payload.position)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


@app.get("/api/courses/{course_id}/lessons")
def list_lessons(course_id: int, db: Session = Depends(get_db)):
    lessons = db.query(Lesson).filter_by(course_id=course_id).order_by(Lesson.position.asc()).all()
    return [{"id": l.id, "title": l.title, "video_path": l.video_path, "position": l.position} for l in lessons]


@app.get("/api/lessons/{lesson_id}/stream")
def stream_video(lesson_id: int, db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    video = BASE_DIR / lesson.video_path
    if not video.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video)


@app.post("/api/courses/{course_id}/quizzes")
def create_quiz(
    course_id: int,
    payload: QuizCreate,
    user: User = Depends(require_role(Role.instructor)),
    db: Session = Depends(get_db),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.instructor_id != user.id:
        raise HTTPException(status_code=403, detail="Only the course instructor can edit this course")
    quiz = Quiz(course_id=course_id, title=payload.title)
    db.add(quiz)
    db.flush()

    for question in payload.questions:
        if question.correct_index >= len(question.options):
            raise HTTPException(status_code=400, detail="Invalid correct index")
        db.add(
            QuizQuestion(
                quiz_id=quiz.id,
                prompt=question.prompt,
                options=question.options,
                correct_index=question.correct_index,
            )
        )
    db.commit()
    db.refresh(quiz)
    return {"quiz_id": quiz.id, "title": quiz.title}


@app.get("/api/courses/{course_id}/quizzes")
def get_quizzes(course_id: int, db: Session = Depends(get_db)):
    quizzes = db.query(Quiz).filter_by(course_id=course_id).all()
    result = []
    for quiz in quizzes:
        questions = db.query(QuizQuestion).filter_by(quiz_id=quiz.id).all()
        result.append(
            {
                "id": quiz.id,
                "title": quiz.title,
                "questions": [
                    {"id": q.id, "prompt": q.prompt, "options": q.options}
                    for q in questions
                ],
            }
        )
    return result


@app.post("/api/quizzes/{quiz_id}/submit")
def submit_quiz(
    quiz_id: int,
    payload: QuizSubmit,
    user: User = Depends(require_role(Role.student)),
    db: Session = Depends(get_db),
):
    questions = db.query(QuizQuestion).filter_by(quiz_id=quiz_id).all()
    if not questions:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Answer count does not match question count")

    correct = sum(1 for idx, q in enumerate(questions) if payload.answers[idx] == q.correct_index)
    score = round((correct / len(questions)) * 100, 2)
    attempt = QuizAttempt(student_id=user.id, quiz_id=quiz_id, score=score)
    db.add(attempt)
    db.commit()

    quiz = db.get(Quiz, quiz_id)
    cert = issue_certificate_if_eligible(user.id, quiz.course_id, db)
    return {"score": score, "certificate_issued": bool(cert)}


@app.post("/api/lessons/{lesson_id}/complete")
def complete_lesson(
    lesson_id: int,
    user: User = Depends(require_role(Role.student)),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    progress = db.query(Progress).filter_by(student_id=user.id, lesson_id=lesson_id).first()
    if not progress:
        progress = Progress(student_id=user.id, lesson_id=lesson_id, completed=True)
        db.add(progress)
    else:
        progress.completed = True
        progress.completed_at = datetime.utcnow()
    db.commit()

    cert = issue_certificate_if_eligible(user.id, lesson.course_id, db)
    return {"message": "Lesson marked complete", "certificate_issued": bool(cert)}


@app.get("/api/courses/{course_id}/progress")
def course_progress(
    course_id: int,
    user: User = Depends(require_role(Role.student)),
    db: Session = Depends(get_db),
):
    lesson_ids = [l.id for l in db.query(Lesson).filter_by(course_id=course_id).all()]
    if not lesson_ids:
        return {"completion_percent": 0, "certificate": False}
    completed = db.query(Progress).filter(
        Progress.student_id == user.id,
        Progress.lesson_id.in_(lesson_ids),
        Progress.completed.is_(True),
    ).count()
    cert = db.query(Certificate).filter_by(student_id=user.id, course_id=course_id).first()
    return {"completion_percent": round(completed / len(lesson_ids) * 100, 2), "certificate": bool(cert)}


@app.get("/api/certificates")
def my_certificates(
    user: User = Depends(require_role(Role.student)),
    db: Session = Depends(get_db),
):
    certs = db.query(Certificate).filter_by(student_id=user.id).all()
    return [
        {
            "id": c.id,
            "course_id": c.course_id,
            "issued_at": c.issued_at.isoformat(),
        }
        for c in certs
    ]
