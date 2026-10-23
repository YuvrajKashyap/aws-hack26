import {build} from '../viewer/node_modules/esbuild/lib/main.js';
import {readFileSync,writeFileSync} from 'node:fs';
const r=await build({entryPoints:['src/main.tsx'],bundle:true,minify:true,jsx:'automatic',format:'iife',write:false,outfile:'dashboard.js',legalComments:'eof',define:{'process.env.NODE_ENV':'"production"','import.meta.env.BASE_URL':'"/"'}});
const js=r.outputFiles.find(f=>f.path.endsWith('.js')).text;
const css=r.outputFiles.find(f=>f.path.endsWith('.css'))?.text||'';
let html=readFileSync('original-index.html','utf8').replace('<script type="module" src="/src/main.tsx"></script>',`<script>${js.replaceAll('</script','<\\/script')}</script>`).replace('</head>',`<style>${css}</style></head>`);
writeFileSync('../../assets/pranav-dashboard.html',html.split('\n').map(l=>l.trimEnd()).join('\n'));
