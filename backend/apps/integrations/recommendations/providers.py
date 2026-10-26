import json
import re
from functools import lru_cache
from pathlib import Path
from .contracts import Course, Outcome, CATEGORIES, INTERESTS, LEVELS, RecommendationDataError

DATA = Path(__file__).with_name('data')


@lru_cache(maxsize=2)
def _read(name):
    raw = (DATA / name).read_bytes()
    if len(raw) > 1024 * 1024:
        raise RecommendationDataError('Provider dataset is too large.')
    return json.loads(raw)


def _codes(values):
    if not isinstance(values, (list, tuple)) or len(values) > 50 or any(
        not isinstance(v, str) or not re.fullmatch(r'[A-Z0-9_-]{1,100}', v) for v in values
    ) or len(set(values)) != len(values):
        raise RecommendationDataError('Invalid structured competency/course identifiers.')
    return tuple(values)


def validate_catalog(catalog):
    if not isinstance(catalog, tuple) or not 1 <= len(catalog) <= 200 or any(not isinstance(c, Course) for c in catalog):
        raise RecommendationDataError('Catalog unavailable or unsupported.')
    by_id = {c.course_id: c for c in catalog}
    if len(by_id) != len(catalog):
        raise RecommendationDataError('Duplicate catalog identifiers.')
    for c in catalog:
        _codes([c.course_id])
        if c.category not in CATEGORIES or c.difficulty not in LEVELS or (c.available is not None and type(c.available) is not bool):
            raise RecommendationDataError('Invalid academic course attributes.')
        if not isinstance(c.department, str) or not 1 <= len(c.department) <= 120:
            raise RecommendationDataError('Invalid course department.')
        for field, maximum in ((c.credits, 30), (c.suggested_semester, 20)):
            if field is not None and (type(field) is not int or not 1 <= field <= maximum):
                raise RecommendationDataError('Invalid optional academic metadata.')
        if not isinstance(c.title, str) or not 1 <= len(c.title) <= 200 or not isinstance(c.description, str) or len(c.description) > 3000:
            raise RecommendationDataError('Invalid course text.')
        if not 1 <= len(c.learning_outcomes) <= 20 or any(not isinstance(o, Outcome) or not isinstance(o.description, str) or not 1 <= len(o.description) <= 500 for o in c.learning_outcomes):
            raise RecommendationDataError('Invalid learning outcomes.')
        _codes([o.competency for o in c.learning_outcomes])
        for values in (c.prerequisite_courses, c.prerequisite_skills, c.background_skills, c.interests):
            _codes(values)
        if set(c.prerequisite_courses) - by_id.keys() or set(c.interests) - set(INTERESTS):
            raise RecommendationDataError('Unknown prerequisite or learning direction.')
    visiting, done = set(), set()
    def visit(cid):
        if cid in visiting:
            raise RecommendationDataError('Catalog dependency cycle.')
        if cid in done:
            return
        visiting.add(cid)
        for requirement in by_id[cid].prerequisite_courses:
            visit(requirement)
        visiting.remove(cid)
        done.add(cid)
    for cid in by_id:
        visit(cid)
    return by_id


class SimulatedBTUAcademicProvider:
    source = 'SIMULATED_BTU_CATALOG'
    disclaimer = 'All catalog offerings and academic history fixtures are simulated. Guidance is not official course approval, enrollment availability or a credential award.'

    def get_catalog(self):
        rows = _read('catalog.json')['courses']
        result = tuple(Course(**{**row,
            'learning_outcomes': tuple(Outcome(**o) for o in row['learning_outcomes']),
            **{key: tuple(row.get(key, ())) for key in ('prerequisite_courses', 'prerequisite_skills', 'background_skills', 'interests')},
        }) for row in rows)
        validate_catalog(result)
        return result

    def get_completed_courses(self, external_student_id):
        # Stable simulated provider data is indexed once, not scanned per request.
        # Unknown identities receive empty history, never another student's sample.
        return _codes(_read('history.json')['students'].get(external_student_id, []))
