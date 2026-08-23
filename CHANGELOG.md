# 更新日志

## [1.0.1] - 2026-08-23

### 修复

- **修复无法自动查找游戏进程的问题**：`locator.py` 中部分函数被误删（包括 `find_game_pid`、V8 变量读写、候选数组扫描等一整组内存定位逻辑），导致修改器连接游戏时报 `module 'locator' has no attribute 'find_game_pid'`。现已全部补回并重新打包。
  - 补回：`find_game_pid`、`read_var` / `write_var`、`smi_to_int`、`decode_tagged`、`_valid_array`、`_scan_by_length` / `_scan_by_max_stamina`、`find_best_candidate` 等
  - 重新打包 `SummerMemoriesTrainer.exe`

## [1.0.0] - 2026-08-23

### 新增

- 首次开源发布
- 实时内存修改：体力、行动点、金钱、回忆点、性欲、时间带、日期，支持写入 / 锁定 / 回满 / 一键 9999
- 人物数值修改：结衣、莉音、美雪的好感度、警戒度、课题/作业
- 自定义数值：任意项目写入 / 锁定，实时生效
- 存档修改：技能点 SP、金钱最大、背包物品数量、全部物品 99、全部拉满（重进游戏生效，自动备份存档）
- 自动定位游戏安装目录（Steam 常见路径 + 注册表 + libraryfolders.vdf）
