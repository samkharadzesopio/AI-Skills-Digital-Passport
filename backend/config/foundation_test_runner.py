"""Run foundation regressions without executing the legacy reference schema."""

from django.test.runner import DiscoverRunner


class FoundationPostgresRunner(DiscoverRunner):
    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)

        def tests(items):
            for item in items:
                if hasattr(item, "id"):
                    yield item
                else:
                    yield from tests(item)

        excluded = {
            "apps.students.tests.StudentPostgreSQLTests."
            "test_reference_schema_matches_migration_and_preserves_foreign_keys",
            "apps.skills.tests.SkillPostgreSQLTests.test_reference_schema_matches_migration",
        }
        selected = []
        for test in tests(suite):
            if test.id() in excluded:
                self.log(f"Excluded legacy reference-SQL test: {test.id()}")
            else:
                selected.append(test)
        return self.test_suite(selected)
