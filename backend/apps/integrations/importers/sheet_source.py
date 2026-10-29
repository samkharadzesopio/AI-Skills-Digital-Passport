"""Read-only, bounded Google access. All targets are operator-configured."""
import random
import time
from contextlib import suppress

from django.conf import settings
import requests
from config.spreadsheet_sources import READ_ONLY_SCOPES, credential_path, validate_target

from .mapping import bounded_grid, digest
from .validators import ImportValidationError


class SheetUnavailable(ImportValidationError):
    pass


def read_profile_sheet(profile, *, client=None):
    sources = getattr(settings, 'BTU_SPREADSHEET_GOOGLE_SOURCES', {})
    key = profile.definition.get('google_source')
    configured = sources.get(key) if isinstance(sources, dict) else None
    try:
        area = validate_target(configured)
    except ValueError:
        raise SheetUnavailable('Google source configuration is invalid.') from None
    if configured['worksheet'] != profile.definition.get('worksheet', 'Completions'):
        raise SheetUnavailable('Google source configuration is invalid.')
    owned_client = client is None
    try:
        if client is None:
            import gspread
            path = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', '')
            if not path:
                raise SheetUnavailable('Google service credentials are not configured.')
            client = gspread.service_account(filename=str(credential_path(path)), scopes=READ_ONLY_SCOPES)
        client.set_timeout((5, 10))
        # Retry only idempotent reads on transient failures, never authorization/configuration.
        for attempt in range(3):
            try:
                worksheet = client.open_by_key(configured['spreadsheet_id']).worksheet(configured['worksheet'])
                rows = worksheet.get(area, value_render_option='FORMULA')
                rows = bounded_grid(rows)
                return rows, digest({'target': configured, 'rows': rows})
            except Exception as exc:
                code = getattr(getattr(exc, 'response', None), 'status_code', None)
                transient = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or code in (429, 500, 502, 503, 504)
                if not transient or attempt == 2:
                    raise SheetUnavailable('Google source is unavailable or access is not configured.') from None
                time.sleep(2 ** attempt + random.uniform(0, 1))
    except ImportValidationError:
        raise
    except Exception:
        raise SheetUnavailable('Google source is unavailable or access is not configured.') from None
    finally:
        if owned_client and client is not None:
            with suppress(Exception):
                client.http_client.session.close()
