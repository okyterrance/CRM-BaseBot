#!/usr/bin/env python
"""把看板上「客户」关联空着、但客户现在已经登记了的行补挂上。

    uv run python scripts/relink_board.py            # 预演：只数一数会补几行
    uv run python scripts/relink_board.py --apply    # 真补

每天的导入（import_daily_incremental.py）已经会顺手做这件事。这个脚本是给「刚登记完
客户，今天就想在 Base 里看到他以前的交易」用的，不用等明天。

为什么会空着：关联只在交易写进看板的那一刻挂一次。客户晚登记，他以前的交易就一直空着
（右边的渠道编号、渠道名称、分佣比例、本笔佣金全空），不会自己补上。
只补空的，已经挂上的一律不动。逻辑在 ``crm_basebot.pipeline.board.relink_missing``。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from crm_basebot.domain import schema  # noqa: E402
from crm_basebot.lark.bitable import BitableClient  # noqa: E402
from crm_basebot.lark.values import PrecisionLossError, link_ids, to_uid  # noqa: E402
from crm_basebot.pipeline import board  # noqa: E402
from crm_basebot.startup import load_settings, require_settings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="补挂看板上空着的客户关联")
    parser.add_argument("--apply", action="store_true", help="真补；不加则只预演")
    args = parser.parse_args(argv)

    settings = load_settings()
    require_settings(settings, "LARK_BASE_APP_TOKEN", "TABLE_CLIENT", "TABLE_DAILY_BOARD")
    bitable = BitableClient(settings.base_app_token)
    links = board.client_links(bitable, settings.table_client)

    if not args.apply:
        users: set[str] = set()
        rows = 0
        for record in bitable.iter_records(
            settings.table_daily_board,
            field_names=[schema.BOARD_CLIENT_UID, schema.BOARD_CLIENT_LINK],
        ):
            if link_ids(record.fields.get(schema.BOARD_CLIENT_LINK)):
                continue
            try:
                uid = to_uid(record.fields.get(schema.BOARD_CLIENT_UID))
            except PrecisionLossError:
                continue
            if uid and uid in links:
                rows += 1
                users.add(uid)
        print(f"会补 {rows} 行（{len(users)} 个客户）。")
        print("（预演，没写。确认无误后加 --apply）")
        return 0

    done = board.relink_missing(bitable, settings.table_daily_board, links)
    print(f"补好了 {done} 行。去 Base 的「{schema.TABLE_DAILY_BOARD_NAME}」看右边那几列。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
