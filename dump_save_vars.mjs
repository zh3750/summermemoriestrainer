import fs from 'fs';
import path from 'path';
import vm from 'vm';

const GAME_ROOT = 'D:/Program Files (x86)/Steam/steamapps/common/Summer Memories';
const LZ_PATH = path.join(GAME_ROOT, 'www/js/libs/lz-string.js');
const SAVE_DIR = path.join(GAME_ROOT, 'www/save');

vm.runInThisContext(fs.readFileSync(LZ_PATH, 'utf8'));

const WANTED = [1, 3, 5, 23, 26, 27, 28, 39, 59, 65, 157, 158, 159, 320];
const out = {};

for (let slot = 1; slot <= 20; slot++) {
  const file = path.join(SAVE_DIR, `file${slot}.rpgsave`);
  if (!fs.existsSync(file)) continue;
  try {
    const raw = fs.readFileSync(file, 'utf8');
    const data = JSON.parse(LZString.decompressFromBase64(raw));
    const vars = data.variables && data.variables._data && data.variables._data['@a'];
    if (!Array.isArray(vars)) continue;
    out[slot] = {
      length: vars.length,
      values: {},
    };
    for (const id of WANTED) {
      out[slot].values[id] = typeof vars[id] === 'number' ? vars[id] : null;
    }
  } catch {
    // Ignore unreadable slots.
  }
}

process.stdout.write(JSON.stringify(out));
