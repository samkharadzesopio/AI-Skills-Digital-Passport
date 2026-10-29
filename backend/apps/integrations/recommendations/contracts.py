from dataclasses import dataclass
from typing import Protocol

CATEGORIES = ('ARTIFICIAL_INTELLIGENCE', 'SOFTWARE_ENGINEERING', 'PROGRAMMING', 'IT', 'CYBERSECURITY', 'DATABASES', 'CLOUD', 'DATA_SCIENCE', 'MATHEMATICS')
INTERESTS = ('AI_ENGINEERING', 'SOFTWARE_ENGINEERING', 'CYBERSECURITY', 'DATA_SCIENCE', 'CLOUD_INFRASTRUCTURE')
LEVELS = {'FOUNDATION': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}


class RecommendationDataError(ValueError):
    pass


@dataclass(frozen=True)
class Outcome:
    competency: str
    description: str


@dataclass(frozen=True)
class Course:
    course_id: str
    title: str
    description: str
    department: str
    category: str
    difficulty: str
    learning_outcomes: tuple[Outcome, ...]
    prerequisite_courses: tuple[str, ...] = ()
    prerequisite_skills: tuple[str, ...] = ()
    background_skills: tuple[str, ...] = ()
    interests: tuple[str, ...] = ()
    credits: int | None = None
    suggested_semester: int | None = None
    available: bool | None = None

    @property
    def skills(self):
        return frozenset(o.competency for o in self.learning_outcomes)


@dataclass(frozen=True)
class LearningProfile:
    completed: frozenset[str]
    verified_skills: frozenset[str]
    passport_skills: frozenset[str]
    inferred_skills: frozenset[str]
    warnings: tuple[str, ...] = ()

    @property
    def knowledge(self):
        return self.verified_skills | self.inferred_skills


@dataclass(frozen=True)
class Options:
    category: str | None = None
    interest: str | None = None
    difficulty: str | None = None
    limit: int = 5
    include_future_pathway: bool = True


@dataclass(frozen=True)
class Proposal:
    course_id: str
    score: float
    reason: str


@dataclass(frozen=True)
class Analysis:
    proposals: tuple[Proposal, ...]
    analysis_mode: str = 'RULE_BASED'


class AcademicProvider(Protocol):
    source: str
    disclaimer: str
    def get_catalog(self) -> tuple[Course, ...]: ...
    def get_completed_courses(self, external_student_id: str) -> tuple[str, ...]: ...


class RecommendationAnalyzer(Protocol):
    def analyze(self, profile: LearningProfile, catalog: tuple[Course, ...], options: Options) -> Analysis: ...
