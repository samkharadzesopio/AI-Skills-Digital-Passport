"""Read-only, bounded Google access. All targets are operator-configured."""
import re
import time

from django.conf import settings
import requests

from .mapping import bounded_grid, digest
from .validators import ImportValidationError


class SheetUnavailable(ImportValidationError):
    pass


def read_profile_sheet(profile, *, client=None):
    sources = getattr(settings, 'BTU_SPREADSHEET_GOOGLE_SOURCES', {})
    key = profile.definition.get('google_source')
    configured = sources.get(key) if isinstance(sources, dict) else None
    if not isinstance(configured, dict) or set(configured) != {'spreadsheet_id', 'worksheet'}:
        raise SheetUnavailable('Google source is not configured.')
    sheet_id = configured['spreadsheet_id']
    if not isinstance(sheet_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', sheet_id) or configured['worksheet'] != profile.definition.get('worksheet', 'Completions'):
        raise SheetUnavailable('Google source configuration is invalid.')
    try:
        if client is None:
            import gspread
            path = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', '')
            if not path:
                raise SheetUnavailable('Google service credentials are not configured.')
            client = gspread.service_account(filename=path, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        client.set_timeout((5, 10))
        # Retry only idempotent reads on transient failures, never authorization/configuration.
        for attempt in range(3):
            try:
                worksheet = client.open_by_key(sheet_id).worksheet(configured['worksheet'])
                rows = worksheet.get('A1:Z5011', value_render_option='FORMULA')
                rows = bounded_grid(rows)
                return rows, digest({'target': configured, 'rows': rows})
            except Exception as exc:
                code = getattr(getattr(exc, 'response', None), 'status_code', None)
                transient = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or code in (429, 500, 502, 503, 504)
                if not transient or attempt == 2:
                    raise SheetUnavailable('Google source is unavailable or access is not configured.') from None
                time.sleep(0.1 * 2 ** attempt)
    except ImportValidationError:
        raise
    except Exception:
        raise SheetUnavailable('Google source is unavailable or access is not configured.') from None
