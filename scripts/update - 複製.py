#!/usr/bin/env python3
"""
MAO Lottery：一次更新今彩539、大樂透、加州天天樂。
放置位置：MAO_Lottery/scripts/update.py
資料輸出：MAO_Lottery/data/*.json
"""
import json
import re
import sys
import time
from datetime import datetime, date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import truststore
truststore.inject_into_ssl()

# update.py 放在 scripts/，所以 parents[1] 就是專案根目錄。
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TAIWAN_TZ = ZoneInfo("Asia/Taipei")

TAIWAN_API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery"
FANTASY5_SOURCE_URL = "https://fantasy-5.com/california/past-numbers"

TAIWAN_GAMES = {
    "539": {
        "endpoint": "Daily539Result",
        "key": "daily539Res",
        "main_count": 5,
        "has_special": False,
    },
    "lotto649": {
        "endpoint": "Lotto649Result",
        "key": "lotto649Res",
        "main_count": 6,
        "has_special": True,
    },
}

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def read_existing_records(path, key="period"):
    """讀取既有 JSON；讀取失敗時拋錯，避免意外覆蓋舊歷史。"""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    result = {}
    for row in records:
        identity = row.get(key) or row.get("date")
        if identity:
            result[str(identity)] = row
    return result


def save_payload(path, payload):
    """先寫暫存檔，再取代正式檔，避免中途寫入造成 JSON 損毀。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def taiwan_month_list():
    now = datetime.now(TAIWAN_TZ)
    year, month = now.year, now.month
    months = []
    for _ in range(2):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return months


def fetch_taiwan_month(endpoint, month):
    query = urlencode({"month": month, "pageSize": 500})
    url = f"{TAIWAN_API_BASE}/{endpoint}?{query}"
    request = Request(url, headers={
        "User-Agent": "MAO-Lottery/1.0",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("rtCode") != 0:
        raise RuntimeError(f"台彩 API 回傳錯誤：{payload.get('rtMsg')}")
    return payload


def normalize_taiwan_record(item, config):
    raw_numbers = item.get("drawNumberSize") or []
    main_count = config["main_count"]
    if len(raw_numbers) < main_count:
        return None

    draw_date = str(item.get("lotteryDate", ""))[:10]
    period = str(item.get("period", ""))
    if not draw_date or not period:
        return None

    record = {
        "date": draw_date,
        "period": period,
        "numbers": [int(n) for n in raw_numbers[:main_count]],
    }
    if config["has_special"] and len(raw_numbers) >= 7:
        record["specialNumber"] = int(raw_numbers[6])
    return record


def update_taiwan_game(game_id, config):
    print(f"\n[{game_id}] 更新台灣彩券官方資料")
    target = DATA_DIR / f"{game_id}.json"

    # 先讀舊檔。若舊檔損毀，停止此遊戲更新，不覆蓋舊資料。
    old_by_period = read_existing_records(target, key="period")
    months = taiwan_month_list()
    print("同步月份：", ", ".join(months))

    fetched_count = 0
    for month in months:
        payload = fetch_taiwan_month(config["endpoint"], month)
        items = payload.get("content", {}).get(config["key"], [])
        for item in items:
            record = normalize_taiwan_record(item, config)
            if record:
                old_by_period[record["period"]] = record
                fetched_count += 1
        print(f"  {month}：API 回傳 {len(items)} 筆")
        time.sleep(0.3)

    records = sorted(
        old_by_period.values(),
        key=lambda row: (row.get("date", ""), row.get("period", "")),
        reverse=True,
    )
    output = {
        "updatedAt": datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "records": records,
    }
    save_payload(target, output)
    print(f"完成：本次整理 {fetched_count} 筆，歷史累計 {len(records)} 筆")
    print("最新資料：", records[0] if records else "目前沒有紀錄")
    return len(records)


class Fantasy5Parser(HTMLParser):
    """解析第三方 Fantasy 5 歷史頁面上的日期與五個號碼。"""

    def __init__(self):
        super().__init__()
        self.records = []
        self.in_anchor = False
        self.anchor_text = []
        self.current_date = None
        self.in_li = False
        self.li_text = []
        self.pending_numbers = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.in_anchor = True
            self.anchor_text = []
        elif tag == "li" and self.current_date:
            self.in_li = True
            self.li_text = []

    def handle_data(self, data):
        if self.in_anchor:
            self.anchor_text.append(data)
        if self.in_li:
            self.li_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_anchor:
            text = " ".join(" ".join(self.anchor_text).split())
            match = re.fullmatch(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s+(\d{4})",
                text,
            )
            if match:
                month_name, day_text, year_text = match.groups()
                self.current_date = date(
                    int(year_text), MONTHS[month_name], int(day_text)
                )
                self.pending_numbers = []
            self.in_anchor = False
            self.anchor_text = []

        elif tag == "li" and self.in_li:
            text = " ".join(" ".join(self.li_text).split())
            if re.fullmatch(r"\d{1,2}", text):
                number = int(text)
                if 1 <= number <= 39:
                    self.pending_numbers.append(number)
                    if len(self.pending_numbers) == 5:
                        if len(set(self.pending_numbers)) == 5:
                            # 網站日期是加州當地日期；本網站統一顯示台灣日期。
                            taiwan_date = self.current_date + timedelta(days=1)
                            self.records.append({
                                "date": taiwan_date.isoformat(),
                                "period": "",
                                "numbers": sorted(self.pending_numbers),
                                "source": "fantasy-5.com",
                                "sourceLocalDate": self.current_date.isoformat(),
                            })
                        self.current_date = None
                        self.pending_numbers = []
            self.in_li = False
            self.li_text = []


def fetch_fantasy5_records():
    request = Request(FANTASY5_SOURCE_URL, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(request, timeout=35) as response:
        html = response.read().decode("utf-8", errors="replace")
        print("第三方歷史頁 HTTP：", response.status)

    parser = Fantasy5Parser()
    parser.feed(html)

    unique = {}
    for row in parser.records:
        unique[row["date"]] = row
    records = sorted(unique.values(), key=lambda row: row["date"], reverse=True)

    if not records:
        raise RuntimeError(
            f"沒有解析到 Fantasy 5 紀錄；HTML 長度 {len(html)}，"
            "可能是來源網站改版或阻擋自動讀取。"
        )

    for row in records:
        nums = row["numbers"]
        if len(nums) != 5 or len(set(nums)) != 5 or min(nums) < 1 or max(nums) > 39:
            raise RuntimeError(f"Fantasy 5 號碼驗證失敗：{row}")
    return records


def update_fantasy5():
    print("\n[fantasy5] 更新加州天天樂資料（第三方來源）")
    target = DATA_DIR / "fantasy5.json"

    old_payload = {"records": []}
    if target.exists():
        old_payload = json.loads(target.read_text(encoding="utf-8"))

    old_records = old_payload.get("records", [])

    # 舊測試版曾將加州日期直接存入 date。只在尚未標記台灣日期時轉換一次。
    if old_payload.get("dateConvention") == "Asia/Taipei":
        migrated_records = [dict(row) for row in old_records]
        migrated = False
    else:
        migrated_records = []
        for old_row in old_records:
            row = dict(old_row)
            old_date_text = row.get("date")
            if old_date_text:
                old_date = date.fromisoformat(old_date_text)
                row.setdefault("sourceLocalDate", old_date.isoformat())
                row["date"] = (old_date + timedelta(days=1)).isoformat()
            migrated_records.append(row)
        migrated = bool(old_records)

    fresh_records = fetch_fantasy5_records()

    # 以台灣顯示日期合併，保留來源網站最近 180 天以外的舊歷史。
    merged = {
        row["date"]: row
        for row in migrated_records
        if row.get("date")
    }
    for row in fresh_records:
        merged[row["date"]] = row

    records = sorted(merged.values(), key=lambda row: row["date"], reverse=True)
    output = {
        "updatedAt": datetime.now(TAIWAN_TZ).isoformat(timespec="seconds"),
        "source": FANTASY5_SOURCE_URL,
        "sourceType": "third-party; verify against California Lottery",
        "dateConvention": "Asia/Taipei",
        "dateNote": "date 為台灣顯示日期；sourceLocalDate 為加州當地開獎日期",
        "records": records,
    }
    save_payload(target, output)

    print(f"本次抓取：{len(fresh_records)} 筆")
    print("舊資料首次日期轉換：", "是" if migrated else "否（已是台灣日期或沒有舊資料）")
    print(f"合併後累計：{len(records)} 筆")
    print("最新台灣日期：", records[0]["date"])
    print("對應加州日期：", records[0].get("sourceLocalDate", ""))
    print("最新號碼：", records[0]["numbers"])
    print("已保存：", target)
    print("提醒：加州資料來自第三方網站，正式使用仍應與加州官方結果核對。")
    return len(records)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    # 三個來源分開處理：其中一個失敗，不阻止另外兩個更新。
    for game_id, config in TAIWAN_GAMES.items():
        try:
            update_taiwan_game(game_id, config)
        except Exception as exc:
            failures.append((game_id, str(exc)))
            print(f"[失敗] {game_id}：{exc}")

    try:
        update_fantasy5()
    except Exception as exc:
        failures.append(("fantasy5", str(exc)))
        print(f"[失敗] fantasy5：{exc}")

    print("\n========== 更新總結 ==========")
    if failures:
        print(f"有 {len(failures)} 項更新失敗：")
        for game_id, message in failures:
            print(f"- {game_id}: {message}")
        print("成功的資料已各自保存；失敗項目的舊 JSON 不會被清空。")
        return 1

    print("三種彩券資料全部更新完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
