"""Test-only, ephemeral Anvil process with fresh unfunded-on-public-networks keys."""
import os
import platform
from pathlib import Path
import shutil
import socket
import subprocess
import time
from eth_account import Account
from web3 import Web3


class AnvilChain:
    def __init__(self):
        root=Path(__file__).resolve().parents[3]
        target={'Linux':'linux','Darwin':'darwin','Windows':'win32'}[platform.system()]
        arch='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'amd64'
        executable='anvil.exe' if os.name=='nt' else 'anvil'
        candidates=[os.environ.get('PASSPORT_ANVIL_BIN',''),
                    str(root/f'blockchain/node_modules/@foundry-rs/anvil-{target}-{arch}/bin/{executable}'),
                    shutil.which('anvil') or '']
        binary=next((value for value in candidates if value and Path(value).is_file()),None)
        if binary is None:
            raise RuntimeError('Anvil is required. Install the pinned blockchain npm dependencies or set PASSPORT_ANVIL_BIN.')
        Account.enable_unaudited_hdwallet_features()
        self.signer,mnemonic=Account.create_with_mnemonic()
        self.other_signer=Account.from_mnemonic(mnemonic,account_path="m/44'/60'/0'/0/2")
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        self.rpc_url=f'http://127.0.0.1:{port}'
        self.process=subprocess.Popen([binary,'--host','127.0.0.1','--port',str(port),'--chain-id','31337',
                                       '--mnemonic',mnemonic,'--silent'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                      **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        self.web3=Web3(Web3.HTTPProvider(self.rpc_url,request_kwargs={'timeout':2},exception_retry_configuration=None))
        for _ in range(100):
            try:
                if self.web3.eth.chain_id==31337:
                    return
            except Exception:
                pass
            time.sleep(.1)
        self.close()
        raise RuntimeError('The isolated Anvil process did not start.')

    def rpc(self,method,params=None):
        result=self.web3.provider.make_request(method,params or [])
        if 'error' in result:
            raise RuntimeError('Local Anvil test control failed.')
        return result['result']

    def mine_blocks(self,total):
        for _ in range(total):
            self.rpc('evm_mine')

    def take_snapshot(self):
        return self.rpc('evm_snapshot')

    def revert_to_snapshot(self,snapshot):
        return self.rpc('evm_revert',[snapshot])

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait()
