from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentTaskStatus(StrEnum):
    pending = "Pending"
    in_progress = "In Progress"
    completed = "Completed"


class StudentTaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StudentTaskStatus


class StudentDailyInsight(BaseModel):
    headline: str = Field(min_length=4, max_length=160)
    summary: str = Field(min_length=10, max_length=900)
    recommended_action: str = Field(min_length=4, max_length=400)


class TaskPriorityRecommendation(BaseModel):
    assignment_id: int = Field(gt=0)
    rationale: str = Field(min_length=4, max_length=400)


class StudentTaskPrioritization(BaseModel):
    recommendations: list[TaskPriorityRecommendation]


class AssistantTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1600)


class StudentAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=1200)
    conversation: list[AssistantTurn] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Question must contain at least two non-space characters.")
        return normalized


class StudentAssistantResponse(BaseModel):
    answer: str = Field(min_length=2, max_length=4000)
    suggested_questions: list[str] = Field(max_length=5)


class StudentCoachAnalysis(BaseModel):
    strengths: list[str] = Field(max_length=8)
    weak_areas: list[str] = Field(max_length=8)
    learning_gaps: list[str] = Field(max_length=8)
    progress_trend: str = Field(min_length=2, max_length=500)
    recommended_next_topic: str | None = Field(default=None, max_length=160)
    recommended_next_task_assignment_id: int | None = Field(default=None, gt=0)
    improvement_actions: list[str] = Field(max_length=8)
    coaching_advice: str = Field(min_length=2, max_length=1600)


class StudyWeekday(StrEnum):
    monday = "Monday"
    tuesday = "Tuesday"
    wednesday = "Wednesday"
    thursday = "Thursday"
    friday = "Friday"
    saturday = "Saturday"
    sunday = "Sunday"


class StudentStudyPlannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_minutes_per_day: int = Field(ge=15, le=480)
    session_minutes: int = Field(ge=10, le=120)
    study_days: list[StudyWeekday] = Field(
        default_factory=lambda: [
            StudyWeekday.monday,
            StudyWeekday.tuesday,
            StudyWeekday.wednesday,
            StudyWeekday.thursday,
            StudyWeekday.friday,
        ],
        min_length=1,
        max_length=7,
    )
    goal: str | None = Field(default=None, max_length=500)

    @field_validator("study_days")
    @classmethod
    def study_days_must_be_unique(cls, value: list[StudyWeekday]) -> list[StudyWeekday]:
        if len(value) != len(set(value)):
            raise ValueError("Study days must not contain duplicates.")
        return value

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class StudySessionNote(BaseModel):
    assignment_id: int = Field(gt=0)
    study_date: str = Field(min_length=10, max_length=10)
    session_number: int = Field(ge=1, le=100)
    note: str = Field(min_length=2, max_length=400)


class StudentStudyPlanAdvice(BaseModel):
    session_notes: list[StudySessionNote] = Field(max_length=100)
    priority_explanation: str = Field(min_length=2, max_length=1000)
    study_advice: str = Field(min_length=2, max_length=1200)


class PracticeType(StrEnum):
    multiple_choice = "Multiple Choice"
    short_answer = "Short Answer"
    mini_challenge = "Mini Challenge"
    revision_questions = "Revision Questions"


class StudentPracticeGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str | None = Field(default=None, min_length=2, max_length=160)
    difficulty: Literal["Beginner", "Intermediate", "Advanced"] | None = None
    question_count: int = Field(default=5, ge=1, le=10)
    practice_type: PracticeType = PracticeType.multiple_choice

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class GeneratedPracticeQuestion(BaseModel):
    question_id: int = Field(ge=1, le=10)
    question: str = Field(min_length=8, max_length=1200)
    topic: str = Field(min_length=2, max_length=160)
    difficulty: Literal["Beginner", "Intermediate", "Advanced"]
    options: list[str] = Field(max_length=6)
    correct_answer: str = Field(min_length=1, max_length=1200)
    explanation: str = Field(min_length=8, max_length=1200)


class GeneratedPracticeSet(BaseModel):
    questions: list[GeneratedPracticeQuestion] = Field(min_length=1, max_length=10)


class StudentPracticeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: int = Field(ge=1, le=10)
    answer: str = Field(min_length=1, max_length=2000)


class StudentPracticeSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[StudentPracticeAnswer] = Field(min_length=1, max_length=10)


class PracticeAnswerEvaluation(BaseModel):
    question_id: int = Field(ge=1, le=10)
    score: int = Field(ge=0, le=100)
    feedback: str = Field(min_length=2, max_length=1000)


class StudentPracticeEvaluation(BaseModel):
    evaluations: list[PracticeAnswerEvaluation] = Field(max_length=10)
    recommendation: str = Field(min_length=2, max_length=1000)


class StudentProgressReportAnalysis(BaseModel):
    summary: str = Field(min_length=10, max_length=2500)
    strengths: list[str] = Field(max_length=8)
    weak_skills: list[str] = Field(max_length=8)
    learning_gaps: list[str] = Field(max_length=8)
    recommended_topics: list[str] = Field(max_length=8)
    next_skills: list[str] = Field(max_length=8)
    career_suggestions: list[str] = Field(max_length=8)
    overall_recommendation: str = Field(min_length=4, max_length=1200)
