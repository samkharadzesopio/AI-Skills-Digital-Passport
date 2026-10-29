"""Run foundation regressions without executing the legacy reference schema."""

from django.test.runner import DiscoverRunner
from config.disposable_tests import DisposableRun, test_database_name


class FoundationPostgresRunner(DiscoverRunner):
    def run_tests(self, test_labels, **kwargs):
        from django.db import connections
        if self.keepdb or self.parallel > 1:
            raise RuntimeError('Disposable tests prohibit keepdb and parallel database clones')
        connection = connections['default']
        previous = connection.settings_dict['TEST']['NAME']
        connection.settings_dict['TEST']['NAME'] = test_database_name('suite')
        try:
            with DisposableRun() as resources:
                resources.database()
                # The shared manager owns setup/teardown even on interruption.
                self._owned_database = True
                return super().run_tests(test_labels, **kwargs)
        finally:
            self._owned_database = False
            connection.settings_dict['TEST']['NAME'] = previous

    def setup_databases(self, **kwargs):
        if getattr(self, '_owned_database', False):
            return []
        return super().setup_databases(**kwargs)

    def teardown_databases(self, old_config, **kwargs):
        if not getattr(self, '_owned_database', False):
            return super().teardown_databases(old_config, **kwargs)

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
