'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
for (const file of ['quest-core.js', 'planner-core.js', 'editor-controller.js', 'ui-common.js', 'panel.js', 'hud-ui.js']) {
  new vm.Script(fs.readFileSync(path.join(root, file), 'utf8'), {filename: file});
}
for (const file of ['hud.html', 'panel.html']) {
  const text = fs.readFileSync(path.join(root, file), 'utf8');
  if (!text.trim().endsWith('</html>')) throw new Error(`${file} is truncated`);
  const opens = (text.match(/<script\b/g) || []).length, closes = (text.match(/<\/script>/g) || []).length;
  if (opens !== closes) throw new Error(`${file} has incomplete script tags`);
  for (const match of text.matchAll(/<script src="([^"]+)"/g)) {
    if (!match[1].startsWith('qrc:') && !fs.existsSync(path.join(root, match[1]))) throw new Error(`Missing asset ${match[1]}`);
  }
}
console.log('JavaScript syntax and both HTML asset lists are valid.');
