import ctypes
import struct
import threading
import time
from ctypes import wintypes

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
TH32CS_SNAPPROCESS = 0x00000002
CHUNK_SIZE = 4 * 1024 * 1024
MAX_RESULTS = 300000

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.VirtualQueryEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_void_p,
    ctypes.c_size_t,
]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', wintypes.LPVOID),
        ('AllocationBase', wintypes.LPVOID),
        ('AllocationProtect', wintypes.DWORD),
        ('PartitionId', wintypes.WORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', wintypes.DWORD),
        ('Protect', wintypes.DWORD),
        ('Type', wintypes.DWORD),
    ]

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_wchar * 260),
    ]

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]

kernel32.Process32FirstW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESSENTRY32W),
]
kernel32.Process32NextW.restype = wintypes.BOOL
psapi.GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
    wintypes.DWORD,
]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

KINDS = {
    'double': ('<d', 8, '8-byte double'),
    'u32': ('<I', 4, '4-byte int'),
    'u16': ('<H', 2, '2-byte int'),
}

def open_process(pid):
    flags = (
        PROCESS_QUERY_INFORMATION
        | PROCESS_VM_READ
        | PROCESS_VM_WRITE
        | PROCESS_VM_OPERATION
    )
    handle = kernel32.OpenProcess(flags, False, pid)
    if not handle:
        print(f'[!] Cannot open PID {pid}. Run this tool as administrator if needed.')
    return handle

def process_working_set(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), ctypes.sizeof(counters)
        ):
            return int(counters.WorkingSetSize)
        return None
    finally:
        kernel32.CloseHandle(handle)

def list_game_processes():
    pids = []
    invalid = ctypes.c_void_p(-1).value
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == invalid:
        return pids
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == 'game.exe':
                pids.append(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return pids

def is_readable(protect):
    return (protect & (PAGE_NOACCESS | PAGE_GUARD)) == 0 and (protect & 0xFF) != 0

def iter_regions(handle):
    addr = 0
    while addr < 0x7FFF0000:
        mbi = MEMORY_BASIC_INFORMATION()
        if kernel32.VirtualQueryEx(
            handle,
            ctypes.c_void_p(addr),
            ctypes.byref(mbi),
            ctypes.sizeof(mbi),
        ) == 0:
            break
        size = int(mbi.RegionSize or 0)
        if size <= 0:
            break
        if mbi.State == MEM_COMMIT and is_readable(mbi.Protect):
            yield addr, size
        addr += size

def find_all(data, pattern):
    out = []
    pos = 0
    while True:
        pos = data.find(pattern, pos)
        if pos < 0:
            break
        out.append(pos)
        pos += 1
        if len(out) >= MAX_RESULTS:
            break
    return out

def first_scan(handle, value, kind):
    fmt, size, _ = KINDS[kind]
    pattern = struct.pack(fmt, value)
    results = []
    for base, region_size in iter_regions(handle):
        for offset in range(0, region_size, CHUNK_SIZE):
            length = min(CHUNK_SIZE, region_size - offset)
            buf = ctypes.create_string_buffer(length)
            read = ctypes.c_size_t(0)
            if not kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(base + offset),
                buf,
                length,
                ctypes.byref(read),
            ):
                continue
            data = buf.raw[: read.value]
            for pos in find_all(data, pattern):
                results.append(base + offset + pos)
                if len(results) >= MAX_RESULTS:
                    return results
    return results

def next_scan(handle, results, value, kind):
    fmt, size, _ = KINDS[kind]
    packed = struct.pack(fmt, value)
    out = []
    for addr in results:
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(
            handle,
            ctypes.c_void_p(addr),
            buf,
            size,
            ctypes.byref(read),
        ):
            continue
        if read.value == size and buf.raw[:size] == packed:
            out.append(addr)
    return out

def write_value(handle, addr, value, kind):
    fmt, size, _ = KINDS[kind]
    packed = struct.pack(fmt, value)
    written = ctypes.c_size_t(0)
    ok = kernel32.WriteProcessMemory(
        handle,
        ctypes.c_void_p(addr),
        packed,
        size,
        ctypes.byref(written),
    )
    return bool(ok) and written.value == size

class Freezer:
    def __init__(self):
        self._lock = threading.Lock()
        self._items = []
        self._stop = False
        self._thread = None

    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=1)

    def add(self, handle, addr, value, kind):
        fmt, size, _ = KINDS[kind]
        packed = struct.pack(fmt, value)
        with self._lock:
            self._items = [
                item
                for item in self._items
                if item['addr'] != addr
            ]
            self._items.append({
                'handle': handle,
                'addr': addr,
                'packed': packed,
            })

    def remove(self, addr=None, remove_all=False):
        with self._lock:
            if remove_all:
                self._items = []
            elif addr is not None:
                self._items = [
                    item for item in self._items if item['addr'] != addr
                ]

    def count(self):
        with self._lock:
            return len(self._items)

    def _run(self):
        while not self._stop:
            with self._lock:
                items = list(self._items)
            for item in items:
                written = ctypes.c_size_t(0)
                kernel32.WriteProcessMemory(
                    item['handle'],
                    ctypes.c_void_p(item['addr']),
                    item['packed'],
                    len(item['packed']),
                    ctypes.byref(written),
                )
            time.sleep(0.02)

