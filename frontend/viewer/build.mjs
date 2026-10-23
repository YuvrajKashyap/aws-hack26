import {build} from 'esbuild';
import {writeFileSync} from 'node:fs';
const result = await build({entryPoints:['viewer.js'], bundle:true, minify:true,
  format:'iife', legalComments:'eof', write:false});
writeFileSync('../../assets/viewer.js', result.outputFiles[0].text.split('\n').map(line=>line.trimEnd()).join('\n'));
