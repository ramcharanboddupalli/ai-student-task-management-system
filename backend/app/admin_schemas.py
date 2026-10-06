from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, field_validator


class Difficulty(StrEnum):
    beginner = "Beginner"
    intermediate = "Intermediate"
    advanced = "Advanced"


class Priority(StrEnum):
    low = "Low"
    normal = "Normal"
    high = "High"


class StudentCreate(BaseModel):
    registration_number: str = Field(min_length=2, max_length=50)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    course: str = Field(min_length=2, max_length=100)
    batch: str = Field(min_length=2, max_length=80)
    current_level: Difficulty = Difficulty.beginner

    @field_validator("registration_number", "full_name", "course", "batch")
    @classmethod
    def trim_required_fields(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Value must contain at least two non-space characters.")
        return normalized


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    course: str | None = Field(default=None, min_length=2, max_length=100)
    batch: str | None = Field(default=None, min_length=2, max_length=80)
    current_level: Difficulty | None = None


class TaskDraftRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    course: str = Field(min_length=2, max_length=100)
    level: Difficulty
    goal: str = Field(min_length=10, max_length=1000)
    requirements: list[str] = Field(default_factory=list, max_length=12)


class GeneratedTask(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=20, max_length=3000)
    requirements: list[str] = Field(min_length=1, max_length=12)
    expected_outcome: str = Field(min_length=8, max_length=1000)
    difficulty: Difficulty
    estimated_minutes: int = Field(ge=10, le=480)
    evaluation_criteria: list[str] = Field(min_length=1, max_length=12)


class TaskCreate(GeneratedTask):
    topic: str = Field(min_length=2, max_length=120)
    course: str = Field(min_length=2, max_length=100)
    priority: Priority = Priority.normal


class AssignmentRequest(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=200)
    deadline: date

    @field_validator("deadline")
    @classmethod
    def deadline_must_not_be_in_the_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Deadline must be today or a future date.")
        return value


class TaskRecommendationsRequest(BaseModel):
    course: str = Field(min_length=2, max_length=100)
    level: Difficulty
    topic: str = Field(min_length=2, max_length=120)


class InsightResponse(BaseModel):
    headline: str = Field(min_length=4, max_length=180)
    summary: str = Field(min_length=10, max_length=1200)
    positive_progress: str = Field(min_length=4, max_length=500)
    students_needing_attention: list[int] = Field(max_length=100)
    common_weakness: str = Field(min_length=2, max_length=300)
    recommended_admin_action: str = Field(min_length=4, max_length=500)


class StudentProfileAnalysis(BaseModel):
    strengths: list[str] = Field(max_length=8)
    weak_areas: list[str] = Field(max_length=8)
    learning_gaps: list[str] = Field(max_length=8)
    recommended_actions: list[str] = Field(max_length=8)


class RiskAdvice(BaseModel):
    student_id: int
    suggested_action: str = Field(min_length=4, max_length=500)


class CandidateRecommendation(BaseModel):
    student_id: int
    rationale: str = Field(min_length=4, max_length=400)


class CandidateRecommendations(BaseModel):
    recommendations: list[CandidateRecommendation] = Field(max_length=200)


class PerformanceAdvice(BaseModel):
    students: list[RiskAdvice] = Field(max_length=200)


class BatchInsights(BaseModel):
    summary: str = Field(min_length=10, max_length=1200)
    learning_trends: list[str] = Field(max_length=8)
    recommendations: list[str] = Field(max_length=8)


class CopilotQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class CopilotAnswer(BaseModel):
    answer: str = Field(min_length=2, max_length=4000)
    supporting_data: list[str] = Field(max_length=20)


class ReportType(StrEnum):
    student = "student"
    batch = "batch"
    performance = "performance"
    weekly = "weekly"


class ReportRequest(BaseModel):
    report_type: ReportType
    student_id: int | None = None
    batch: str | None = Field(default=None, min_length=2, max_length=80)

    @field_validator("student_id", mode="before")
    @classmethod
    def positive_student_id(cls, value):
        if value is not None and (not isinstance(value, int) or value < 1):
            raise ValueError("student_id must be a positive integer.")
        return value


class GeneratedReport(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    summary: str = Field(min_length=10, max_length=3000)
    insights: list[str] = Field(max_length=12)
    recommendations: list[str] = Field(max_length=12)
