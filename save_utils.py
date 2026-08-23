import json
import re
import sys
from pathlib import Path

_BASE = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
_VENDOR = _BASE / 'vendor'
if _VENDOR.exists():
    sys.path.insert(0, str(_VENDOR))

from lzstring import LZString


LZ = LZString()
GAME_NAME = 'Summer Memories'
WANTED_VARS = [1, 3, 5, 23, 26, 27, 28, 39, 59, 65, 157, 158, 159, 320]
ALIASES = {
    'stamina': 27,
    'max': 320,
    'money': 23,
    'memory': 28,
    'action': 65,
    'time': 39,
    'day': 59,
}


def _is_game_root(path):
    return (
        (path / 'www' / 'save').is_dir()
        and (path / 'www' / 'js' / 'libs' / 'lz-string.js').is_file()
    )


def _candidate_roots():
    drives = ['C:', 'D:', 'E:', 'F:', 'G:']
    fixed = [
        r'Program Files (x86)\Steam\steamapps\common',
        r'Program Files\Steam\steamapps\common',
        r'Steam\steamapps\common',
        r'SteamLibrary\steamapps\common',
        r'Steam\steamapps\common',
    ]
    for drive in drives:
        drive_path = Path(drive + '\\')
        for rel in fixed:
            yield drive_path / rel / GAME_NAME
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
        steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
        yield steam_path / 'steamapps' / 'common' / GAME_NAME
        vdf = steam_path / 'steamapps' / 'libraryfolders.vdf'
        if vdf.exists():
            text = vdf.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r'"path"\s+"(.+?)"', text):
                raw = match.group(1).replace('\\\\', '\\')
                yield Path(raw) / 'steamapps' / 'common' / GAME_NAME
    except Exception:
        pass


def find_game_root():
    seen = set()
    for root in _candidate_roots():
        try:
            resolved = root.resolve()
        except Exception:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_game_root(resolved):
            return resolved
    return None


def load_save(root, slot):
    path = Path(root) / 'www' / 'save' / f'file{slot}.rpgsave'
    if not path.exists():
        raise FileNotFoundError(f'存档文件不存在：{path}')
    raw = path.read_text(encoding='utf-8')
    data = json.loads(LZ.decompressFromBase64(raw))
    return path, data


def _dump(data):
    return json.dumps(
        data,
        ensure_ascii=False,
        separators=(',', ':'),
    )


def load_templates(root=None):
    root = Path(root) if root else find_game_root()
    if not root:
        return None
    values = {var_id: set() for var_id in WANTED_VARS}
    lengths = set()
    for slot in range(1, 21):
        path = root / 'www' / 'save' / f'file{slot}.rpgsave'
        if not path.exists():
            continue
        try:
            data = json.loads(LZ.decompressFromBase64(path.read_text(encoding='utf-8')))
            vars_a = data.get('variables', {}).get('_data', {}).get('@a')
            if not isinstance(vars_a, list):
                continue
            lengths.add(len(vars_a))
            for var_id in WANTED_VARS:
                if var_id < len(vars_a) and isinstance(vars_a[var_id], (int, float)):
                    values[var_id].add(vars_a[var_id])
        except Exception:
            continue
    if not lengths:
        return None
    return {'values': values, 'length': max(lengths)}


def load_item_names(root=None):
    root = Path(root) if root else find_game_root()
    if not root:
        return {}
    try:
        path = root / 'www' / 'data' / 'Items.json'
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return {int(item['id']): item.get('name', '') for item in data if item}
    except Exception:
        return {}


def _set_variable(data, var_id, value):
    vars_a = data.get('variables', {}).get('_data', {}).get('@a')
    if not isinstance(vars_a, list) or not (0 <= var_id < len(vars_a)):
        raise ValueError(f'变量编号 {var_id} 超出范围')
    before = vars_a[var_id]
    vars_a[var_id] = int(value)
    return before


def _set_sp(data, value):
    actors = data.get('actors', {}).get('_data', {}).get('@a')
    if not isinstance(actors, list):
        raise ValueError('存档里没有角色数据')
    changed = []
    for actor in actors:
        if isinstance(actor, dict):
            before = actor.get('_stsSp')
            actor['_stsSp'] = int(value)
            changed.append((actor.get('_actorId'), before, int(value)))
    return changed


def _set_gold(data, value):
    party = data.get('party')
    if not isinstance(party, dict):
        raise ValueError('存档里没有队伍数据')
    before = party.get('_gold')
    party['_gold'] = int(value)
    vars_a = data.get('variables', {}).get('_data', {}).get('@a')
    if isinstance(vars_a, list) and len(vars_a) > 23:
        vars_a[23] = int(value)
    return before


def _set_item(data, item_id, count):
    party = data.get('party')
    if not isinstance(party, dict):
        raise ValueError('存档里没有队伍数据')
    party.setdefault('_items', {})
    key = str(item_id)
    before = party['_items'].get(key, 0)
    party['_items'][key] = int(count)
    return before


def _set_all_items(data, count):
    party = data.get('party')
    if not isinstance(party, dict) or not isinstance(party.get('_items'), dict):
        raise ValueError('存档里没有物品数据')
    changed = []
    for key in list(party['_items'].keys()):
        if re.fullmatch(r'\d+', key):
            changed.append((key, party['_items'][key], int(count)))
            party['_items'][key] = int(count)
    return changed


def edit_save(root, slot, edits):
    root = Path(root)
    path, data = load_save(root, slot)
    backup = path.with_suffix('.rpgsave.bak')
    if not backup.exists():
        backup.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

    messages = []
    for edit in edits:
        key, _, value_text = edit.partition('=')
        if not key:
            raise ValueError(f'无效参数：{edit}')
        if key == 'item':
            item_id, _, count_text = value_text.partition(':')
            if not count_text:
                raise ValueError('物品参数要用 item=编号:数量')
            if item_id == 'all':
                messages.append('items: ' + str(_set_all_items(data, int(count_text))))
            else:
                messages.append(
                    f'item {item_id}: {_set_item(data, int(item_id), int(count_text))} -> {int(count_text)}'
                )
        elif key == 'sp':
            value = int(value_text)
            messages.append('sp: ' + str(_set_sp(data, value)))
        elif key == 'gold':
            value = int(value_text)
            messages.append(f'gold: {_set_gold(data, value)} -> {value}')
        else:
            var_id = ALIASES.get(key)
            if var_id is None:
                var_id = int(key)
            value = int(value_text)
            messages.append(
                f'variable {var_id}: {_set_variable(data, var_id, value)} -> {value}'
            )

    path.write_text(LZ.compressToBase64(_dump(data)), encoding='utf-8')
    return messages
