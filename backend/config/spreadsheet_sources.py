"""Pure server-side Google target validation; never opens credentials or a network."""
from pathlib import Path
import re

DEFAULT_RANGE = 'A1:Z5011'
READ_ONLY_SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def validate_target(target):
    if (not isinstance(target, dict)
            or not {'spreadsheet_id', 'worksheet'}.issubset(target)
            or set(target) - {'spreadsheet_id', 'worksheet', 'range'}):
        raise ValueError('Invalid Google target.')
    if (not isinstance(target['spreadsheet_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', target['spreadsheet_id'])
            or not isinstance(target['worksheet'], str)
            or not target['worksheet'].strip() or len(target['worksheet']) > 100):
        raise ValueError('Invalid Google target.')
    area = target.get('range', DEFAULT_RANGE)
    match = re.fullmatch(r'A1:([A-Z])([1-9][0-9]{0,3})', area) if isinstance(area, str) else None
    if not match or int(match[2]) > 5011:
        # Starting at A1 preserves the original source row numbers in previews.
        # No named ranges, whole columns, worksheet overrides or external URLs.
        raise ValueError('Use a bounded A1 range within A1:Z5011.')
    return area


def validate_sources(sources):
    if not isinstance(sources, dict) or len(sources) > 100:
        raise ValueError('Invalid Google sources.')
    for key, target in sources.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key):
            raise ValueError('Invalid Google source key.')
        validate_target(target)
    return sources


def credential_path(value):
    """Require an existing absolute secret file outside every Git checkout."""
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ValueError('Configure an absolute credential path outside Git.')
    path = Path(value).resolve(strict=True)
    parents = (*Path(value).parents, *path.parents)
    if not path.is_file() or any((parent / '.git').exists() for parent in parents):
        raise ValueError('Configure an absolute credential path outside Git.')
    return path
