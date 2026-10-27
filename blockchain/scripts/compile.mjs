import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const platform={linux:'linux',darwin:'darwin',win32:'win32'}[process.platform];
const arch={x64:'amd64',arm64:'arm64'}[process.arch];
const local=path.join(root,`node_modules/@foundry-rs/forge-${platform}-${arch}/bin/forge${process.platform==='win32'?'.exe':''}`);
const forge=process.env.PASSPORT_FORGE_BIN || (fs.existsSync(local)?local:'forge');
const args=['build','--force'];
if (process.env.SOLC_PATH) args.push('--use',process.env.SOLC_PATH);
const built=spawnSync(forge,args,{cwd:root,stdio:'inherit'});
if (built.error || built.status!==0) process.exit(built.status || 1);
const a=JSON.parse(fs.readFileSync(path.join(root,'out/PassportRegistry.sol/PassportRegistry.json'),'utf8'));
if (!a.metadata.compiler.version.startsWith('0.8.30+')) throw new Error('Unexpected Solidity compiler');
const output=JSON.stringify({compiler:a.metadata.compiler.version,contract:'PassportRegistry',evmVersion:'cancun',
  abi:a.abi,bytecode:a.bytecode.object,runtime_bytecode:a.deployedBytecode.object},null,2)+'\n';
const destination=path.join(root,'../backend/apps/blockchain/contract.json');
if (process.argv.includes('--check')) {
  // Git autocrlf changes JSON line endings, not ABI or bytecode. Keep the
  // complete artifact comparison while normalizing checkout-only newlines.
  if (fs.readFileSync(destination,'utf8').replace(/\r\n/g,'\n')!==output) throw new Error('Committed registry bytecode differs from Foundry output');
  process.stdout.write('Foundry source and committed contract artifact match.\n');
} else {
  fs.writeFileSync(destination,output);
  process.stdout.write('Exported pinned Foundry registry artifact.\n');
}
