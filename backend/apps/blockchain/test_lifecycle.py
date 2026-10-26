import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.credentials.models import Credential, CredentialLifecycleEvent
from apps.credentials.services import issue_credential
from apps.passports.lifecycle import change_legal_name, revoke_passport, PassportLifecycleConflict
from apps.passports.models import DigitalPassport, PassportLifecycleEvent, PassportPublication
from apps.passports.publication import process_publication, process_publications
from apps.passports.services import publish_passport_for_credential_event
from apps.skills.models import VerifiedAchievement, Skill, AchievementSourceEvent
from apps.verification.document_service import DocumentVerificationService
from .tests import ChainDataMixin
from .models import PassportAnchor
from .services import process_anchor, process_batch


class PassportReplacementTests(ChainDataMixin,TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.admin=User.objects.create_admin_user(email='registrar.chain@btu.edu.ge',password='Synthetic-Local-Registrar-2026!',
            permission_codenames={'manage_legal_identity','manage_passport_lifecycle','view_student_records'})
        self.student.email='chain.student@btu.edu.ge'; self.student.save(update_fields=['email'])
        self.user=User.objects.create_user(email=self.student.email,student=self.student,is_email_verified=True)
        self.data=dict(student_id=self.student.pk,expected_passport_reference=self.version.passport.public_reference,
            first_name='ანა',last_name='ახალი',idempotency_key='REGISTRAR-CHANGE-1',evidence_source='BTU_REGISTRAR',
            evidence_reference='REGISTRAR-APPROVAL-0001',reason='Approved synthetic legal name correction')
        # Synthetic registrar/root approval only; all EVM transactions and RPCs are real Anvil.
        authority=patch('apps.blockchain.authority.institution_approves_registry',return_value=True)
        authority.start(); self.addCleanup(authority.stop)

    def replace(self,**changes):
        return change_legal_name(actor=self.admin,**{**self.data,**changes})

    def finish(self,event):
        process_publications(20)
        cancellation=PassportAnchor.objects.get(operation_type='REPLACE',replacement=event.replacement)
        self.assertEqual(self.await_operation(cancellation.pk),'CONFIRMED')
        for job in PassportAnchor.objects.filter(passport=event.replacement,operation_type='ISSUE').order_by('created_at'):
            self.assertEqual(self.await_operation(job.pk),'CONFIRMED')
        event.replacement.refresh_from_db()
        return event.replacement

    def test_complete_replacement_real_pdf_api_public_reference_and_chain(self):
        self.assertEqual(self.process(),'CONFIRMED')
        old_pdf=self.pdf_bytes(); old_id=self.version.passport.public_reference
        event=self.replace()
        old=DigitalPassport.objects.get(pk=self.version.passport_id)
        self.assertEqual(old.status,'REPLACED')
        self.assertNotEqual(event.replacement.public_reference,old_id)
        self.assertNotEqual(event.replacement.latest_version_id,self.version.pk)
        self.student.refresh_from_db(); self.assertEqual(self.student.first_name,'ანა')
        self.assertEqual(Credential.objects.count(),1); self.assertEqual(VerifiedAchievement.objects.count(),1)
        client=APIClient(); client.force_authenticate(self.user)
        current=client.get('/api/student/passport/').json()
        self.assertEqual(current['public_reference'],str(event.replacement.public_reference))
        self.assertEqual(current['status'],'PENDING_BLOCKCHAIN')
        self.assertEqual(client.get(f'/api/student/passport/versions/{self.version.pk}/pdf/download/').status_code,404)
        public=APIClient()
        old_result=public.get(f'/api/verification/passport-version/{self.version.public_reference}/').json()
        self.assertEqual(old_result['status'],'REPLACED')
        self.assertFalse(old_result['is_latest']); self.assertFalse(old_result['blockchain']['blockchain_verified'])
        new=self.finish(event)
        response=client.get('/api/student/passport/pdf/download/')
        self.assertEqual(response.status_code,200)
        new_pdf=b''.join(response.streaming_content); response.close()
        self.assertNotEqual(hashlib.sha256(old_pdf).digest(),hashlib.sha256(new_pdf).digest())
        self.assertEqual(old_pdf,self.pdf_bytes())
        import pymupdf
        with pymupdf.open(stream=new_pdf,filetype='pdf') as doc:
            text=' '.join(p.get_text() for p in doc)
        self.assertIn('ანა',text); self.assertIn('ახალი',text)
        self.assertIn(str(new.public_reference),text)
        self.assertIn(str(new.latest_version.public_reference),text)
        self.assertIn('MACHINE LEARNING FOUNDATIONS',' '.join(text.split()))
        self.assertEqual(client.get('/api/student/passport/').json()['status'],'BLOCKCHAIN_VERIFIED')
        result=public.get(f'/api/verification/passport/{new.public_reference}/').json()
        self.assertEqual(result['status'],'VALID'); self.assertTrue(result['blockchain']['blockchain_verified'])
        uploaded=public.post('/api/verification/document/',{'file':SimpleUploadedFile('new.pdf',new_pdf,content_type='application/pdf')},format='multipart').json()
        self.assertEqual(uploaded['status'],'VALID')
        old_upload=public.post('/api/verification/document/',{'file':SimpleUploadedFile('old.pdf',old_pdf,content_type='application/pdf')},format='multipart').json()
        self.assertEqual(old_upload['status'],'REPLACED')
        self.assertTrue(old_upload['authentic']); self.assertTrue(old_upload['blockchain']['historical_blockchain_authentic'])
        self.assertFalse(old_upload['blockchain']['blockchain_verified'])
        self.assertNotIn('PDF Student',str(old_upload))

    def test_idempotent_request_preserves_one_new_identity_and_audit(self):
        first=self.replace(); replay=self.replace()
        self.assertEqual(first.pk,replay.pk)
        self.assertEqual(DigitalPassport.objects.filter(student=self.student).count(),2)
        self.assertEqual(DigitalPassport.objects.filter(student=self.student,status='ACTIVE').count(),1)
        self.assertEqual(PassportLifecycleEvent.objects.count(),1)
        with self.assertRaises(PassportLifecycleConflict):
            self.replace(first_name='Changed again')

    def test_credential_validation_limit_cannot_be_treated_as_empty_snapshot(self):
        self.assertEqual(self.process(),'CONFIRMED')
        client=APIClient(); client.force_authenticate(self.user)
        with patch('apps.verification.passport_service.MAX_PUBLIC_CREDENTIALS',0):
            private=client.get('/api/student/passport/').json()
            public=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
            uploaded=APIClient().post('/api/verification/document/',{'file':SimpleUploadedFile('bounded.pdf',self.pdf_bytes(),content_type='application/pdf')},format='multipart').json()
        self.assertEqual(private['status'],'UNVERIFIABLE')
        self.assertEqual(public['status'],'UNVERIFIABLE')
        self.assertEqual(uploaded['status'],'UNVERIFIABLE')
        for response in (private,public,uploaded):
            self.assertFalse(response['blockchain']['blockchain_verified'])
            self.assertTrue(response['blockchain']['historical_blockchain_authentic'])

    def test_concurrent_conflicting_administrators_cannot_replace_twice(self):
        barrier=Barrier(2)
        def change(index):
            close_old_connections()
            try:
                actor=User.objects.get(pk=self.admin.pk)
                barrier.wait(timeout=10)
                try:
                    event=change_legal_name(actor=actor,**{**self.data,'idempotency_key':f'CONCURRENT-{index}','first_name':f'Name{index}'})
                    return str(event.pk)
                except PassportLifecycleConflict:
                    return 'CONFLICT'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(change,range(2)))
        self.assertEqual(outcomes.count('CONFLICT'),1)
        self.assertEqual(DigitalPassport.objects.filter(student=self.student,status='ACTIVE').count(),1)
        self.assertEqual(DigitalPassport.objects.filter(student=self.student).count(),2)

    def test_concurrent_duplicate_request_returns_same_replacement(self):
        barrier=Barrier(2)
        def change(_):
            close_old_connections()
            try:
                actor=User.objects.get(pk=self.admin.pk); barrier.wait(timeout=10)
                return change_legal_name(actor=actor,**self.data).replacement_id
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(change,range(2)))
        self.assertEqual(outcomes[0],outcomes[1])
        self.assertEqual(DigitalPassport.objects.filter(student=self.student).count(),2)

    def test_student_and_unpermissioned_admin_and_unapproved_evidence_are_denied(self):
        unprivileged=User.objects.create_admin_user(email='unprivileged.chain@btu.edu.ge',password='Synthetic-Local-2026!',permission_codenames={'view_student_records'})
        for actor in [self.user,unprivileged]:
            with self.assertRaises(PermissionDenied):
                change_legal_name(actor=actor,**self.data)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.replace(evidence_source='SELF_ENTERED')
        self.assertEqual(DigitalPassport.objects.count(),1)

    def test_pdf_failure_and_retry_never_restore_old_passport(self):
        event=self.replace()
        job=PassportPublication.objects.get(version=event.replacement.latest_version)
        with patch('apps.passports.publication.generate_passport_document',side_effect=OSError('private evidence')):
            self.assertEqual(process_publication(job.pk),'PENDING')
        self.assertEqual(DigitalPassport.objects.get(pk=event.previous_id).status,'REPLACED')
        self.assertEqual(process_publication(job.pk),'COMPLETE')
        job.refresh_from_db(); self.assertIsNotNone(job.document_id)

    def test_rpc_failure_leaves_replacement_pending_and_retry_recovers(self):
        self.assertEqual(self.process(),'CONFIRMED')
        event=self.replace(); process_publications(20)
        cancel=PassportAnchor.objects.get(replacement=event.replacement,operation_type='REPLACE')
        with patch('apps.blockchain.chain.ChainGateway.signing_context',side_effect=ConnectionError('RPC secret')):
            self.assertEqual(process_anchor(cancel.pk),'PENDING')
        issue=PassportAnchor.objects.get(document__passport_version=event.replacement.latest_version)
        self.assertEqual(process_anchor(issue.pk),'PENDING')
        public=APIClient().get(f'/api/verification/passport/{event.replacement.public_reference}/').json()
        self.assertEqual(public['status'],'PENDING_BLOCKCHAIN')
        self.finish(event)
        self.assertEqual(APIClient().get(f'/api/verification/passport/{event.replacement.public_reference}/').json()['status'],'VALID')

    def test_old_worker_event_does_not_resurrect_cancelled_identity(self):
        event=self.replace()
        old_pointer=DigitalPassport.objects.get(pk=event.previous_id).latest_version_id
        original=CredentialLifecycleEvent.objects.filter(credential=self.credential,event_type='ISSUED').first()
        publish_passport_for_credential_event(lifecycle_event_id=original.pk)
        old=DigitalPassport.objects.get(pk=event.previous_id)
        self.assertEqual(old.status,'REPLACED'); self.assertEqual(old.latest_version_id,old_pointer)
        self.assertEqual(DigitalPassport.objects.get(student=self.student,status='ACTIVE').pk,event.replacement_id)

    def test_credential_issuance_during_replacement_keeps_all_earned_skills(self):
        event=self.replace()
        skill=Skill.objects.create(skill_code='NAME-CHANGE-ADDITIONAL',skill_name='AI Safety',category='AI',description='Assessed safe AI use.',stamp_type='FOCUSED',badge_asset_id='test')
        source=AchievementSourceEvent.objects.create(source='SYNTHETIC_REGISTRAR',source_event_id='DURING-NAME-CHANGE',payload_sha256='a'*64)
        achievement=VerifiedAchievement.objects.create(student=self.student,skill=skill,source_event=source,earned_on='2026-10-20',verification_status='VERIFIED')
        issue_credential(issuer_reference=self.issuer.reference,idempotency_key='DURING-NAME-CHANGE',achievement_ids=[achievement.pk])
        current=DigitalPassport.objects.get(student=self.student,status='ACTIVE')
        self.assertEqual(current.pk,event.replacement_id)
        self.assertEqual(set(current.latest_version.skill_snapshots.values_list('skill_code',flat=True)),{self.skill.skill_code,skill.skill_code})
        self.finish(event)
        current.refresh_from_db()
        self.assertEqual(current.latest_version.student_snapshot['first_name'],'ანა')

    def test_revocation_invalidates_public_status_and_preserves_chain_history(self):
        self.assertEqual(self.process(),'CONFIRMED')
        event=revoke_passport(actor=self.admin,passport_reference=self.version.passport.public_reference,idempotency_key='REVOKE-1',reason='Synthetic institutional invalidation')
        operation=PassportAnchor.objects.get(operation_type='REVOKE',passport=event.previous)
        self.assertEqual(self.await_operation(operation.pk),'CONFIRMED')
        result=APIClient().get(f'/api/verification/passport/{event.previous.public_reference}/').json()
        self.assertEqual(result['status'],'REVOKED')
        self.assertFalse(result['blockchain']['blockchain_verified'])
        client=APIClient(); client.force_authenticate(self.user)
        self.assertEqual(client.get('/api/student/passport/').json(),{'passport':None})
        with self.assertRaises(Exception):
            publish_passport_for_credential_event(lifecycle_event_id=CredentialLifecycleEvent.objects.filter(credential=self.credential).first().pk)
        self.assertEqual(DigitalPassport.objects.count(),1)

    def test_raw_identity_reactivation_and_audit_rewrite_are_blocked(self):
        event=self.replace()
        for changes in [{'status':'ACTIVE','cancelled_at':None},{'legal_name_snapshot':{'first_name':'Forged'}},{'first_issued_at':None}]:
            with self.assertRaises(IntegrityError),transaction.atomic():
                DigitalPassport.objects.filter(pk=event.previous_id).update(**changes)
        with self.assertRaises(IntegrityError),transaction.atomic():
            PassportLifecycleEvent.objects.filter(pk=event.pk).update(reason='Rewritten')
        from importlib import import_module
        from django.apps import apps
        with self.assertRaises(RuntimeError):
            import_module('apps.passports.migrations.0008_lifecycle_integrity').safe_reverse(apps,None)

    def test_real_admin_session_csrf_and_current_student_contract(self):
        client=APIClient(enforce_csrf_checks=True)
        url=f'/api/admin/students/{self.student.pk}/legal-name-change/'
        body={key:str(value) if key in ('expected_passport_reference',) else value for key,value in self.data.items() if key!='student_id'}
        self.assertIn(client.post(url,body,format='json').status_code,[401,403])
        csrf=client.get('/api/accounts/csrf/').json()['csrfToken']
        login=client.post('/api/accounts/login/',{'email':self.admin.email,'password':'Synthetic-Local-Registrar-2026!'},format='json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(login.status_code,200)
        self.assertEqual(client.post(url,body,format='json').status_code,403)
        csrf=client.get('/api/accounts/csrf/').json()['csrfToken']
        result=client.post(url,body,format='json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.json()['passport']['status'],'PENDING_BLOCKCHAIN')

    def test_chain_calldata_contains_only_opaque_keys_not_personal_identifiers(self):
        self.assertEqual(self.process(),'CONFIRMED')
        event=self.replace(); self.finish(event)
        for operation in PassportAnchor.objects.all():
            data=bytes.fromhex(self.gateway.calldata(operation)[2:])
            for raw in [self.student.pk.bytes,self.version.passport.public_reference.bytes,self.document.public_reference.bytes,
                        self.student.email.encode(),self.student.external_student_id.encode(),b'PDF Student','ანა'.encode()]:
                self.assertNotIn(raw,data)
        self.assertEqual(self.gateway.contract.functions.passportState(bytes.fromhex(self.anchor.passport_key)).call(),2)

    def test_history_and_old_pdf_are_permissioned_and_audited(self):
        event=self.replace()
        url=f'/api/admin/students/{self.student.pk}/passport-lifecycle/'
        client=APIClient(); client.force_authenticate(self.user)
        self.assertEqual(client.get(url).status_code,403)
        client.force_authenticate(self.admin)
        history=client.get(url)
        self.assertEqual(history.status_code,200)
        self.assertEqual(history.json()['results'][0]['previous_reference'],str(event.previous.public_reference))
        self.assertNotIn('legal_names',history.json()['results'][0])
        old_pdf=client.get(f'/api/admin/passports/{event.previous_id}/pdf/download/')
        self.assertEqual(old_pdf.status_code,200)
        self.assertEqual(b''.join(old_pdf.streaming_content),self.pdf_bytes()); old_pdf.close()
        from apps.accounts.models import SecurityAudit
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin,action='PassportLifecycleHistoryView:GET',status_code=200).exists())

    def test_inflight_public_verification_rechecks_institutional_cancellation(self):
        self.assertEqual(self.process(),'CONFIRMED')
        changed=[]
        def approved_after_correction(policy):
            if not changed:
                changed.append(self.replace())
            return True
        with patch('apps.blockchain.authority.institution_approves_registry',side_effect=approved_after_correction):
            result=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
        self.assertEqual(result['status'],'REPLACED')
        self.assertFalse(result['blockchain']['blockchain_verified'])
        self.assertTrue(result['blockchain']['historical_blockchain_authentic'])

    def test_inflight_current_view_reloads_new_identity_after_correction(self):
        self.assertEqual(self.process(),'CONFIRMED')
        changed=[]
        def approved_after_correction(policy):
            if not changed:
                changed.append(self.replace())
            return True
        client=APIClient(); client.force_authenticate(self.user)
        with patch('apps.blockchain.authority.institution_approves_registry',side_effect=approved_after_correction):
            result=client.get('/api/student/passport/').json()
        self.assertEqual(result['public_reference'],str(changed[0].replacement.public_reference))
        self.assertEqual(result['status'],'PENDING_BLOCKCHAIN')

    @patch('apps.api.pdf_views.open_passport_document_for_student')
    def test_inflight_old_pdf_download_is_denied_after_identity_cancellation(self,opened):
        from apps.passports.document_services import open_passport_document_for_student
        streams=[]
        def open_then_correct(**kwargs):
            document,stream=open_passport_document_for_student(**kwargs)
            streams.append(stream); self.replace()
            return document,stream
        opened.side_effect=open_then_correct
        client=APIClient(); client.force_authenticate(self.user)
        response=client.get('/api/student/passport/pdf/download/')
        self.assertEqual(response.status_code,404)
        self.assertTrue(streams[0].closed)

    def test_cancellation_during_rpc_quote_prevents_a_new_old_identity_signature(self):
        original=self.gateway.signing_context
        def quote_then_cancel():
            quote=original(); self.replace(); return quote
        with patch.object(self.gateway,'signing_context',side_effect=quote_then_cancel):
            self.assertEqual(self.process(),'FAILED')
        self.anchor.refresh_from_db()
        self.assertIsNone(self.anchor.signed_transaction)
        self.assertEqual(self.anchor.error_code,'CANCELLED_BEFORE_ANCHORING')

    def test_registrar_can_replace_after_authoritative_student_name_was_updated(self):
        self.student.first_name,self.student.last_name=self.data['first_name'],self.data['last_name']
        self.student.save(update_fields=['first_name','last_name'])
        event=self.replace()
        self.assertNotEqual(event.previous.public_reference,event.replacement.public_reference)
        self.assertEqual(event.legal_names['previous'],{'first_name':'PDF','last_name':'Student'})

    @override_settings(BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY')
    def test_trusted_completion_automatically_publishes_pdf_and_real_chain_proof(self):
        from apps.integrations.classroom_automation import receive,process_event
        for code in ['AI_LITERACY','AI_FUNDAMENTALS']:
            Skill.objects.create(skill_code=code,skill_name=code.replace('_',' ').title(),category='AI',
                description='Assessed introductory AI competency.',stamp_type='FOCUSED',badge_asset_id='test')
        event=receive({'source':'BTU_CLASSROOM','event_id':'ANVIL-CLASSROOM-COMPLETION-1',
            'student_id':self.student.external_student_id,'course_id':'AI-101',
            'completion_status':'completed','passed':True,'grade':90,'completion_date':'2026-10-20'})
        from apps.integrations.models import ClassroomSyncEvent
        self.assertEqual(process_event(event),'issued',ClassroomSyncEvent.objects.get(pk=event).error_code)
        self.assertEqual(process_event(event),'skipped')
        current=DigitalPassport.objects.get(student=self.student,status='ACTIVE')
        self.assertEqual(current.public_reference,self.version.passport.public_reference)
        self.assertNotEqual(current.latest_version_id,self.version.pk)
        process_publications(20)
        for operation in PassportAnchor.objects.filter(passport=current,operation_type='ISSUE').order_by('created_at'):
            self.assertEqual(self.await_operation(operation.pk),'CONFIRMED')
        client=APIClient(); client.force_authenticate(self.user)
        metadata=client.get('/api/student/passport/').json()
        self.assertEqual(metadata['status'],'BLOCKCHAIN_VERIFIED')
        self.assertEqual(Credential.objects.count(),2)
        pdf=client.get('/api/student/passport/pdf/download/')
        content=b''.join(pdf.streaming_content); pdf.close()
        result=APIClient().post('/api/verification/document/',{'file':SimpleUploadedFile('passport.pdf',content,content_type='application/pdf')},format='multipart').json()
        self.assertEqual(result['status'],'VALID')
        self.assertTrue(result['blockchain']['blockchain_verified'])

    def test_approved_correction_is_not_undone_by_missing_chain_configuration(self):
        with override_settings(PASSPORT_BLOCKCHAIN_ENABLED=False):
            event=self.replace()
            self.assertEqual(DigitalPassport.objects.get(pk=event.previous_id).status,'REPLACED')
            self.assertFalse(PassportAnchor.objects.filter(replacement=event.replacement).exists())
            client=APIClient(); client.force_authenticate(self.user)
            self.assertEqual(client.get('/api/student/passport/').json()['status'],'PENDING_BLOCKCHAIN')
            old=APIClient().get(f'/api/verification/passport/{event.previous.public_reference}/').json()
            self.assertEqual(old['status'],'REPLACED')
            process_publications(20)
        process_batch(batch_size=20)
        self.assertTrue(PassportAnchor.objects.filter(operation_type='REPLACE',replacement=event.replacement).exists())
        self.finish(event)
        self.assertEqual(APIClient().get(f'/api/verification/passport/{event.replacement.public_reference}/').json()['status'],'VALID')

    @override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor,credential:'synthetic-registrar')
    def test_pending_credential_refresh_cannot_leave_a_current_verification_badge(self):
        from apps.credentials.services import revoke_credential
        self.assertEqual(self.process(),'CONFIRMED')
        with patch('apps.credentials.passport_refresh.process_passport_refresh_event',return_value=None):
            revoke_credential(public_reference=self.credential.public_reference,actor=None,reason='Synthetic pending refresh')
        current=DigitalPassport.objects.get(student=self.student,status='ACTIVE')
        self.assertEqual(current.latest_version_id,self.version.pk)
        client=APIClient(); client.force_authenticate(self.user)
        private=client.get('/api/student/passport/').json()
        self.assertEqual(private['status'],'REVOKED')
        self.assertFalse(private['blockchain']['blockchain_verified'])
        public=APIClient().get(f'/api/verification/passport/{current.public_reference}/').json()
        self.assertEqual(public['status'],'REVOKED')
        self.assertFalse(public['blockchain']['blockchain_verified'])
        self.assertTrue(public['blockchain']['historical_blockchain_authentic'])