def parse_value(kind, text):
    if kind == 'double':
        return float(text)
    return int(text)

def resolve_target(token, results):
    token = token.strip()
    if token.lower().startswith('0x'):
        return int(token, 16)
    idx = int(token)
    if 0 <= idx < len(results):
        return results[idx]
    raise ValueError(f'index {idx} is out of range')

def show_results(results, limit=20):
    print(f'Total matches: {len(results)}')
    for i, addr in enumerate(results[:limit]):
        print(f'  #{i}: 0x{addr:X}')
    if len(results) > limit:
        print(f'  ... and {len(results) - limit} more')

def print_help():
    print(
        '\nCommands:\n'
        '  first <value>            first scan for a value\n'
        '  next <value>             filter previous results with a new value\n'
        '  show [n]                 show matches (default 20)\n'
        '  set <addr|#> <value>     write a value to one match\n'
        '  freeze <addr|#> <value>  keep writing a value every 0.1s\n'
        '  unfreeze <addr|#>|all    stop freezing\n'
        '  type <double|u32|u16>    change scan type (default double)\n'
        '  clear                    clear current results\n'
        '  help                     show this help\n'
        '  quit\n'
    )

def main():
    games = list_game_processes()
    if not games:
        print('No Game.exe process found. Start the game first.')
        input('Press Enter to exit...')
        return

    print('Game.exe processes:')
    infos = [(pid, process_working_set(pid)) for pid in games]
    best_index = max(
        range(len(infos)),
        key=lambda i: infos[i][1] if infos[i][1] is not None else -1,
    )
    for i, (pid, ws) in enumerate(infos):
        if ws is None:
            print(f'  {i}: PID {pid}  (cannot read memory size)')
        else:
            mark = '  <-- recommended' if i == best_index else ''
            print(f'  {i}: PID {pid}  {ws / 1048576:.1f} MB{mark}')

    choice = input(f'Enter index or PID [{best_index}]: ').strip()
    if not choice:
        pid = games[best_index]
    elif choice.isdigit() and int(choice) < len(games):
        pid = games[int(choice)]
    else:
        pid = int(choice)

    handle = open_process(pid)
    if not handle:
        input('Press Enter to exit...')
        return

    kind = 'double'
    results = []
    freezer = Freezer()
    freezer.start()
    print_help()
    print(f'Attached to PID {pid}. Scan type: {kind} ({KINDS[kind][2]}).')

    try:
        while True:
            try:
                line = input('> ').strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()

            try:
                if cmd == 'quit':
                    break
                elif cmd == 'help':
                    print_help()
                elif cmd == 'first':
                    value = parse_value(kind, parts[1])
                    results = first_scan(handle, value, kind)
                    show_results(results)
                elif cmd == 'next':
                    if not results:
                        print('No results yet. Use first <value> first.')
                        continue
                    value = parse_value(kind, parts[1])
                    results = next_scan(handle, results, value, kind)
                    show_results(results)
                elif cmd == 'show':
                    limit = int(parts[1]) if len(parts) > 1 else 20
                    show_results(results, limit)
                elif cmd == 'set':
                    addr = resolve_target(parts[1], results)
                    value = parse_value(kind, parts[2])
                    if write_value(handle, addr, value, kind):
                        print(f'Wrote {value} to 0x{addr:X}')
                    else:
                        print(f'Failed to write 0x{addr:X}')
                elif cmd == 'freeze':
                    addr = resolve_target(parts[1], results)
                    value = parse_value(kind, parts[2])
                    write_value(handle, addr, value, kind)
                    freezer.add(handle, addr, value, kind)
                    print(f'Freezing 0x{addr:X} at {value}')
                elif cmd == 'unfreeze':
                    if parts[1].lower() == 'all':
                        freezer.remove(remove_all=True)
                        print('All freeze slots removed.')
                    else:
                        addr = resolve_target(parts[1], results)
                        freezer.remove(addr=addr)
                        print(f'Unfroze 0x{addr:X}')
                elif cmd == 'type':
                    new_kind = parts[1].lower()
                    if new_kind not in KINDS:
                        print('Type must be double, u32 or u16.')
                    else:
                        kind = new_kind
                        print(f'Scan type: {kind} ({KINDS[kind][2]})')
                elif cmd == 'clear':
                    results = []
                    print('Results cleared.')
                else:
                    print('Unknown command. Type help to see commands.')
            except (IndexError, ValueError) as e:
                print(f'[!] {e}')
    finally:
        freezer.stop()
        kernel32.CloseHandle(handle)

if __name__ == '__main__':
    main()
