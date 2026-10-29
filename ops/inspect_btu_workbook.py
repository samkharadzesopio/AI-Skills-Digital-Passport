"""Read-only structural inspection. Does not access Django/database or approve evidence."""
import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from apps.integrations.importers.mapping import excel_grid, map_grid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    args = parser.parse_args()
    with args.workbook.open('rb') as file:
        rows, hashed = excel_grid(file, worksheet='Passport Skill Records')
    headers = rows[3]
    source = [dict(zip(headers, row)) for row in rows[4:] if any(v is not None and str(v).strip() for v in row)]
    populated = [r for r in source if r.get('Record ID')]
    # Inspection-only ID collection describes structure. It is not an institutional
    # allowlist, never provisioned/saved as a policy, and cannot authorize issuance.
    definition = {'worksheet': 'Passport Skill Records', 'evidence_namespace': 'inspection-only',
        'columns': {'external_student_id': ['Student ID'], 'source_event_id': ['Record ID'],
                    'skill_code': ['Skill ID'], 'earned_on': ['Date Earned']},
        'allowed_skill_codes': sorted({r['Skill ID'] for r in populated}),
        'eligible_student_statuses': ['INSPECTION_ONLY_NO_ISSUANCE']}
    mapped = map_grid(rows, kind='SKILL_AWARD', definition=definition)
    by_student = defaultdict(lambda: defaultdict(set))
    for row in populated:
        for field in ['First Name', 'Last Name', 'BTU Email (Test)', 'Student Status']:
            by_student[row['Student ID']][field].add(row[field])
    result = {'sha256': hashed, 'sheet': 'Passport Skill Records', 'header_row': 4,
        'headers': [v for v in headers if v], 'nonempty_rows': len(source),
        'populated_awards': len(populated), 'id_only_rows': sum(sum(v is not None and str(v).strip() != '' for v in r.values()) == 1 for r in source),
        'blank_rows_within_source_extent': len(rows) - 4 - len(source),
        'duplicate_populated_record_ids': sum(n - 1 for n in Counter(r['Record ID'] for r in populated).values() if n > 1),
        'duplicate_student_skill_pairs': sum(n - 1 for n in Counter((r['Student ID'], r['Skill ID']) for r in populated).values() if n > 1),
        'distinct_students_with_awards': len(by_student),
        'identity_conflict_count': sum(any(len(v) > 1 for v in fields.values()) for fields in by_student.values()),
        'formula_cells': sum(isinstance(v, str) and v.startswith('=') for row in rows for v in row),
        'sync_status_counts': dict(Counter(str(r['Passport Sync Status']) for r in populated)),
        'student_status_counts': dict(Counter(str(r['Student Status']) for r in populated)),
        'structurally_mapped_awards': len(mapped['records']), 'invalid_rows': len(mapped['issues']),
        'approval_column_present': any('approval' in str(v).casefold() or 'confirmed' in str(v).casefold() for v in headers),
        'missing_approval_records': len(mapped['records']),
        'date_min': min(r['Date Earned'] for r in populated), 'date_max': max(r['Date Earned'] for r in populated)}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
