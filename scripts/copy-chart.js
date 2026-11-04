'use strict';

const fs = require('node:fs');
const path = require('node:path');

const projectRoot = path.resolve(__dirname, '..');
const source = path.join(
  projectRoot,
  'node_modules',
  'chart.js',
  'dist',
  'chart.umd.min.js',
);
const destination = path.join(
  projectRoot,
  'static',
  'vendor',
  'chart.umd.min.js',
);

if (!fs.existsSync(source)) {
  console.error(`Build Chart.js introuvable : ${source}`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(destination), { recursive: true });
fs.copyFileSync(source, destination);
console.log(`Chart.js localisé : ${path.relative(projectRoot, destination)}`);
