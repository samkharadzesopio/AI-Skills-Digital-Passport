// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;
import {PassportRegistry} from "../contracts/PassportRegistry.sol";

interface Vm {
    function prank(address) external;
    function expectRevert() external;
    function warp(uint256) external;
}

contract PassportRegistryTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    PassportRegistry registry;
    address issuer = address(0xB7);
    bytes32 p = keccak256("opaque-old");
    bytes32 replacement = keccak256("opaque-new");
    bytes32 v = keccak256("opaque-version");
    bytes32 d = keccak256("opaque-document");
    bytes32 h = sha256("domain separated salted pdf hash");

    function setUp() public { registry = new PassportRegistry(address(this), issuer); }
    function issue() private { vm.prank(issuer); registry.anchorPassport(p,v,d,h); }
    function testAuthorizedIssueStoresExactCommitment() public {
        issue();
        (bytes32 actualP, bytes32 actualV, bytes32 actualH, address actualIssuer) = registry.commitments(d);
        require(actualP == p && actualV == v && actualH == h && actualIssuer == issuer);
        require(registry.passportState(p) == PassportRegistry.State.ACTIVE);
    }
    function testUnauthorizedIssuance() public { vm.expectRevert(); registry.anchorPassport(p,v,d,h); }
    function testUnauthorizedRevocation() public { issue(); vm.expectRevert(); registry.revokePassport(p); }
    function testUnauthorizedReplacement() public { issue(); vm.expectRevert(); registry.replacePassport(p,replacement); }
    function testDuplicateCannotOverwrite() public { issue(); bytes32 changed=sha256("changed"); vm.prank(issuer); vm.expectRevert(); registry.anchorPassport(p,v,d,changed); }
    function testReplacementCancellationThenNewIssuance() public {
        issue(); vm.prank(issuer); registry.replacePassport(p,replacement);
        vm.prank(issuer); registry.anchorPassport(replacement,v,keccak256("d2"),h);
        require(registry.passportState(p) == PassportRegistry.State.REPLACED);
        require(registry.passportState(replacement) == PassportRegistry.State.ACTIVE);
        (,,bytes32 historic,) = registry.commitments(d); require(historic == h);
    }
    function testDelayedOldIssueCannotResurrectReplacement() public {
        vm.prank(issuer); registry.replacePassport(p,replacement);
        vm.prank(issuer); vm.expectRevert(); registry.anchorPassport(p,v,keccak256("late"),h);
    }
    function testZeroReplacementRejectedWithoutCancellingCurrentPassport() public {
        issue();
        vm.prank(issuer); vm.expectRevert(); registry.replacePassport(p,bytes32(0));
        require(registry.passportState(p) == PassportRegistry.State.ACTIVE);
        (,,bytes32 historic,) = registry.commitments(d); require(historic == h);
    }
    function testRevocationIsTerminalAndKeepsCommitment() public {
        issue(); vm.prank(issuer); registry.revokePassport(p);
        require(registry.passportState(p) == PassportRegistry.State.REVOKED);
        vm.prank(issuer); vm.expectRevert(); registry.anchorPassport(p,v,keccak256("late"),h);
    }
    function testIssuerRotationBlocksOldKeyAndAllowsNewKey() public {
        issue(); address next = address(0xB8);
        registry.grantRole(registry.ISSUER_ROLE(),next);
        registry.revokeRole(registry.ISSUER_ROLE(),issuer);
        vm.prank(issuer); vm.expectRevert(); registry.anchorPassport(p,v,keccak256("d2"),h);
        vm.prank(next); registry.anchorPassport(p,v,keccak256("d2"),h);
        (,,,address historicalIssuer) = registry.commitments(d); require(historicalIssuer == issuer);
    }
    function testAdministrativeRotationRequiresDelayAndAcceptance() public {
        address next = address(0xAD);
        registry.beginDefaultAdminTransfer(next);
        vm.prank(next); vm.expectRevert(); registry.acceptDefaultAdminTransfer();
        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(next); registry.acceptDefaultAdminTransfer();
        require(registry.defaultAdmin() == next);
        bytes32 role=registry.ISSUER_ROLE();
        vm.expectRevert(); registry.grantRole(role,address(0xB9));
    }
    function testZeroCommitmentRejected() public { vm.prank(issuer); vm.expectRevert(); registry.anchorPassport(p,v,d,bytes32(0)); }
}
