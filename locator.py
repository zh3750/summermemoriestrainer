import ctypes
import json
import subprocess
import struct
from pathlib import Path

import memory_trainer as mt


VAR_IDS = [1, 3, 5, 23, 26, 27, 28, 39, 59, 65, 157, 158, 159, 320]
ELEMENT_BASE = 4  # FixedArray stores length at offset 0, elements after that


def _valid_ptr(raw):
    return raw is not None and 0x10000 <= raw < 0x7FFF0000 and raw & 1 == 0


def find_party_gold_slot(handle, base):
    """Locate the real gold slot on the Game_Party object in V8 memory."""
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
    return found[0] if len(found) == 1 else None


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


