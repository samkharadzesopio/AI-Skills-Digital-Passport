from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from .analyzers import RuleBasedAnalyzer, eligible, missing
from .contracts import Analysis, LearningProfile, Options, Proposal, RecommendationDataError
from .providers import SimulatedBTUAcademicProvider, validate_catalog
from .service import RecommendationService


class RuleEngineTests(SimpleTestCase):
    def setUp(self):
        self.provider = SimulatedBTUAcademicProvider()
        self.catalog = self.provider.get_catalog()
        self.by_id = validate_catalog(self.catalog)

    def profile(self, external_id=None, verified=()):
        completed = frozenset(self.provider.get_completed_courses(external_id)) if external_id else frozenset()
        inferred = frozenset(s for cid in completed for s in self.by_id[cid].skills)
        return LearningProfile(completed, frozenset(verified), frozenset(), inferred)

    def service(self, profile, analyzer=None, provider=None):
        return RecommendationService(provider=provider or self.provider, analyzer=analyzer, profiles=SimpleNamespace(load=lambda *a: profile))

    def test_beginner_gets_programming_foundation_not_advanced_deep_learning(self):
        profile = self.profile('DEMO-STUDENT-BEGINNER', ['AI_LITERACY', 'PROMPT_ENGINEERING'])
        result = self.service(profile).recommend('unused')
        ids = [c['course_id'] for c in result['recommendations']]
        self.assertEqual(ids[0], 'DEMO-PYTHON-101')
        self.assertNotIn('DEMO-DEEP-301', ids)
        self.assertEqual(result['analysis_mode'], 'RULE_BASED')
        self.assertTrue(all(not r['ai_assisted'] for r in result['recommendations']))
        blocked = next(c for c in result['blocked_courses'] if c['course_id'] == 'DEMO-DEEP-301')
        self.assertIn('AI-201', blocked['missing_prerequisites']['courses'])

    def test_advanced_profile_has_different_ready_courses(self):
        profile = self.profile('DEMO-STUDENT-ADVANCED')
        result = self.service(profile).recommend('unused', Options(limit=10))
        ids = [c['course_id'] for c in result['recommendations']]
        self.assertIn('AI-201', ids)
        self.assertIn('DEMO-CLOUD-201', ids)
        self.assertIn('DEMO-BACKEND-201', ids)
        self.assertNotIn('DEMO-PYTHON-101', ids)

    def test_empty_history_only_eligible_foundations(self):
        profile = self.profile()
        result = self.service(profile).recommend('unused', Options(limit=10))
        self.assertTrue(result['recommendations'])
        self.assertTrue(all(c['difficulty'] == 'FOUNDATION' for c in result['recommendations']))
        self.assertNotIn('DEMO-PYTHON-101', [c['course_id'] for c in result['recommendations']])

    def test_completed_unavailable_and_redundant_courses_excluded(self):
        profile = self.profile('DEMO-STUDENT-BEGINNER', ['SQL', 'RELATIONAL_MODELING'])
        result = self.service(profile).recommend('unused', Options(limit=10))
        ids = {c['course_id'] for c in result['recommendations']}
        self.assertFalse(ids & profile.completed)
        self.assertNotIn('DEMO-RETIRED-101', ids)
        self.assertNotIn('DEMO-DB-101', ids)

    def test_titles_do_not_control_ranking(self):
        profile = self.profile('DEMO-STUDENT-ADVANCED')
        analyzer = RuleBasedAnalyzer()
        original = analyzer.analyze(profile, self.catalog, Options())
        renamed = tuple(replace(c, title='Completely unrelated title') for c in self.catalog)
        updated = analyzer.analyze(profile, renamed, Options())
        self.assertEqual([(p.course_id,p.score) for p in original.proposals], [(p.course_id,p.score) for p in updated.proposals])

    def test_interests_affect_ranking_and_identical_inputs_are_stable(self):
        profile = self.profile('DEMO-STUDENT-ADVANCED')
        service = self.service(profile)
        baseline = service.recommend('unused')
        selected = service.recommend('unused', Options(interest='SOFTWARE_ENGINEERING'))
        self.assertNotEqual(baseline['recommendations'][0]['course_id'], selected['recommendations'][0]['course_id'])
        self.assertEqual(selected, service.recommend('unused', Options(interest='SOFTWARE_ENGINEERING')))

    def test_explanations_cite_actual_records_and_outcomes(self):
        profile = self.profile('DEMO-STUDENT-BEGINNER')
        result = self.service(profile).recommend('unused')
        python = next(r for r in result['recommendations'] if r['course_id']=='DEMO-PYTHON-101')
        self.assertIn('Computer Science Foundations', python['reason'])
        self.assertIn('PYTHON', python['potential_new_skills'])
        self.assertIn('Write and test Python', python['reason'])
        self.assertEqual(python['related_completed_courses'], ['DEMO-CS-101'])

    def test_pathway_prerequisites_are_satisfied_only_after_assumed_steps(self):
        profile = self.profile('DEMO-STUDENT-BEGINNER')
        result = self.service(profile).recommend('unused')
        any_future = False
        for path in result['pathways']:
            completed, knowledge = set(profile.completed), set(profile.knowledge)
            completed.add(path['recommended_next'])
            knowledge.update(self.by_id[path['recommended_next']].skills)
            for step in path['future_courses']:
                any_future = True
                course = self.by_id[step['course_id']]
                self.assertTrue(eligible(course, completed, knowledge))
                self.assertEqual(step['readiness'], 'FUTURE')
                self.assertFalse(eligible(course, profile.completed, profile.knowledge))
                completed.add(course.course_id)
                knowledge.update(course.skills)
        self.assertTrue(any_future)

    def test_filters_and_no_future_option(self):
        result = self.service(self.profile('DEMO-STUDENT-ADVANCED')).recommend('unused', Options(category='DATABASES', limit=1, include_future_pathway=False))
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['category'], 'DATABASES')
        self.assertFalse(result['pathways'])
        self.assertFalse(result['blocked_courses'])

    def test_replacement_provider_uses_same_contract(self):
        provider = SimpleNamespace(source='SIMULATED_REPLACEMENT', get_catalog=lambda:self.catalog, get_completed_courses=lambda _:())
        result = self.service(self.profile(), provider=provider).recommend('unused')
        self.assertEqual(result['source'], 'SIMULATED_REPLACEMENT')
        self.assertTrue(result['recommendations'])

    def test_catalog_cycle_duplicate_and_missing_prerequisites_fail_closed(self):
        first = self.catalog[0]
        for bad in [(replace(first, prerequisite_courses=(first.course_id,)),)+self.catalog[1:],
                    self.catalog+(first,), (replace(first, prerequisite_courses=('UNKNOWN',)),)+self.catalog[1:], ()]:
            with self.assertRaises(RecommendationDataError):
                validate_catalog(bad)

    def test_invented_blocked_and_nonfinite_analyzer_results_fall_back(self):
        profile = self.profile('DEMO-STUDENT-BEGINNER')
        for proposal in [Proposal('INVENTED', 99, 'Unfounded'), Proposal('DEMO-DEEP-301',99,'Bypass prerequisites'), Proposal('DEMO-PYTHON-101',float('nan'),'Invalid score')]:
            analyzer = SimpleNamespace(analyze=lambda *args,p=proposal: Analysis((p,), 'AI_ASSISTED'))
            result = self.service(profile, analyzer=analyzer).recommend('unused')
            self.assertEqual(result['analysis_mode'], 'RULE_BASED')
            self.assertIn('ANALYZER_UNAVAILABLE_OR_REJECTED', result['warnings'])
            self.assertTrue(all(r['readiness']=='READY' and not r['ai_assisted'] for r in result['recommendations']))

    def test_unavailable_analyzer_falls_back_without_network_or_keys(self):
        analyzer = Mock()
        analyzer.analyze.side_effect = RuntimeError('private provider detail')
        result = self.service(self.profile(), analyzer=analyzer).recommend('unused')
        self.assertEqual(result['analysis_mode'], 'RULE_BASED')
        self.assertNotIn('private provider', str(result))

    def test_invalid_weights_rejected(self):
        with self.assertRaises(RecommendationDataError):
            RuleBasedAnalyzer({'novelty':100})

    def test_verified_skills_do_not_override_hard_course_prerequisites(self):
        profile=self.profile(verified=['PYTHON','PROBABILITY','AI_LITERACY','MACHINE_LEARNING','LINEAR_ALGEBRA'])
        result=self.service(profile).recommend('unused', Options(limit=10))
        self.assertNotIn('AI-201',[c['course_id'] for c in result['recommendations']])

    def test_unknown_history_does_not_borrow_demo_student_courses(self):
        self.assertEqual(self.provider.get_completed_courses('UNKNOWN-UNIVERSITY-ID'),())

    def test_duplicate_and_unavailable_analyzer_proposals_are_rejected(self):
        profile=self.profile()
        for proposals in [(Proposal('DEMO-RETIRED-101',90,'Unavailable'),),
                          (Proposal('AI-101',90,'One'),Proposal('AI-101',80,'Duplicate'))]:
            result=self.service(profile,SimpleNamespace(analyze=lambda *a,p=proposals:Analysis(p))).recommend('unused')
            self.assertIn('ANALYZER_UNAVAILABLE_OR_REJECTED',result['warnings'])
            self.assertNotIn('DEMO-RETIRED-101',[c['course_id'] for c in result['recommendations']])
