import ctypes
import struct

import memory_trainer as mt


VAR_IDS = [1, 3, 5, 23, 26, 27, 28, 39, 59, 65, 157, 158, 159, 320]
ELEMENT_BASE = 4  # FixedArray stores length at offset 0, elements after that


def smi_to_int(raw):
    """Decode a V8 small-integer tagged value."""
    if raw & 1:
        return None
    signed = raw - 0x100000000 if raw >= 0x80000000 else raw
    return signed >> 1


def _read32(handle, addr):
    buf = ctypes.create_string_buffer(4)
    read = ctypes.c_size_t(0)
    if not mt.kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(addr), buf, 4, ctypes.byref(read)
    ):
        return None
    if read.value != 4:
        return None
    return struct.unpack('<I', buf.raw[:4])[0]


def decode_tagged(handle, raw, addr):
    """Turn a tagged V8 value into a Python number when possible."""
    int_value = smi_to_int(raw)
    if int_value is not None:
        return int_value
    buf = ctypes.create_string_buffer(8)
    read = ctypes.c_size_t(0)
    if mt.kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(raw + 4), buf, 8, ctypes.byref(read)
    ) and read.value == 8:
        return struct.unpack('<d', buf.raw[:8])[0]
    return None


def read_var(handle, base, var_id):
    addr = base + ELEMENT_BASE + 4 * var_id
    raw = _read32(handle, addr)
    if raw is None:
        return None
    return decode_tagged(handle, raw, addr)


def write_var(handle, base, var_id, value):
    addr = base + ELEMENT_BASE + 4 * var_id
    packed = struct.pack('<I', int(value) << 1 & 0xFFFFFFFF)
    written = ctypes.c_size_t(0)
    return bool(
        mt.kernel32.WriteProcessMemory(
            handle,
            ctypes.c_void_p(addr),
            packed,
            4,
            ctypes.byref(written),
        )
    ) and written.value == 4


def _valid_ptr(raw):
    return raw is not None and 0x10000 <= raw < 0x7FFF0000 and raw & 1 == 0


def find_game_party_object(handle):
    """Locate the Game_Party instance through the global $gameParty string."""
    name = b'$gameParty'
    data_pattern = name + b'\x00\x00'
    strings = set()
    for region_base, region_size in mt.iter_regions(handle):
        for off in range(0, region_size, mt.CHUNK_SIZE):
            length = min(mt.CHUNK_SIZE, region_size - off)
            buf = ctypes.create_string_buffer(length)
            read = ctypes.c_size_t(0)
            if not mt.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(region_base + off),
                buf,
                length,
                ctypes.byref(read),
            ):
                continue
            data = buf.raw[: read.value]
            pos = 0
            while True:
                pos = data.find(data_pattern, pos)
                if pos < 0:
                    break
                s = region_base + off + pos - 12
                map_ptr = _read32(handle, s)
                length_smi = smi_to_int(_read32(handle, s + 8)) if _read32(handle, s + 8) is not None else None
                if _valid_ptr(map_ptr) and length_smi == len(name):
                    strings.add(s)
                pos += 1
    if not strings:
        return None

    for region_base, region_size in mt.iter_regions(handle):
        for off in range(0, region_size, mt.CHUNK_SIZE):
            length = min(mt.CHUNK_SIZE, region_size - off)
            buf = ctypes.create_string_buffer(length)
            read = ctypes.c_size_t(0)
            if not mt.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(region_base + off),
                buf,
                length,
                ctypes.byref(read),
            ):
                continue
            data = buf.raw[: read.value]
            for s in list(strings):
                pattern = struct.pack('<I', s)
                pos = 0
                while True:
                    pos = data.find(pattern, pos)
                    if pos < 0:
                        break
                    ref = region_base + off + pos
                    value = _read32(handle, ref + 4)
                    if _valid_ptr(value):
                        obj_map = _read32(handle, value)
                        gold_raw = _read32(handle, value + 16)
                        steps_raw = _read32(handle, value + 20)
                        if (
                            _valid_ptr(obj_map)
                            and smi_to_int(gold_raw) is not None
                            and smi_to_int(steps_raw) is not None
                        ):
                            return value
                    pos += 1
    return None


