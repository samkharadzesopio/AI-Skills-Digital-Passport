// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {AccessControlDefaultAdminRules} from "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";

/// @notice Opaque, domain-separated commitments; no student identities or PDF data.
contract PassportRegistry is AccessControlDefaultAdminRules {
    bytes32 public constant ISSUER_ROLE = keccak256("BTU_PASSPORT_ISSUER");
    enum State { UNKNOWN, ACTIVE, REPLACED, REVOKED }
    struct Commitment { bytes32 passportKey; bytes32 versionKey; bytes32 digest; address issuer; }
    mapping(bytes32 => Commitment) public commitments;
    mapping(bytes32 => State) public passportState;

    event PassportAnchored(bytes32 indexed documentKey, bytes32 indexed passportKey, bytes32 indexed versionKey, bytes32 digest, address issuer);
    event PassportReplaced(bytes32 indexed previousKey, bytes32 indexed replacementKey);
    event PassportRevoked(bytes32 indexed passportKey);
    error InvalidCommitment();
    error InactivePassport();
    error DocumentAlreadyAnchored();

    constructor(address admin, address issuer) AccessControlDefaultAdminRules(1 days, admin) {
        if (issuer == address(0)) revert InvalidCommitment();
        _grantRole(ISSUER_ROLE, issuer);
    }

    function anchorPassport(bytes32 passportKey, bytes32 versionKey, bytes32 documentKey, bytes32 digest) external onlyRole(ISSUER_ROLE) {
        _anchor(passportKey, versionKey, documentKey, digest);
    }

    function replacePassport(bytes32 previousKey, bytes32 passportKey) external onlyRole(ISSUER_ROLE) {
        if (previousKey == bytes32(0) || previousKey == passportKey) revert InvalidCommitment();
        if (passportState[previousKey] == State.REPLACED || passportState[previousKey] == State.REVOKED
            || passportState[passportKey] != State.UNKNOWN) revert InactivePassport();
        // A tombstone also prevents a delayed issuance from activating the old key.
        passportState[previousKey] = State.REPLACED;
        emit PassportReplaced(previousKey, passportKey);
    }

    function revokePassport(bytes32 passportKey) external onlyRole(ISSUER_ROLE) {
        if (passportKey == bytes32(0)) revert InvalidCommitment();
        if (passportState[passportKey] == State.REPLACED || passportState[passportKey] == State.REVOKED) revert InactivePassport();
        passportState[passportKey] = State.REVOKED;
        emit PassportRevoked(passportKey);
    }

    function _anchor(bytes32 passportKey, bytes32 versionKey, bytes32 documentKey, bytes32 digest) private {
        if (passportKey == bytes32(0) || versionKey == bytes32(0) || documentKey == bytes32(0) || digest == bytes32(0)) revert InvalidCommitment();
        if (passportState[passportKey] == State.REPLACED || passportState[passportKey] == State.REVOKED) revert InactivePassport();
        if (commitments[documentKey].digest != bytes32(0)) revert DocumentAlreadyAnchored();
        passportState[passportKey] = State.ACTIVE;
        commitments[documentKey] = Commitment(passportKey, versionKey, digest, msg.sender);
        emit PassportAnchored(documentKey, passportKey, versionKey, digest, msg.sender);
    }
}
