import fs from 'fs';
import path from 'path';
import vm from 'vm';

const GAME_ROOT = 'D:/Program Files (x86)/Steam/steamapps/common/Summer Memories';
const LZ_PATH = path.join(GAME_ROOT, 'www/js/libs/lz-string.js');
const SAVE_DIR = path.join(GAME_ROOT, 'www/save');

vm.runInThisContext(fs.readFileSync(LZ_PATH, 'utf8'));

const ALIASES = {
  stamina: 27,
  max: 320,
  money: 23,
  memory: 28,
  action: 65,
  time: 39,
  day: 59,
};

function printHelp() {
  console.log(`Usage: node save_editor.mjs [slot=N] [name=value ...]

Names:
  stamina  body stamina (variable 27)
  max      max stamina (variable 320)
  money    money (variable 23)
  memory   memory points (variable 28)
  time     time band (variable 39)
  day      date (variable 59)
  sp       skill points SP on all actors
  <id>     any game variable id, e.g. 28=9999

Example:
  node save_editor.mjs stamina=999 memory=9999 sp=9999`);
}

function loadSave(slot) {
  const file = path.join(SAVE_DIR, `file${slot}.rpgsave`);
  if (!fs.existsSync(file)) {
    throw new Error(`Save file not found: ${file}`);
  }
  const raw = fs.readFileSync(file, 'utf8');
  const data = JSON.parse(LZString.decompressFromBase64(raw));
  return { file, data };
}

function setVariable(data, id, value) {
  const vars = data.variables && data.variables._data && data.variables._data['@a'];
  if (!Array.isArray(vars) || id < 0 || id >= vars.length) {
    throw new Error(`Variable id ${id} is out of range`);
  }
  const before = vars[id];
  vars[id] = Number(value);
  return before;
}

function setSp(data, value) {
  const actors = data.actors && data.actors._data && data.actors._data['@a'];
  if (!Array.isArray(actors)) {
    throw new Error('Actor data not found in save');
  }
  const changed = [];
  for (const actor of actors) {
    if (actor && typeof actor === 'object') {
      const before = actor._stsSp;
      actor._stsSp = Number(value);
      changed.push({ id: actor._actorId, before, after: actor._stsSp });
    }
  }
  return changed;
}

function setGold(data, value) {
  if (!data.party || typeof data.party !== 'object') {
    throw new Error('Party data not found in save');
  }
  const before = data.party._gold;
  data.party._gold = Number(value);
  if (Array.isArray(data.variables?._data?.['@a'])) {
    data.variables._data['@a'][23] = Number(value);
  }
  return before;
}

function setItem(data, id, count) {
  if (!data.party || typeof data.party !== 'object') {
    throw new Error('Party data not found in save');
  }
  const key = String(id);
  const before = data.party._items?.[key] || 0;
  data.party._items = data.party._items || {};
  data.party._items[key] = Number(count);
  return before;
}

function setAllItems(data, count) {
  if (!data.party?._items || typeof data.party._items !== 'object') {
    throw new Error('Item data not found in save');
  }
  const changed = [];
  for (const key of Object.keys(data.party._items)) {
    if (/^\d+$/.test(key)) {
      changed.push({ id: key, before: data.party._items[key], after: Number(count) });
      data.party._items[key] = Number(count);
    }
  }
  return changed;
}

const args = process.argv.slice(2);
if (args.length === 0 || args.some((a) => a === 'help' || a === '--help')) {
  printHelp();
  process.exit(0);
}

let slot = 1;
const edits = [];
for (const arg of args) {
  const slotMatch = arg.match(/^slot=(\d+)$/);
  if (slotMatch) {
    slot = Number(slotMatch[1]);
    continue;
  }
  const eq = arg.indexOf('=');
  if (eq < 1) {
    throw new Error(`Invalid argument: ${arg}`);
  }
  const key = arg.slice(0, eq);
  const value = arg.slice(eq + 1);
  edits.push({ key, value });
}

const { file, data } = loadSave(slot);
const backup = file + '.bak';
if (!fs.existsSync(backup)) {
  fs.copyFileSync(file, backup);
  console.log(`Backup created: ${backup}`);
}

for (const edit of edits) {
  const value = Number(edit.value);
  if (edit.key === 'sp') {
    const changed = setSp(data, value);
    console.log('sp changed:', JSON.stringify(changed));
  } else if (edit.key === 'gold') {
    const before = setGold(data, value);
    console.log(`gold: ${before} -> ${value}`);
  } else if (edit.key === 'item') {
    const sep = edit.value.indexOf(':');
    if (sep < 0) {
      throw new Error(`Invalid item value, use item=id:count or item=all:count`);
    }
    const id = edit.value.slice(0, sep);
    const count = edit.value.slice(sep + 1);
    if (id === 'all') {
      console.log('items changed:', JSON.stringify(setAllItems(data, Number(count))));
    } else {
      const before = setItem(data, id, Number(count));
      console.log(`item ${id}: ${before} -> ${Number(count)}`);
    }
  } else {
    const id = ALIASES[edit.key] !== undefined ? ALIASES[edit.key] : Number(edit.key);
    if (Number.isNaN(id)) {
      throw new Error(`Unknown name: ${edit.key}`);
    }
    const before = setVariable(data, id, value);
    console.log(`variable ${id}: ${before} -> ${value}`);
  }
}

const out = LZString.compressToBase64(JSON.stringify(data));
fs.writeFileSync(file, out, 'utf8');
console.log(`Save written: ${file}`);
