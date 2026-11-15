import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { build } from 'esbuild';

await mkdir('dist/assets', { recursive: true });
await build({
  entryPoints: ['src/main.jsx'],
  bundle: true,
  minify: true,
  jsx: 'automatic',
  outdir: 'dist/assets',
  define: { 'process.env.NODE_ENV': '"production"' },
});
let index = await readFile('index.html', 'utf8');
for (const name of ['main.css', 'main.js']) {
  const url = `/assets/${name}`;
  const bytes = await readFile(`dist${url}`);
  const version = createHash('sha256').update(bytes).digest('hex').slice(0, 12);
  index = index.replace(`"${url}"`, `"${url}?v=${version}"`);
}
await writeFile('dist/index.html', index);
await cp('assets', 'dist/assets', { recursive: true });
