import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from django.utils import timezone
from .authority import institution_approves_registry
from .chain import artifact
from .policy import ChainPolicy


class UniversityAuthorityTests(SimpleTestCase):
    def setUp(self):
        self.policy=ChainPolicy('https://rpc.invalid',80002,'0x'+'1'*40,'0x'+'2'*40,
            issuer_identity_url='https://passport.btu.edu.ge/.well-known/btu-passport-issuer.json')
        self.declaration={'issuer_reference':'BTU-UNIVERSITY','chain_id':80002,'registry_address':self.policy.contract_address,
            'runtime_sha256':hashlib.sha256(bytes.fromhex(artifact()['runtime_bytecode'][2:])).hexdigest(),
            'published_at':(timezone.now()-timedelta(minutes=1)).isoformat(),
            'expires_at':(timezone.now()+timedelta(days=1)).isoformat()}

    def response(self,body,status=200):
        response=Mock(status_code=status)
        response.iter_content.return_value=[body]
        context=Mock(); context.__enter__=Mock(return_value=response); context.__exit__=Mock(return_value=False)
        return context

    def test_synthetic_https_declaration_matches_expected_chain_registry_and_code(self):
        # Transport fixture only; no claim of access to a real BTU domain.
        with patch('apps.blockchain.authority.requests.get',return_value=self.response(json.dumps(self.declaration).encode())) as get:
            self.assertTrue(institution_approves_registry(self.policy))
        get.assert_called_once_with(self.policy.issuer_identity_url,timeout=5,allow_redirects=False,stream=True)

    def test_wrong_chain_registry_runtime_and_expired_declarations_fail_closed(self):
        for changes in [{'chain_id':137},{'registry_address':'0x'+'3'*40},{'runtime_sha256':'a'*64},
                        {'expires_at':(timezone.now()-timedelta(days=1)).isoformat()},
                        {'issuer_reference':'OTHER'},{'chain_id':'80002'}]:
            body=json.dumps({**self.declaration,**changes}).encode()
            with patch('apps.blockchain.authority.requests.get',return_value=self.response(body)):
                self.assertFalse(institution_approves_registry(self.policy))

    def test_external_http_or_redirected_authority_is_rejected(self):
        for url in ['https://btu.edu.ge.evil.invalid/.well-known/btu-passport-issuer.json',
                    'http://btu.edu.ge/.well-known/btu-passport-issuer.json','https://btu.edu.ge/other',
                    'https://user:password@btu.edu.ge/.well-known/btu-passport-issuer.json']:
            with patch('apps.blockchain.authority.requests.get',side_effect=AssertionError('Unapproved destination')):
                self.assertFalse(institution_approves_registry(replace(self.policy,issuer_identity_url=url)))
        with patch('apps.blockchain.authority.requests.get',return_value=self.response(b'',302)):
            self.assertFalse(institution_approves_registry(self.policy))

    def test_outages_bad_json_and_oversized_authority_never_establish_identity(self):
        with patch('apps.blockchain.authority.requests.get',side_effect=ConnectionError('private provider text')):
            self.assertFalse(institution_approves_registry(self.policy))
        for body in [b'invalid',b'x'*65537,b'{}']:
            with patch('apps.blockchain.authority.requests.get',return_value=self.response(body)):
                self.assertFalse(institution_approves_registry(self.policy))