def find_party_gold_slot(handle, base, hint=None):
    """Locate the real gold slot on the Game_Party object in V8 memory."""
    if hint is None:
        hint = read_var(handle, base, 23)
    if not isinstance(hint, (int, float)):
        return None
    pattern = struct.pack('<I', int(hint) << 1)
    found = []
    for region_base, region_size in mt.iter_regions(handle):
        for off in range(0, region_size, mt.CHUNK_SIZE):
            length = min(mt.CHUNK_SIZE, region_size - off)
            buf = ctypes.create_string_buffer(length)
            read = ctypes.c_size_t(0)
            if not mt.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(region_base + off),
                buf,
                length,
                ctypes.byref(read),
            ):
                continue
            data = buf.raw[: read.value]
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos < 0:
                    break
                slot = region_base + off + pos
                obj = slot - 16
                map_ptr = _read32(handle, obj)
                props = _read32(handle, obj + 4)
                elems = _read32(handle, obj + 8)
                menu_actor_raw = _read32(handle, obj + 28)
                target_actor_raw = _read32(handle, obj + 32)
                actors = _read32(handle, obj + 36)
                items = _read32(handle, obj + 40)
                weapons = _read32(handle, obj + 44)
                armors = _read32(handle, obj + 48)
                menu_actor = (
                    smi_to_int(menu_actor_raw) if menu_actor_raw is not None else None
                )
                target_actor = (
                    smi_to_int(target_actor_raw)
                    if target_actor_raw is not None
                    else None
                )
                if (
                    menu_actor == 0
                    and target_actor == 0
                    and all(
                        _valid_ptr(x)
                        for x in (
                            map_ptr,
                            props,
                            elems,
                            actors,
                            items,
                            weapons,
                            armors,
                        )
                    )
                ):
                    found.append(slot)
                pos += 1
    if found:
        return found[0]
    obj = find_game_party_object(handle)
    if obj:
        return obj + 16
    return None


def read_party_gold(handle, gold_slot):
    raw = _read32(handle, gold_slot)
    return smi_to_int(raw) if raw is not None else None


def write_party_gold(handle, gold_slot, value):
    packed = struct.pack('<I', int(value) << 1 & 0xFFFFFFFF)
    written = ctypes.c_size_t(0)
    return bool(
        mt.kernel32.WriteProcessMemory(
            handle,
            ctypes.c_void_p(gold_slot),
            packed,
            4,
            ctypes.byref(written),
        )
    ) and written.value == 4


def _valid_array(handle, array_base):
    length_raw = _read32(handle, array_base)
    length_value = smi_to_int(length_raw) if length_raw is not None else None
    if length_value is None or not (320 <= length_value <= 2000):
        return None
    vals = {var_id: read_var(handle, array_base, var_id) for var_id in VAR_IDS}
    all_numeric = all(
        isinstance(vals[var_id], (int, float)) for var_id in VAR_IDS
    )
    if not (
        all_numeric
        and 0 <= vals[23] <= 9999999
        and 0 <= vals[27] <= 9999999
        and 0 <= vals[28] <= 9999999
        and 0 <= vals[39] <= 10
        and 0 <= vals[59] <= 9999
        and 10 <= vals[320] <= 9999999
    ):
        return None
    return vals


def _scan_by_length(handle, length):
    pattern = struct.pack('<I', length << 1)
    candidates = []
    for base, region_size in mt.iter_regions(handle):
        for offset in range(0, region_size, mt.CHUNK_SIZE):
            size = min(mt.CHUNK_SIZE, region_size - offset)
            buf = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t(0)
            if not mt.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(base + offset),
                buf,
                size,
                ctypes.byref(read),
            ):
                continue
            data = buf.raw[: read.value]
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos < 0:
                    break
                array_base = base + offset + pos
                vals = _valid_array(handle, array_base)
                if vals is not None:
                    candidates.append((array_base, vals))
                pos += 1
    return candidates


def _scan_by_max_stamina(handle):
    pattern = struct.pack('<I', 100 << 1)
    candidates = []
    for base, region_size in mt.iter_regions(handle):
        for offset in range(0, region_size, mt.CHUNK_SIZE):
            size = min(mt.CHUNK_SIZE, region_size - offset)
            buf = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t(0)
            if not mt.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(base + offset),
                buf,
                size,
                ctypes.byref(read),
            ):
                continue
            data = buf.raw[: read.value]
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos < 0:
                    break
                elem320 = base + offset + pos
                array_base = elem320 - (ELEMENT_BASE + 4 * 320)
                vals = _valid_array(handle, array_base)
                if vals is not None:
                    candidates.append((array_base, vals))
                pos += 1
    return candidates


def _scan_candidates(handle, expected_length=None):
    if expected_length:
        return _scan_by_length(handle, expected_length)
    found = _scan_by_max_stamina(handle)
    if found:
        return found
    return _scan_by_length(handle, 661)


def find_best_candidate(handle, expected_length=None, templates=None):
    candidates = _scan_candidates(handle, expected_length)
    if not candidates:
        return None

    def score(item):
        base, vals = item
        points = 0
        if templates:
            known = templates.get('values', {})
            for var_id in VAR_IDS:
                expected = known.get(var_id)
                if expected and vals.get(var_id) in expected:
                    points += 1
        return points

    candidates.sort(key=score, reverse=True)
    best = candidates[0]
    if templates and score(best) == 0:
        return None
    return best


def find_game_pid():
    pids = mt.list_game_processes()
    if not pids:
        return None
    infos = [(pid, mt.process_working_set(pid)) for pid in pids]
    best = max(range(len(infos)), key=lambda i: infos[i][1] or -1)
    return pids[best]
