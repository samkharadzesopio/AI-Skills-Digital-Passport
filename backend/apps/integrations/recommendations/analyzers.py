"""Academic rules use structured outcomes/requirements, never title matching."""
from .contracts import Analysis, LEVELS, Proposal, RecommendationDataError

DEFAULT_WEIGHTS = {'novelty': 35, 'progression': 20, 'foundation_unlock': 20, 'interest': 15, 'complement': 10}


def missing(course, completed, knowledge):
    return {'courses': sorted(set(course.prerequisite_courses) - completed),
            'skills': sorted(set(course.prerequisite_skills) - knowledge)}


def eligible(course, completed, knowledge):
    gaps = missing(course, completed, knowledge)
    return (course.available is not False and course.course_id not in completed
            and not gaps['courses'] and not gaps['skills'] and bool(course.skills - knowledge))


class RuleBasedAnalyzer:
    def __init__(self, weights=None):
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        if set(self.weights) != set(DEFAULT_WEIGHTS) or any(type(v) is not int or v < 0 for v in self.weights.values()) or sum(self.weights.values()) != 100:
            raise RecommendationDataError('Scoring weights must be nonnegative integers totaling 100.')

    def analyze(self, profile, catalog, options):
        by_id = {c.course_id: c for c in catalog}
        level = max((LEVELS[by_id[c].difficulty] for c in profile.completed if c in by_id), default=0)
        proposals = []
        for c in catalog:
            if not eligible(c, profile.completed, profile.knowledge):
                continue
            if options.category and c.category != options.category or options.difficulty and c.difficulty != options.difficulty:
                continue
            new = c.skills - profile.knowledge
            relevant = (set(c.prerequisite_skills) | set(c.background_skills)) & profile.knowledge
            related = set(c.prerequisite_courses) & profile.completed
            unlocks = [other.course_id for other in catalog if other.course_id != c.course_id
                       and other.available is not False
                       and not eligible(other, profile.completed, profile.knowledge)
                       and eligible(other, profile.completed | {c.course_id}, profile.knowledge | c.skills)]
            factors = {
                'novelty': len(new) / len(c.skills),
                'progression': 1 if LEVELS[c.difficulty] == min(level + 1, 3) else .5,
                'foundation_unlock': min(len(unlocks), 2) / 2,
                'interest': int(bool(options.interest and options.interest in c.interests)),
                'complement': min(len(relevant) + len(related), 2) / 2,
            }
            score = round(sum(self.weights[k] * factors[k] for k in self.weights), 2)
            evidence = []
            if related:
                evidence.append('Builds on completed ' + ', '.join(by_id[cid].title for cid in sorted(related)))
            if relevant:
                evidence.append('Uses existing competencies ' + ', '.join(sorted(relevant)))
            if not evidence:
                evidence.append('This eligible foundation has no unmet course or competency prerequisites')
            evidence.append('Develops ' + ', '.join(sorted(new)) + ' through ' + '; '.join(o.description for o in c.learning_outcomes if o.competency in new))
            if unlocks:
                evidence.append('Completing it can unlock ' + ', '.join(sorted(unlocks)))
            reason = '. '.join(evidence)
            if len(reason) > 2000:
                reason = reason[:1950].rsplit(' ', 1)[0] + '...'
            proposals.append(Proposal(c.course_id, score, reason))
        return Analysis(tuple(sorted(proposals, key=lambda p: (-p.score, p.course_id))))
