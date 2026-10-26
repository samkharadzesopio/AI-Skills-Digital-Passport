"""BTU domain publication is the external identity root, not a DB trust boolean."""
import hashlib
import json
from urllib.parse import urlsplit
import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .chain import artifact


def institution_approves_registry(policy):
    url=policy.issuer_identity_url
    parsed=urlsplit(url)
    host=parsed.hostname or ''
    if (parsed.scheme!='https' or not (host=='btu.edu.ge' or host.endswith('.btu.edu.ge'))
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.port not in (None,443) or parsed.path!='/.well-known/btu-passport-issuer.json'):
        return False
    try:
        with requests.get(url,timeout=5,allow_redirects=False,stream=True) as response:
            if response.status_code!=200:
                return False
            raw=bytearray()
            for chunk in response.iter_content(8192):
                raw.extend(chunk)
                if len(raw)>65536:
                    return False
        declaration=json.loads(raw)
        expires=parse_datetime(declaration['expires_at'])
        published=parse_datetime(declaration['published_at'])
        now=timezone.now()
        runtime=hashlib.sha256(bytes.fromhex(artifact()['runtime_bytecode'][2:])).hexdigest()
        return bool(declaration['issuer_reference']=='BTU-UNIVERSITY'
                    and type(declaration['chain_id']) is int and declaration['chain_id']==policy.chain_id
                    and declaration['registry_address'].lower()==policy.contract_address
                    and declaration['runtime_sha256']==runtime
                    and published and expires and timezone.is_aware(published) and timezone.is_aware(expires)
                    and published<=now<expires)
    except Exception:
        return False
