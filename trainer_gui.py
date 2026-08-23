import json
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))

import memory_trainer as mt
import locator
import save_utils


TRAINER_DIR = Path(__file__).resolve().parent
BG = '#20242e'
PANEL = '#2a3040'
PANEL_LIGHT = '#333a4d'
TEXT = '#e8ebf2'
MUTED = '#9aa3b5'
ACCENT = '#e8b34b'

class TrainerApp(tk.Tk):
    CHARACTERS = [
        ('结衣', 1, 2, 157),
        ('莉音', 3, 4, 158),
        ('美雪', 5, 6, 159),
    ]

    CUSTOM_IDS = {
        '体力': 27,
        '体力上限': 320,
        '行动点': 65,
        '金钱': 23,
        '回忆点': 28,
        '时间带': 39,
        '日期': 59,
        '性欲': 26,
        '结衣好感': 1,
        '莉音好感': 3,
        '美雪好感': 5,
        '结衣警戒': 2,
        '莉音警戒': 4,
        '美雪警戒': 6,
        '结衣课题': 157,
        '莉音课题': 158,
        '美雪课题': 159,
    }

    def __init__(self):
        super().__init__()
        self.title('夏日狂想曲 修改器')
        self.geometry('1080x820')
        self.minsize(940, 720)
        self.configure(bg=BG)

        self.handle = None
        self.base = None
        self.gold_slot = None
        self.freezer = mt.Freezer()
        self.freezer.start()
        self.msg_queue = queue.Queue()
        self.game_root = save_utils.find_game_root()
        self.item_names = save_utils.load_item_names(self.game_root)
        self.item_follow = True

        self._build_style()
        self._build_ui()

        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(100, self._poll_queue)
        self.after(1200, self.refresh_values)
        self.after(400, self.connect_game)

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure(
            'TButton',
            font=('Microsoft YaHei UI', 10, 'bold'),
            padding=(9, 6),
            background='#3f485e',
            foreground=TEXT,
            borderwidth=0,
        )
        style.map(
            'TButton',
            background=[('active', '#57627c'), ('pressed', '#2e3547')],
            foreground=[('disabled', MUTED)],
        )
        style.configure(
            'Accent.TButton',
            background=ACCENT,
            foreground='#1b1e26',
            font=('Microsoft YaHei UI', 11, 'bold'),
        )
        style.map(
            'Accent.TButton',
            background=[('active', '#f0c66d'), ('pressed', '#c99632')],
        )
        style.configure(
            'TCombobox',
            fieldbackground=PANEL_LIGHT,
            background=PANEL_LIGHT,
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=PANEL,
            padding=5,
        )

    def _panel(self, parent):
        return tk.Frame(parent, bg=PANEL, padx=14, pady=12)

    def _title(self, parent, text):
        tk.Label(
            parent,
            text=text,
            bg=PANEL,
            fg=ACCENT,
            font=('Microsoft YaHei UI', 11, 'bold'),
        ).pack(anchor='w')

    def _build_ui(self):
        header = tk.Frame(self, bg='#171a21', padx=18, pady=12)
        header.pack(fill='x')
        tk.Label(
            header,
            text='夏日狂想曲 修改器',
            bg='#171a21',
            fg=TEXT,
            font=('Microsoft YaHei UI', 18, 'bold'),
        ).pack(side='left')
        tk.Label(
            header,
            text='单机自用，改完即玩',
            bg='#171a21',
            fg=MUTED,
            font=('Microsoft YaHei UI', 10),
        ).pack(side='left', padx=12, pady=(4, 0))

        status = tk.Frame(self, bg=BG, padx=18, pady=10)
        status.pack(fill='x')
        self.game_status = tk.StringVar(value='正在寻找游戏...')
        self.locate_status = tk.StringVar(value='')
        tk.Label(
            status,
            textvariable=self.game_status,
            bg=BG,
            fg=TEXT,
            font=('Microsoft YaHei UI', 11, 'bold'),
        ).pack(side='left')
        tk.Label(
            status,
            textvariable=self.locate_status,
            bg=BG,
            fg=MUTED,
            font=('Microsoft YaHei UI', 10),
        ).pack(side='left', padx=14)
        ttk.Button(
            status,
            text='重新连接',
            command=self.connect_game,
        ).pack(side='right')
        ttk.Button(
            status,
            text='游戏目录',
            command=self.choose_game_root,
        ).pack(side='right', padx=8)
        ttk.Button(
            status,
            text='解除全部锁定',
            command=self.unfreeze_all,
        ).pack(side='right', padx=8)

        scroll_wrap = tk.Frame(self, bg=BG)
        scroll_wrap.pack(fill='both', expand=True)
        body = self._build_scrollable(scroll_wrap)
        body.configure(padx=18, pady=6)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=3)
        body.columnconfigure(2, weight=3)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=0)

        left = self._panel(body)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        self._title(left, '实时修改')
        self._build_live_rows(left)

        mid = self._panel(body)
        mid.grid(row=0, column=1, sticky='nsew', padx=(8, 8))
        self._title(mid, '人物数值（先选人再看）')
        self._build_actor_panel(mid)

        right = self._panel(body)
        right.grid(row=0, column=2, sticky='nsew', padx=(8, 0))
        self._title(right, '存档修改（重进生效）')
        self._build_save_panel(right)

        custom_panel = self._panel(body)
        custom_panel.grid(
            row=1, column=0, columnspan=3, sticky='ew', pady=(10, 0)
        )
        self._build_custom_panel(custom_panel)

        log_panel = self._panel(body)
        log_panel.grid(
            row=2, column=0, columnspan=3, sticky='ew', pady=(10, 0)
        )
        self._title(log_panel, '最近操作')
        self.log_text = tk.Text(
            log_panel,
            height=4,
            bg='#171a21',
            fg=TEXT,
            insertbackground=TEXT,
            relief='flat',
            font=('Microsoft YaHei UI', 9),
            padx=8,
            pady=6,
        )
        self.log_text.pack(fill='x', pady=(6, 0))
        self.log_text.configure(state='disabled')

    def _build_scrollable(self, parent):
        canvas = tk.Canvas(
            parent,
            bg=BG,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            parent,
            orient='vertical',
            command=canvas.yview,
        )
        inner = tk.Frame(canvas, bg=BG)
        inner_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        inner.bind(
            '<Configure>',
            lambda _: canvas.configure(scrollregion=canvas.bbox('all')),
        )
        canvas.bind(
            '<Configure>',
            lambda event: canvas.itemconfigure(inner_id, width=event.width),
        )

        def bind_wheel(_):
            canvas.bind_all('<MouseWheel>', self._on_mousewheel)

        def unbind_wheel(_):
            canvas.unbind_all('<MouseWheel>')

        inner.bind('<Enter>', bind_wheel)
        inner.bind('<Leave>', unbind_wheel)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        self._scroll_canvas = canvas
        return inner

    def _on_mousewheel(self, event):
        if hasattr(self, '_scroll_canvas'):
            self._scroll_canvas.yview_scroll(
                int(-event.delta / 120),
                'units',
            )

    def _build_live_rows(self, parent):
        self.value_vars = {}
        rows = [
            ('体力', 27, [('回满', 'refill'), ('锁9999', 'freeze_stamina')]),
            ('体力上限', 320, []),
            ('行动点', 65, [('9999', 'action_boost'), ('锁', 'freeze_action')]),
            ('金钱', 23, [('99999', 'money')]),
            ('回忆点', 28, [('9999', 'memory')]),
            ('性欲', 26, [('9999', 'lust_boost'), ('锁', 'freeze_lust')]),
            ('日期', 59, [('-1', 'day_minus'), ('+1', 'day_plus'), ('冻结', 'freeze_day')]),
        ]
        for label, var_id, actions in rows:
            row = tk.Frame(parent, bg=PANEL, pady=3)
            row.pack(fill='x', pady=2)
            tk.Label(
                row,
                text=label,
                width=6,
                anchor='w',
                bg=PANEL,
                fg=MUTED,
                font=('Microsoft YaHei UI', 10),
            ).pack(side='left')
            var = tk.StringVar(value='-')
            self.value_vars[var_id] = var
            tk.Label(
                row,
                textvariable=var,
                width=5,
                anchor='w',
                bg=PANEL,
                fg=TEXT,
                font=('Microsoft YaHei UI', 12, 'bold'),
            ).pack(side='left')
            for text, action in actions:
                ttk.Button(
                    row,
                    text=text,
                    command=getattr(self, action),
                ).pack(side='right', padx=3)

        self._build_time_row(parent)

        ttk.Button(
            parent,
            text='全部拉到 9999',
            style='Accent.TButton',
            command=self.mega_boost,
        ).pack(fill='x', pady=(12, 0))
        tk.Label(
            parent,
            text='行动点会被时间推进重置，锁住才不会变；解除全部锁定可关闭。',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 9),
            justify='left',
            wraplength=300,
        ).pack(anchor='w', pady=(10, 0))

    def _build_time_row(self, parent):
        top = tk.Frame(parent, bg=PANEL, pady=3)
        top.pack(fill='x', pady=2)
        tk.Label(
            top,
            text='时间带',
            width=6,
            anchor='w',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 10),
        ).pack(side='left')
        self.value_vars[39] = tk.StringVar(value='-')
        tk.Label(
            top,
            textvariable=self.value_vars[39],
            width=5,
            anchor='w',
            bg=PANEL,
            fg=TEXT,
            font=('Microsoft YaHei UI', 12, 'bold'),
        ).pack(side='left')
        for text, action in [
            ('-1', 'time_minus'),
            ('+1', 'time_plus'),
            ('冻结', 'freeze_time'),
        ]:
            ttk.Button(
                top,
                text=text,
                command=getattr(self, action),
            ).pack(side='right', padx=3)

        bottom = tk.Frame(parent, bg=PANEL, pady=3)
        bottom.pack(fill='x', pady=(0, 2))
        for label, value in [
            ('早', 1),
            ('中', 2),
            ('黄昏', 3),
            ('晚', 4),
            ('深夜', 5),
        ]:
            ttk.Button(
                bottom,
                text=label,
                command=lambda v=value: self.time_set(v),
            ).pack(side='left', padx=3, fill='x', expand=True)

    def _build_actor_panel(self, parent):
        self.actor_names = [c[0] for c in self.CHARACTERS]
        self.actor_var = tk.StringVar(value=self.actor_names[0])
        ttk.Combobox(
            parent,
            textvariable=self.actor_var,
            values=self.actor_names,
            state='readonly',
            width=12,
        ).pack(fill='x', pady=(8, 8))
        self.actor_var.trace_add('write', lambda *_: self.refresh_actor())

        self.actor_vals = {}
        for label, key in [('好感度', 'aff'), ('警戒度', 'guard'), ('课题/作业', 'task')]:
            row = tk.Frame(parent, bg=PANEL, pady=2)
            row.pack(fill='x')
            tk.Label(
                row,
                text=label,
                width=6,
                anchor='w',
                bg=PANEL,
                fg=MUTED,
                font=('Microsoft YaHei UI', 10),
            ).pack(side='left')
            var = tk.StringVar(value='-')
            self.actor_vals[key] = var
            tk.Label(
                row,
                textvariable=var,
                width=8,
                anchor='w',
                bg=PANEL,
                fg=TEXT,
                font=('Microsoft YaHei UI', 13, 'bold'),
            ).pack(side='left')

        self.actor_custom_aff = tk.StringVar(value='9999')
        self.actor_custom_task = tk.StringVar(value='9999')
        aff_row = tk.Frame(parent, bg=PANEL)
        aff_row.pack(fill='x', pady=(10, 0))
        tk.Label(
            aff_row,
            text='好感',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 10),
        ).pack(side='left')
        tk.Entry(
            aff_row,
            textvariable=self.actor_custom_aff,
            width=8,
            bg='#171a21',
            fg=TEXT,
            insertbackground=TEXT,
            relief='flat',
            font=('Microsoft YaHei UI', 10),
            justify='center',
        ).pack(side='left', padx=6)
        ttk.Button(
            aff_row,
            text='写入',
            command=self.actor_write_aff,
        ).pack(side='left', padx=2)
        ttk.Button(
            aff_row,
            text='锁',
            command=self.actor_freeze_aff,
        ).pack(side='left', padx=2)
        ttk.Button(
            aff_row,
            text='9999',
            command=self.actor_boost_aff,
        ).pack(side='left', padx=2)

        task_row = tk.Frame(parent, bg=PANEL)
        task_row.pack(fill='x', pady=(8, 0))
        tk.Label(
            task_row,
            text='课题',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 10),
        ).pack(side='left')
        tk.Entry(
            task_row,
            textvariable=self.actor_custom_task,
            width=8,
            bg='#171a21',
            fg=TEXT,
            insertbackground=TEXT,
            relief='flat',
            font=('Microsoft YaHei UI', 10),
            justify='center',
        ).pack(side='left', padx=6)
        ttk.Button(
            task_row,
            text='写入',
            command=self.actor_write_task,
        ).pack(side='left', padx=2)
        ttk.Button(
            task_row,
            text='9999',
            command=self.actor_boost_task,
        ).pack(side='left', padx=2)
        tk.Label(
            parent,
            text='选好人以后，改好感或课题会作用在当前人物身上。',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 9),
            justify='left',
            wraplength=280,
        ).pack(anchor='w', pady=(10, 0))

    def _actor_ids(self):
        name = self.actor_var.get()
        for item in self.CHARACTERS:
            if item[0] == name:
                return item
        return self.CHARACTERS[0]

    def refresh_actor(self):
        if not self.handle or self.base is None:
            return
        _, aff_id, guard_id, task_id = self._actor_ids()
        values = {
            'aff': locator.read_var(self.handle, self.base, aff_id),
            'guard': locator.read_var(self.handle, self.base, guard_id),
            'task': locator.read_var(self.handle, self.base, task_id),
        }
        for key, var in self.actor_vals.items():
            value = values.get(key)
            var.set(str(value) if value is not None else '-')

    def _build_save_panel(self, parent):
        tk.Label(
            parent,
            text='技能点、真实金钱、背包物品改存档最稳。',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 9),
            justify='left',
            wraplength=300,
        ).pack(anchor='w', pady=(4, 8))

        self.slot_var = tk.StringVar(value='1号存档位')
        ttk.Combobox(
            parent,
            textvariable=self.slot_var,
            values=['1号存档位', '2号存档位'],
            state='readonly',
        ).pack(fill='x')

        sp_row = tk.Frame(parent, bg=PANEL)
        sp_row.pack(fill='x', pady=(8, 0))
        self.custom_sp_var = tk.StringVar(value='9999')
        tk.Entry(
            sp_row,
            textvariable=self.custom_sp_var,
            width=8,
            bg='#171a21',
            fg=TEXT,
            insertbackground=TEXT,
            relief='flat',
            font=('Microsoft YaHei UI', 10),
            justify='center',
        ).pack(side='left', fill='x', expand=True)
        ttk.Button(
            sp_row,
            text='技能点',
            command=self.custom_sp,
        ).pack(side='right', padx=(6, 0))

        gold_row = tk.Frame(parent, bg=PANEL)
        gold_row.pack(fill='x', pady=(8, 0))
        ttk.Button(
            gold_row,
            text='金钱最大 99999999',
            command=lambda: self.edit_save(['gold=99999999']),
        ).pack(fill='x')

        item_label = tk.Label(
            parent,
            text='背包物品（菜单里选中的会自动跟过来）',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 9),
        ).pack(anchor='w', pady=(10, 4))
        self.item_combo = ttk.Combobox(
            parent,
            state='readonly',
        )
        self._fill_item_combo()
        self.item_combo.pack(fill='x')
        self.item_combo.bind(
            '<<ComboboxSelected>>',
            lambda *_: setattr(self, 'item_follow', False),
        )

        item_row = tk.Frame(parent, bg=PANEL)
        item_row.pack(fill='x', pady=(8, 0))
        self.item_count_var = tk.StringVar(value='99')
        tk.Entry(
            item_row,
            textvariable=self.item_count_var,
            width=8,
            bg='#171a21',
            fg=TEXT,
            insertbackground=TEXT,
            relief='flat',
            font=('Microsoft YaHei UI', 10),
            justify='center',
        ).pack(side='left', fill='x', expand=True)
        ttk.Button(
            item_row,
            text='改数量',
            command=self.edit_item,
        ).pack(side='right', padx=(6, 0))


        ttk.Button(
            parent,
            text='全部物品 99',
            command=lambda: self.edit_save(['item=all:99']),
        ).pack(fill='x', pady=(8, 0))

        ttk.Button(
            parent,
            text='全部拉满（含 SP/金钱/物品）',
            style='Accent.TButton',
            command=lambda: self.edit_save(
                [
                    'stamina=9999',
                    'max=9999',
                    'action=9999',
                    'money=99999',
                    'memory=9999',
                    'sp=9999',
                    'gold=99999999',
                    'item=all:99',
                    '1=9999',
                    '3=9999',
                    '5=9999',
                    '26=9999',
                    '157=9999',
                    '158=9999',
                    '159=9999',
                ]
            ),
        ).pack(fill='x', pady=(8, 0))
        tk.Label(
            parent,
            text='存档修改后重进游戏读档才显示，会自动备份。',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 9),
            justify='left',
            wraplength=300,
        ).pack(anchor='w', pady=(8, 0))

    def _fill_item_combo(self):
        names = [f"{item_id} {name}" for item_id, name in self.item_names.items()]
        self.item_combo['values'] = names
        if names:
            self.item_combo.set(names[0])

    def _selected_item_id(self):
        text = self.item_combo.get()
        if not text:
            return None
        first = text.split(' ', 1)[0]
        return int(first) if first.isdigit() else None

    def _build_custom_panel(self, parent):
        self._title(parent, '自定义数值（实时生效）')
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill='x', pady=(8, 0))
        self.custom_id_var = tk.StringVar(value='行动点')
        ttk.Combobox(
            row,
            textvariable=self.custom_id_var,
            values=list(self.CUSTOM_IDS.keys()),
            state='readonly',
            width=14,
        ).pack(side='left')
        self.custom_value_var = tk.StringVar(value='9999')
        tk.Entry(
            row,
            textvariable=self.custom_value_var,
            width=12,
            bg='#171a21',
            fg=TEXT,
            insertbackground=TEXT,
            relief='flat',
            font=('Microsoft YaHei UI', 10),
            justify='center',
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            row,
            text='写入',
            command=self.custom_write,
        ).pack(side='left', padx=(8, 0))
        ttk.Button(
            row,
            text='锁定',
            command=self.custom_freeze,
        ).pack(side='left', padx=(6, 0))
        tk.Label(
            parent,
            text='选项目、填任意整数，写入立即生效；锁定会持续保持。',
            bg=PANEL,
            fg=MUTED,
            font=('Microsoft YaHei UI', 9),
        ).pack(anchor='w', pady=(8, 0))

    def _log(self, text):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg[0]
                if kind == 'connected':
                    _, pid, handle, base, vals, gold_slot = msg
                    self.handle = handle
                    self.base = base
                    self.gold_slot = gold_slot
                    self.game_status.set(f'已连接游戏（PID {pid}）')
                    self.locate_status.set('数值表已识别')
                    self._log('已连接，数值位置识别完成。')
                    self._show_values(vals)
                    self.refresh_actor()
                elif kind == 'log':
                    self._log(msg[1])
                elif kind == 'error':
                    self.game_status.set('未连接')
                    self.locate_status.set(msg[1])
                    self._log(msg[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _show_values(self, vals):
        for var_id, value in vals.items():
            if value is not None and var_id in self.value_vars:
                self.value_vars[var_id].set(str(value))

    def connect_game(self):
        self.game_status.set('正在寻找游戏...')
        self.locate_status.set('')
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def choose_game_root(self):
        path = filedialog.askdirectory(title='选择“夏日狂想曲”游戏目录')
        if not path:
            return
        root = Path(path)
        if not save_utils._is_game_root(root):
            self._log('这个目录不是有效的夏日狂想曲游戏目录。')
            return
        self.game_root = root
        self.item_names = save_utils.load_item_names(root)
        self._fill_item_combo()
        self._log(f'游戏目录已设为：{root}')
        self.connect_game()

    def _connect_worker(self):
        try:
            pid = locator.find_game_pid()
            if pid is None:
                self.msg_queue.put(
                    ('error', '没找到游戏，请先打开游戏并进入存档。')
                )
                return
            handle = mt.open_process(pid)
            if not handle:
                self.msg_queue.put(
                    ('error', '读不到游戏内存，请用管理员身份打开本程序。')
                )
                return
            templates = save_utils.load_templates(self.game_root)
            expected = templates.get('length') if templates else None
            candidate = locator.find_best_candidate(
                handle, expected_length=expected, templates=templates
            )
            if candidate is None:
                mt.kernel32.CloseHandle(handle)
                self.msg_queue.put(
                    ('error', '游戏开着，但没能自动识别数值，重进存档后再试一次。')
                )
                return
            base, vals = candidate
            gold_slot = locator.find_party_gold_slot(handle, base)
            self.msg_queue.put(('connected', pid, handle, base, vals, gold_slot))
        except Exception as exc:
            self.msg_queue.put(('error', f'连接出错：{exc}'))

    def _ready(self):
        if not self.handle or self.base is None:
            self._log('还没连上游戏，先点重新连接。')
            return False
        return True

    def _write(self, var_id, value):
        if not self._ready():
            return False
        ok = locator.write_var(self.handle, self.base, var_id, value)
        self._log(f'已写入：{var_id} = {value}' if ok else '写入失败')
        return ok

    def _freeze(self, var_id, value):
        if not self._ready():
            return
        addr = self.base + locator.ELEMENT_BASE + 4 * var_id
        self.freezer.add(self.handle, addr, int(value) << 1 & 0xFFFFFFFF, 'u32')
        self._log(f'已锁定：{var_id} = {value}')

    def refill(self):
        if not self._ready():
            return
        max_value = locator.read_var(self.handle, self.base, 320)
        target = max_value if isinstance(max_value, (int, float)) and max_value > 0 else 9999
        self._write(27, int(target))

    def freeze_stamina(self):
        self._freeze(27, 9999)

    def money(self):
        if not self._ready():
            return
        self._write(23, 99999)
        if self.gold_slot:
            ok = locator.write_party_gold(self.handle, self.gold_slot, 99999)
            self._log('真实金钱也已写入' if ok else '真实金钱写入失败')
        else:
            self._log('没找到真实金钱位置，请用存档修改金钱最大。')

    def memory(self):
        self._write(28, 9999)

    def action_boost(self):
        self._write(65, 9999)

    def freeze_action(self):
        self._freeze(65, 9999)

    def lust_boost(self):
        self._write(26, 9999)

    def freeze_lust(self):
        self._freeze(26, 9999)

    def time_plus(self):
        if not self._ready():
            return
        current = locator.read_var(self.handle, self.base, 39)
        value = 1 if current is None or int(current) >= 5 else int(current) + 1
        self._write(39, value)

    def time_minus(self):
        if not self._ready():
            return
        current = locator.read_var(self.handle, self.base, 39)
        value = 5 if current is None or int(current) <= 1 else int(current) - 1
        self._write(39, value)

    def time_set(self, value):
        self._write(39, value)

    def freeze_time(self):
        if not self._ready():
            return
        current = locator.read_var(self.handle, self.base, 39)
        day = locator.read_var(self.handle, self.base, 59)
        if current is not None:
            self._freeze(39, int(current))
        if day is not None:
            self._freeze(59, int(day))
        self._log('时间带和日期已一起锁定。')

    def day_plus(self):
        if not self._ready():
            return
        current = locator.read_var(self.handle, self.base, 59)
        value = 30 if current is None or int(current) >= 30 else int(current) + 1
        if int(current or 1) >= 30:
            self._log('日期已经是第 30 天了。')
            return
        self._write(59, value)

    def day_minus(self):
        if not self._ready():
            return
        current = locator.read_var(self.handle, self.base, 59)
        value = 1 if current is None else max(1, int(current) - 1)
        if int(current or 1) <= 1:
            self._log('日期已经是第 1 天了。')
            return
        self._write(59, value)

    def freeze_day(self):
        if not self._ready():
            return
        current = locator.read_var(self.handle, self.base, 59)
        if current is not None:
            self._freeze(59, int(current))

    def mega_boost(self):
        for var_id, value in [
            (23, 99999),
            (27, 9999),
            (28, 9999),
            (65, 9999),
            (26, 9999),
            (1, 9999),
            (3, 9999),
            (5, 9999),
            (157, 9999),
            (158, 9999),
            (159, 9999),
        ]:
            self._write(var_id, value)
        if self.gold_slot:
            locator.write_party_gold(self.handle, self.gold_slot, 99999)

    def unfreeze_all(self):
        self.freezer.remove(remove_all=True)
        self._log('已解除所有锁定。')

    def actor_write_aff(self):
        if not self._ready():
            return
        _, aff_id, _, _ = self._actor_ids()
        try:
            value = int(self.actor_custom_aff.get().strip())
        except ValueError:
            self._log('好感值请输入整数。')
            return
        self._write(aff_id, value)

    def actor_freeze_aff(self):
        if not self._ready():
            return
        _, aff_id, _, _ = self._actor_ids()
        try:
            value = int(self.actor_custom_aff.get().strip())
        except ValueError:
            self._log('好感值请输入整数。')
            return
        self._freeze(aff_id, value)

    def actor_boost_aff(self):
        if not self._ready():
            return
        _, aff_id, _, _ = self._actor_ids()
        self._write(aff_id, 9999)

    def actor_write_task(self):
        if not self._ready():
            return
        _, _, _, task_id = self._actor_ids()
        try:
            value = int(self.actor_custom_task.get().strip())
        except ValueError:
            self._log('课题值请输入整数。')
            return
        self._write(task_id, value)

    def actor_boost_task(self):
        if not self._ready():
            return
        _, _, _, task_id = self._actor_ids()
        self._write(task_id, 9999)

    def _custom_target(self):
        var_id = self.CUSTOM_IDS.get(self.custom_id_var.get())
        try:
            value = int(self.custom_value_var.get().strip())
        except ValueError:
            self._log('自定义数值请输入整数。')
            return None
        return var_id, value

    def custom_write(self):
        target = self._custom_target()
        if target:
            self._write(target[0], target[1])

    def custom_freeze(self):
        target = self._custom_target()
        if target:
            self._freeze(target[0], target[1])

    def custom_sp(self):
        try:
            value = int(self.custom_sp_var.get().strip())
        except ValueError:
            self._log('技能点请输入整数。')
            return
        self.edit_save([f'sp={value}'])

    def edit_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            self._log('请先选择一个物品。')
            return
        try:
            count = int(self.item_count_var.get().strip())
        except ValueError:
            self._log('物品数量请输入整数。')
            return
        self.edit_save([f'item={item_id}:{count}'])


    def edit_save(self, edits):
        if not self.game_root:
            self._log('还没找到游戏目录，请先点“游戏目录”选择。')
            return
        slot = 1 if self.slot_var.get().startswith('1') else 2
        threading.Thread(
            target=self._save_worker,
            args=(slot, list(edits)),
            daemon=True,
        ).start()

    def _save_worker(self, slot, edits):
        try:
            save_utils.edit_save(self.game_root, slot, edits)
            self.msg_queue.put(
                ('log', '存档已修改，重进游戏读档即可看到（已自动备份）。')
            )
        except Exception as exc:
            self.msg_queue.put(('log', f'存档修改出错：{exc}'))

    def refresh_values(self):
        if self.handle and self.base is not None:
            for var_id in locator.VAR_IDS:
                value = locator.read_var(self.handle, self.base, var_id)
                if value is not None and var_id in self.value_vars:
                    self.value_vars[var_id].set(str(value))
            self.refresh_actor()
            self._follow_selected_item()
        self.after(1200, self.refresh_values)

    def _follow_selected_item(self):
        if not self.item_follow or not self.item_names:
            return
        item_id = locator.read_var(self.handle, self.base, 80)
        if isinstance(item_id, (int, float)) and int(item_id) > 0:
            item_id = int(item_id)
            name = self.item_names.get(item_id)
            if name:
                self.item_combo.set(f'{item_id} {name}')

    def on_close(self):
        self.freezer.stop()
        if self.handle:
            mt.kernel32.CloseHandle(self.handle)
        self.destroy()


if __name__ == '__main__':
    TrainerApp().mainloop()
