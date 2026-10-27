import secrets
from django.db import migrations
from django.db.models import Count


def preserve_identity(apps,schema_editor):
    Passport=apps.get_model('passports','DigitalPassport')
    Version=apps.get_model('passports','PassportVersion')
    for passport in Passport.objects.select_related('student').iterator(chunk_size=500):
        first=Version.objects.filter(passport_id=passport.pk,status='ISSUED').order_by('version_number').first()
        data=first.student_snapshot if first else {'first_name':passport.student.first_name,'last_name':passport.student.last_name}
        Passport.objects.filter(pk=passport.pk).update(legal_name_snapshot={key:data.get(key,'') for key in ('first_name','last_name')},
            first_issued_at=first.issued_at if first else None,chain_salt=secrets.token_bytes(32))


def safe_reverse(apps,schema_editor):
    Passport=apps.get_model('passports','DigitalPassport')
    if Passport.objects.exclude(status='ACTIVE').exists() or Passport.objects.values('student_id').annotate(total=Count('pk')).filter(total__gt=1).exists():
        raise RuntimeError('Cannot restore one-to-one Passport schema while cancelled historical identities exist.')


FORWARD=r"""
CREATE FUNCTION passport_lifecycle_permission(actor uuid, code text) RETURNS boolean LANGUAGE sql STABLE AS $$
SELECT EXISTS (
 SELECT 1 FROM accounts_user u WHERE u.id=actor AND u.role='ADMIN'
 AND u.is_staff AND NOT u.is_superuser AND u.is_active AND u.is_email_verified
 AND (EXISTS (SELECT 1 FROM accounts_user_user_permissions up JOIN auth_permission p ON p.id=up.permission_id
              JOIN django_content_type ct ON ct.id=p.content_type_id
              WHERE up.user_id=u.id AND ct.app_label='accounts' AND p.codename=code)
      OR EXISTS (SELECT 1 FROM accounts_user_groups ug JOIN auth_group_permissions gp ON gp.group_id=ug.group_id
                 JOIN auth_permission p ON p.id=gp.permission_id JOIN django_content_type ct ON ct.id=p.content_type_id
                 WHERE ug.user_id=u.id AND ct.app_label='accounts' AND p.codename=code)))
$$;

CREATE FUNCTION passport_lifecycle_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor uuid; prior_student uuid; prior_status text; permission text;
BEGIN
  actor=nullif(current_setting('app.passport_lifecycle_actor',true),'')::uuid;
  IF TG_OP='INSERT' AND NEW.replaces_id IS NOT NULL THEN
    SELECT student_id,status INTO prior_student,prior_status FROM digital_passports WHERE id=NEW.replaces_id;
    IF prior_student IS DISTINCT FROM NEW.student_id OR prior_status IS DISTINCT FROM 'REPLACED'
       OR NOT passport_lifecycle_permission(actor,'manage_legal_identity') THEN
      RAISE EXCEPTION 'replacement requires approved same-student identity correction' USING ERRCODE='23514';
    END IF;
  END IF;
  IF TG_OP='UPDATE' THEN
    IF NEW.chain_salt IS DISTINCT FROM OLD.chain_salt OR NEW.replaces_id IS DISTINCT FROM OLD.replaces_id
       OR (OLD.legal_name_snapshot<>'{}'::jsonb AND NEW.legal_name_snapshot<>OLD.legal_name_snapshot)
       OR (OLD.first_issued_at IS NOT NULL AND NEW.first_issued_at IS DISTINCT FROM OLD.first_issued_at) THEN
      RAISE EXCEPTION 'permanent Passport identity facts are immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status<>'ACTIVE' AND (NEW.status<>OLD.status OR NEW.latest_version_id IS DISTINCT FROM OLD.latest_version_id
        OR NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at) THEN
      RAISE EXCEPTION 'cancelled Passport cannot become current again' USING ERRCODE='23514';
    END IF;
    IF NEW.status<>OLD.status THEN
      permission=CASE WHEN NEW.status='REPLACED' THEN 'manage_legal_identity' ELSE 'manage_passport_lifecycle' END;
      IF NOT passport_lifecycle_permission(actor,permission) THEN
        RAISE EXCEPTION 'explicit institutional lifecycle permission required' USING ERRCODE='23514';
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER passport_lifecycle_guard_trg BEFORE INSERT OR UPDATE ON digital_passports
FOR EACH ROW EXECUTE FUNCTION passport_lifecycle_guard();

CREATE FUNCTION passport_lifecycle_event_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous_student uuid; next_student uuid; previous_status text; permission text;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'identity correction audit is immutable' USING ERRCODE='23514'; END IF;
 SELECT student_id,status INTO previous_student,previous_status FROM digital_passports WHERE id=NEW.previous_id;
 permission=CASE WHEN NEW.event_type='NAME_CHANGE' THEN 'manage_legal_identity' ELSE 'manage_passport_lifecycle' END;
 IF previous_student IS DISTINCT FROM NEW.student_id OR NOT passport_lifecycle_permission(NEW.approved_by_id,permission) THEN
   RAISE EXCEPTION 'invalid institutional identity approval' USING ERRCODE='23514';
 END IF;
 IF NEW.event_type='NAME_CHANGE' THEN
   SELECT student_id INTO next_student FROM digital_passports WHERE id=NEW.replacement_id AND replaces_id=NEW.previous_id;
   IF next_student IS DISTINCT FROM NEW.student_id OR previous_status<>'REPLACED' THEN
     RAISE EXCEPTION 'invalid replacement audit linkage' USING ERRCODE='23514';
   END IF;
 ELSIF NEW.event_type<>'REVOCATION' OR NEW.replacement_id IS NOT NULL OR previous_status<>'REVOKED' THEN
   RAISE EXCEPTION 'invalid Passport cancellation event' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER passport_lifecycle_event_guard_trg BEFORE INSERT OR UPDATE OR DELETE ON passport_lifecycle_events
FOR EACH ROW EXECUTE FUNCTION passport_lifecycle_event_guard();
"""

REVERSE=r"""
DROP TRIGGER IF EXISTS passport_lifecycle_event_guard_trg ON passport_lifecycle_events;
DROP FUNCTION IF EXISTS passport_lifecycle_event_guard();
DROP TRIGGER IF EXISTS passport_lifecycle_guard_trg ON digital_passports;
DROP FUNCTION IF EXISTS passport_lifecycle_guard();
DROP FUNCTION IF EXISTS passport_lifecycle_permission(uuid,text);
"""


class Migration(migrations.Migration):
    dependencies=[('passports','0007_passportlifecycleevent_passportpublication_and_more'),('accounts','0007_alter_user_options')]
    operations=[migrations.RunPython(preserve_identity,safe_reverse),migrations.RunSQL(FORWARD,REVERSE)]
