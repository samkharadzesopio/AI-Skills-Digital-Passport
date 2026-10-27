"""SHA-256 commitments scoped to chain and registry; no raw identifiers on-chain."""
import hashlib

DOMAIN = b'BTU_PASSPORT_POLYGON_V1\x00'


def namespace(policy):
    return DOMAIN + policy.chain_id.to_bytes(32,'big') + bytes.fromhex(policy.contract_address[2:])


def passport_key(passport, policy):
    return hashlib.sha256(namespace(policy)+b'PASSPORT\x00'+passport.public_reference.bytes+bytes(passport.chain_salt)).hexdigest()


def document_material(document, policy, salt):
    p = passport_key(document.passport_version.passport,policy)
    v = hashlib.sha256(namespace(policy)+b'VERSION\x00'+bytes.fromhex(p)+document.passport_version.public_reference.bytes).hexdigest()
    d = hashlib.sha256(namespace(policy)+b'DOCUMENT\x00'+bytes.fromhex(v)+document.public_reference.bytes+bytes.fromhex(salt)).hexdigest()
    snapshot=document.passport_version.content_sha256
    digest = pdf_commitment(policy,p,v,d,document.pdf_sha256,snapshot,salt)
    return {'passport_key':p,'version_key':v,'document_key':d,'commitment':digest,'commitment_salt':salt,'snapshot_sha256':snapshot}


def pdf_commitment(policy,p,v,d,pdf_sha256,snapshot_sha256,salt):
    return hashlib.sha256(namespace(policy)+b'PDF\x00'+b''.join(bytes.fromhex(value) for value in (p,v,d,pdf_sha256,snapshot_sha256,salt))).hexdigest()
