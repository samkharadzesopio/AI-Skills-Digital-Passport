// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;
import {PassportRegistry} from "../contracts/PassportRegistry.sol";
interface DeployVm {
    function envAddress(string calldata) external returns(address);
    function startBroadcast() external;
    function stopBroadcast() external;
}
/// @notice Foundry simulation by default. --broadcast requires explicit operator approval.
contract Deploy {
    DeployVm constant vm=DeployVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    function run() external returns(PassportRegistry registry) {
        require(block.chainid==80002 || block.chainid==31337,"Only Polygon Amoy or local Anvil");
        address admin=vm.envAddress("BTU_REGISTRY_ADMIN");
        address issuer=vm.envAddress("BTU_REGISTRY_ISSUER");
        require(admin!=address(0) && issuer!=address(0),"Explicit issuer and admin required");
        vm.startBroadcast();
        registry=new PassportRegistry(admin,issuer);
        vm.stopBroadcast();
    }
}
