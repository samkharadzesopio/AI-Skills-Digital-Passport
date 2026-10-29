import math
from dataclasses import replace
from .analyzers import RuleBasedAnalyzer, eligible, missing
from .contracts import Analysis, LEVELS, Options, RecommendationDataError
from .profile import LearningProfileRepository
from .providers import SimulatedBTUAcademicProvider, validate_catalog


class RecommendationService:
    def __init__(self, provider=None, analyzer=None, profiles=None):
        self.provider = provider or SimulatedBTUAcademicProvider()
        self.analyzer = analyzer or RuleBasedAnalyzer()
        self.profiles = profiles or LearningProfileRepository()

    def _validated(self, analysis, profile, catalog, options):
        by_id = {c.course_id: c for c in catalog}
        if not isinstance(analysis, Analysis) or analysis.analysis_mode not in ('RULE_BASED', 'AI_ASSISTED') or len(analysis.proposals) > len(catalog):
            raise RecommendationDataError('Invalid analyzer result.')
        seen = set()
        for p in analysis.proposals:
            c = by_id.get(p.course_id)
            if (c is None or c.course_id in seen or not eligible(c, profile.completed, profile.knowledge)
                or options.category and c.category != options.category or options.difficulty and c.difficulty != options.difficulty
                or isinstance(p.score, bool) or not isinstance(p.score, (int, float)) or not math.isfinite(p.score) or not 0 <= p.score <= 100
                or not isinstance(p.reason, str) or not 1 <= len(p.reason) <= 2000):
                raise RecommendationDataError('Analyzer output violates academic constraints.')
            seen.add(c.course_id)
        return analysis

    def recommend(self, student_id, options=None):
        options = options or Options()
        catalog = self.provider.get_catalog()
        by_id = validate_catalog(catalog)
        profile = self.profiles.load(student_id, self.provider, catalog)
        warnings = list(profile.warnings)
        try:
            analysis = self._validated(self.analyzer.analyze(profile, catalog, options), profile, catalog, options)
        except Exception:
            if isinstance(self.analyzer, RuleBasedAnalyzer):
                raise
            warnings.append('ANALYZER_UNAVAILABLE_OR_REJECTED')
            analysis = self._validated(RuleBasedAnalyzer().analyze(profile, catalog, options), profile, catalog, options)
        recommendations = []
        for p in analysis.proposals[:options.limit]:
            c = by_id[p.course_id]
            related = set(c.prerequisite_courses) & profile.completed
            relevant = (set(c.prerequisite_skills) | set(c.background_skills)) & profile.knowledge
            recommendations.append({
                'course_id': c.course_id, 'title': c.title, 'department': c.department, 'category': c.category, 'difficulty': c.difficulty,
                'score': p.score, 'readiness': 'READY', 'existing_skills': sorted(relevant),
                'related_completed_courses': sorted(related), 'potential_new_skills': sorted(c.skills - profile.knowledge),
                'missing_prerequisites': [], 'reason': p.reason,
                'progression': f'Eligible level {LEVELS[c.difficulty]}; learning outcomes add competencies and may satisfy later prerequisites.',
                'learning_outcomes': [{'competency': o.competency, 'description': o.description} for o in c.learning_outcomes],
                'ai_assisted': analysis.analysis_mode == 'AI_ASSISTED', 'source': self.provider.source,
                'availability': c.available, 'credits': c.credits, 'suggested_semester': c.suggested_semester,
            })
        pathways = []
        if options.include_future_pathway:
            for recommendation in recommendations[:3]:
                current = by_id[recommendation['course_id']]
                completed, knowledge = set(profile.completed), set(profile.knowledge)
                assumptions, steps = [], []
                for _ in range(3):
                    before_completed, before_knowledge = set(completed), set(knowledge)
                    assumptions.append(current.course_id)
                    completed.add(current.course_id)
                    knowledge.update(current.skills)
                    hypothetical = replace(profile, completed=frozenset(completed), inferred_skills=frozenset(knowledge))
                    future = RuleBasedAnalyzer().analyze(hypothetical, catalog, replace(options, category=None, difficulty=None))
                    unlocked = [p for p in future.proposals if not eligible(by_id[p.course_id], before_completed, before_knowledge)
                                and p.course_id not in assumptions]
                    if not unlocked:
                        break
                    current = by_id[unlocked[0].course_id]
                    steps.append({
                        'course_id': current.course_id, 'title': current.title,
                        'department': current.department, 'category': current.category, 'difficulty': current.difficulty,
                        'readiness': 'FUTURE', 'score': unlocked[0].score,
                        'assumes_completion_of': list(assumptions),
                        'existing_skills': sorted((set(current.prerequisite_skills) | set(current.background_skills)) & profile.knowledge),
                        'related_completed_courses': sorted(set(current.prerequisite_courses) & profile.completed),
                        'potential_new_skills': sorted(current.skills - profile.knowledge),
                        'missing_prerequisites': missing(current, profile.completed, profile.knowledge),
                        'reason': 'Conditional on completing planned courses ' + ', '.join(assumptions) + '. ' + unlocked[0].reason,
                        'progression': 'Planned progression only; no future completion or skill is recorded as earned.',
                        'ai_assisted': False, 'source': self.provider.source,
                        'availability': current.available, 'credits': current.credits, 'suggested_semester': current.suggested_semester,
                    })
                pathways.append({'recommended_next': recommendation['course_id'], 'future_courses': steps})
        blocked = [{'course_id': c.course_id, 'readiness': 'PREREQUISITES_MISSING',
                    'missing_prerequisites': missing(c, profile.completed, profile.knowledge)}
                   for c in sorted(catalog, key=lambda c: c.course_id)
                   if c.available is not False and c.course_id not in profile.completed
                   and (missing(c, profile.completed, profile.knowledge)['courses'] or missing(c, profile.completed, profile.knowledge)['skills'])]
        return {'source': self.provider.source, 'analysis_mode': analysis.analysis_mode,
                'disclaimer': getattr(self.provider, 'disclaimer', 'Academic guidance is not a credential award or enrollment decision.'),
                'profile': {'completed_courses': sorted(profile.completed), 'verified_achievement_skills': sorted(profile.verified_skills),
                            'passport_verified_skills': sorted(profile.passport_skills),
                            'inferred_course_skills': sorted(profile.inferred_skills),
                            'highest_completed_catalog_level': max((LEVELS[by_id[cid].difficulty] for cid in profile.completed if cid in by_id), default=0),
                            'missing_competencies': sorted(set().union(*(c.skills for c in catalog if c.available is not False)) - profile.knowledge)},
                'recommendations': recommendations, 'pathways': pathways,
                'blocked_courses': blocked[:20] if options.include_future_pathway else [], 'warnings': warnings}
