# -*- coding: utf-8 -*-
"""
HOT CAR ANALYZER by bohangyang PATSMET V1.1 2026.08
AC History Data Analyzer

Features:
  1. Drag & drop a CSV data file onto this program (or HOTCAR_Analyzer.bat) to open it.
  2. Reads config.json located in the same directory:
       - column mapping (time / fresh air / return air)
       - the two alarm thresholds (target temp / trigger temp)
       - output language: en = English console & charts, zh = Chinese console & charts
  3. Automatically lists every date found in the data file; select ranges such as 1-5, 1,3,5 or all.
  4. Marks the return-air max temperature point every 20 minutes (star) and exports an HTML
     chart for each selected day.
  5. When generation finishes, press Enter to open the generated chart(s) and close the window.
"""

import json
import os
import re
import sys
import webbrowser

import pandas as pd
import plotly.graph_objects as go

APP_NAME = "HOT CAR ANALYZER by bohangyang PATSMET V1.1 2026.08"


def app_dir():
    """Directory of the exe when frozen by PyInstaller, otherwise the script directory.

    When packaged with PyInstaller, __file__ points inside a temp extraction dir
    (_MEIxxxx for --onefile) or the bundled _internal folder (onedir), so config.json
    next to the exe would never be found. sys.executable always points to the exe,
    so its folder is the right place to keep the editable config.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def config_path():
    """config.json always lives next to the exe (or next to the script when running source)."""
    return os.path.join(app_dir(), "config.json")

DEFAULT_CONFIG = {
    "columns": {"time_column": 0, "fresh_air_column": 27, "return_air_column": 28},
    "csv": {"skip_rows": 1, "encoding": "auto"},
    "alarms": {"target_temp": 23.0, "trigger_temp": 28.5},
    "sensor_ranges": {
        "fresh_air_min": 10, "fresh_air_max": 50,
        "return_air_min": 10, "return_air_max": 40,
    },
    "analysis": {"downsample_every": 10, "max_interval_minutes": 20},
    "language": "en",
    "output_dir": "",
}

# ------------------------------------------------------------------ console text (per language)
TXT = {
    "zh": {
        "found_days": "数据文件中找到以下日期：",
        "prompt": "请输入要导出的日期编号（支持 1-5、1,3,5 或 all）：",
        "invalid": "输入无效，请重新输入。",
        "empty": "没有可导出的日期。",
        "processing": "正在处理 {d} ...",
        "chart_saved": "  图表已保存：{p}",
        "opened": "  已打开：{p}",
        "open_fail": "  [警告] 无法自动打开文件：{p}",
        "final_open": "按回车键打开生成的文件并退出……",
        "rows": "采样数据点数：{n}",
        "fresh": "新风温度：",
        "return": "回风温度：",
        "min": "  最低：{v:.1f}°C",
        "max": "  最高：{v:.1f}°C",
        "avg": "  平均：{v:.1f}°C",
        "cnt_high": "回风温度 >{t}°C 的点数：{n}",
        "cnt_mid": "回风温度 {a}-{b}°C 的点数：{n}",
        "cnt_low": "回风温度 <{a}°C 的点数：{n}",
        "no_data_day": "  [{d}] 过滤后无有效数据，已跳过。",
        "no_file": "未选择数据文件，程序退出。",
        "file_not_found": "文件不存在：{p}",
        "read_error": "文件读取失败：{e}",
        "config_warn": "[警告] 配置文件读取失败（{e}），已使用默认配置。",
        "config_created": "[提示] 已生成默认配置文件：{p}",
        "lang_warn": "[警告] language 只能为 zh 或 en，已使用 en。",
        "swap_warn": "[警告] target_temp（{a}）应小于 trigger_temp（{b}），已自动交换。",
        "col_error": "列配置错误：{e}",
        "time_error": "无法解析时间列，请检查 config.json 中的 time_column。",
        "no_dates": "数据文件中没有日期记录。",
        "done": "全部完成！",
        "banner_lang": "  语言：{lang} | 目标温度：{a}°C | 触发温度：{b}°C | 最高点间隔：{m} 分钟",
        "data_file": "数据文件：{p}",
        "col_info": "时间列：'{t}' | 新风温度列：'{f}' | 回风温度列：'{r}'",
        "process_error": "[错误] 处理 {d} 失败：{e}",
        "select_title": "选择空调数据文件 (CSV)",
        "csv_files": "CSV 文件",
        "all_files": "所有文件",
        "enter_path": "请输入数据文件路径（或直接将文件拖入窗口）：",
        "wait_exit_msg": "按回车键退出……",
    },
    "en": {
        "found_days": "Days found in the data file:",
        "prompt": "Enter day numbers to export (e.g. 1-5, 1,3,5 or all): ",
        "invalid": "Invalid input, please try again.",
        "empty": "No days to export.",
        "processing": "Processing {d} ...",
        "chart_saved": "  Chart saved: {p}",
        "opened": "  Opened: {p}",
        "open_fail": "  [Warning] Could not auto-open the file: {p}",
        "final_open": "Press Enter to open the generated file(s) and exit...",
        "rows": "Sampled data points: {n}",
        "fresh": "Fresh air temp:",
        "return": "Return air temp:",
        "min": "  Min: {v:.1f}°C",
        "max": "  Max: {v:.1f}°C",
        "avg": "  Avg: {v:.1f}°C",
        "cnt_high": "Return air >{t}°C points: {n}",
        "cnt_mid": "Return air {a}-{b}°C points: {n}",
        "cnt_low": "Return air <{a}°C points: {n}",
        "no_data_day": "  [{d}] No valid data after filtering, skipped.",
        "no_file": "No data file selected, exiting.",
        "file_not_found": "File not found: {p}",
        "read_error": "Failed to read file: {e}",
        "config_warn": "[Warning] Failed to read config file ({e}), using defaults.",
        "config_created": "[Info] Default config file created: {p}",
        "lang_warn": "[Warning] language must be 'zh' or 'en', using 'en'.",
        "swap_warn": "[Warning] target_temp ({a}) should be lower than trigger_temp ({b}); swapped automatically.",
        "col_error": "Column error: {e}",
        "time_error": "Unable to parse the time column, please check 'time_column' in config.json.",
        "no_dates": "No date records found in the data file.",
        "done": "All done!",
        "banner_lang": "  Language: {lang} | Target Temp: {a}°C | Trigger Temp: {b}°C | Max interval: {m} min",
        "data_file": "Data file: {p}",
        "col_info": "Time column: '{t}' | Fresh air column: '{f}' | Return air column: '{r}'",
        "process_error": "[Error] Failed to process {d}: {e}",
        "select_title": "Select AC data file (CSV)",
        "csv_files": "CSV files",
        "all_files": "All files",
        "enter_path": "Enter the data file path (or drag the file into this window): ",
        "wait_exit_msg": "Press Enter to exit...",
    },
}

# ------------------------------------------------------------- chart label languages
L = {
    "zh": {
        "title": "<b>{f} - {d} 新风/回风温度变化曲线</b>",
        "subtitle": "每{n}行取样 | 红: >{t}°C | 黄: {a}-{b}°C | ⭐: 每{m}分钟回风温度最高点",
        "x_axis": "时间",
        "y_axis": "温度 (°C)",
        "fresh_legend": "新风温度",
        "return_legend": "回风温度",
        "scatter_high": "回风温度 >{t}°C (红)",
        "scatter_mid": "回风温度 {a}-{b}°C (黄)",
        "scatter_low": "回风温度 <{a}°C (绿)",
        "star": "⭐ 每{m}分钟回风温度最高点",
        "star_hover": "⭐ 每{m}分钟最高回风温度<br>时间: {t}<br>回风温度: {v:.1f}°C",
        "pt_hover": "时间: {t}<br>新风温度: {f:.1f}°C<br>回风温度: {r:.1f}°C",
        "zone_alarm": "报警区域 (> {t}°C)",
        "zone_throttle": "节流区域 ({a}~{b}°C)",
        "zone_target": "目标区域 (< {a}°C)",
        "line_target": "目标温度 {a}°C",
        "line_trigger": "触发温度 {b}°C",
    },
    "en": {
        "title": "<b>{f} - {d} Fresh/Return Air Temperature</b>",
        "subtitle": "Sample every {n} rows | Red: >{t}°C | Yellow: {a}-{b}°C | ⭐: {m}-min max return air temp",
        "x_axis": "Time",
        "y_axis": "Temperature (°C)",
        "fresh_legend": "Fresh Air Temp",
        "return_legend": "Return Air Temp",
        "scatter_high": "Return air >{t}°C (red)",
        "scatter_mid": "Return air {a}-{b}°C (yellow)",
        "scatter_low": "Return air <{a}°C (green)",
        "star": "⭐ {m}-min max return air temp",
        "star_hover": "⭐ {m}-min max return air temp<br>Time: {t}<br>Return air: {v:.1f}°C",
        "pt_hover": "Time: {t}<br>Fresh air: {f:.1f}°C<br>Return air: {r:.1f}°C",
        "zone_alarm": "Alarm Zone (> {t}°C)",
        "zone_throttle": "Throttle Zone ({a}~{b}°C)",
        "zone_target": "Target Zone (< {a}°C)",
        "line_target": "Target Temp {a}°C",
        "line_trigger": "Trigger Temp {b}°C",
    },
}

# Matches a trailing date-like token, e.g. "10.8.2026", "2026.08.10", "20260810"
_DATE_TAIL = re.compile(r"^\d{1,4}[./-]\d{1,2}[./-]\d{1,4}$|^\d{8}$")


def display_name(base_name):
    """Strip a trailing date token from the file name for the chart title."""
    parts = base_name.split()
    while parts and _DATE_TAIL.match(parts[-1]):
        parts.pop()
    return " ".join(parts).strip() or base_name


# ------------------------------------------------------------------ config
def deep_merge(base, extra):
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    cfg = deep_merge(DEFAULT_CONFIG, {})
    cfg_file = config_path()
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = deep_merge(cfg, json.load(f))
        except Exception as e:
            print(TXT["en"]["config_warn"].format(e=e))
    else:
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            print(TXT["en"]["config_created"].format(p=cfg_file))
        except Exception:
            pass
    lang = cfg.get("language", "en")
    if lang not in ("zh", "en"):
        print(TXT["en"]["lang_warn"])
        lang = "en"
    cfg["language"] = lang
    return cfg


# ------------------------------------------------------------------ helpers
def resolve_column(df, spec, label):
    """Resolve the configured column (0-based index or name) to the real column name."""
    if isinstance(spec, int):
        if 0 <= spec < len(df.columns):
            return df.columns[spec]
        raise ValueError(
            f"Index {spec} out of range (file has {len(df.columns)} columns); "
            f"check '{label}' in config.json."
        )
    s = str(spec)
    for col in df.columns:
        if col == s:
            return col
    for col in df.columns:
        if str(col).strip() == s:
            return col
    low = s.strip().lower()
    for col in df.columns:
        if str(col).strip().lower() == low:
            return col
    raise ValueError(
        f"Column '{s}' ({label}) not found. Columns in the file: {list(df.columns)}\n"
        f"Fix the column mapping in config.json."
    )


def read_csv(path, csv_cfg):
    skip = int(csv_cfg.get("skip_rows", 1))
    enc_cfg = csv_cfg.get("encoding", "auto")
    encodings = ["utf-8", "gbk", "gb18030", "latin-1"] if enc_cfg == "auto" else [enc_cfg]
    errs = []
    for enc in encodings:
        try:
            return pd.read_csv(path, skiprows=skip, low_memory=False, encoding=enc)
        except Exception as e:
            errs.append(f"{enc}: {e}")
    raise RuntimeError(" | ".join(errs))


def parse_time_col(s):
    t = pd.to_datetime(s, errors="coerce")
    if t.isna().all():
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                    "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M"):
            t = pd.to_datetime(s, format=fmt, errors="coerce")
            if not t.isna().all():
                break
    return t


def parse_selection(text, n):
    """Parse inputs like 1-5 / 1,3,5 / all into a 1-based index list."""
    text = (text or "").strip().lower()
    if text in ("", "all", "*"):
        return list(range(1, n + 1))
    idxs = set()
    try:
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = int(a), int(b)
                if a > b:
                    a, b = b, a
                idxs.update(range(a, b + 1))
            else:
                idxs.add(int(part))
    except ValueError:
        return None
    for i in idxs:
        if not (1 <= i <= n):
            return None
    return sorted(idxs)


def choose_days(days, lang):
    t = TXT[lang]
    print(t["found_days"])
    for i, d in enumerate(days, 1):
        print(f"  [{i}] {d}")
    while True:
        try:
            sel = input(t["prompt"]).strip()
        except EOFError:
            return []
        idxs = parse_selection(sel, len(days))
        if idxs is None:
            print(t["invalid"])
            continue
        return [days[i - 1] for i in idxs]


def choose_file(lang):
    """Open a file dialog when no file is passed on the command line."""
    t = TXT[lang]
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title=t["select_title"],
            filetypes=[(t["csv_files"], "*.csv"), (t["all_files"], "*.*")])
        root.destroy()
        return path or None
    except Exception:
        try:
            p = input(t["enter_path"]).strip().strip('"')
            return p or None
        except EOFError:
            return None


def wait_exit(lang):
    try:
        input("\n" + TXT[lang]["wait_exit_msg"])
    except EOFError:
        pass


def open_file(path, lang):
    """Open a generated file with the default application (browser for HTML)."""
    t = TXT[lang]
    try:
        if sys.platform.startswith("win"):
            os.startfile(os.path.abspath(path))  # Windows: open with default program
        else:
            webbrowser.open("file://" + os.path.abspath(path))
        print(t["opened"].format(p=path))
    except Exception:
        try:
            webbrowser.open("file://" + os.path.abspath(path))
            print(t["opened"].format(p=path))
        except Exception:
            print(t["open_fail"].format(p=path))


def final_open_and_exit(chart_paths, lang):
    """After all files are generated: press Enter to open them, then the window closes."""
    if not chart_paths:
        wait_exit(lang)
        return
    try:
        input("\n" + TXT[lang]["final_open"])
    except EOFError:
        return
    for p in chart_paths:
        open_file(p, lang)


# ------------------------------------------------------------------ chart
def make_chart(sampled, max_pts, base_name, day_str, cfg, lang, a, b):
    t = L[lang]
    down = int(cfg["analysis"]["downsample_every"])
    mins = int(cfg["analysis"]["max_interval_minutes"])

    times = sampled["_time"]
    fresh = sampled["_fresh"]
    ret = sampled["_ret"]
    y_top = max(fresh.max(), ret.max()) + 1
    y_bot = min(fresh.min(), ret.min()) - 1

    fig = go.Figure()

    # Alarm zone (red, above trigger temp)
    fig.add_hrect(y0=b, y1=y_top, fillcolor="rgba(255,0,0,0.08)", line_width=0,
                  annotation_text=t["zone_alarm"].format(t=b),
                  annotation_position="top left",
                  annotation=dict(font_size=12, font_color="red"))
    # Throttle zone (yellow, target temp ~ trigger temp)
    fig.add_hrect(y0=a, y1=b, fillcolor="rgba(255,215,0,0.10)", line_width=0,
                  annotation_text=t["zone_throttle"].format(a=a, b=b),
                  annotation_position="top left",
                  annotation=dict(font_size=12, font_color="goldenrod"))
    # Target zone (green, below target temp)
    fig.add_hrect(y0=y_bot, y1=a, fillcolor="rgba(0,128,0,0.06)", line_width=0,
                  annotation_text=t["zone_target"].format(a=a),
                  annotation_position="bottom left",
                  annotation=dict(font_size=12, font_color="green"))

    hover = [t["pt_hover"].format(t=tt.strftime("%H:%M:%S"), f=f, r=r)
             for tt, f, r in zip(times, fresh, ret)]

    # Fresh air temperature line
    fig.add_trace(go.Scatter(
        x=times, y=fresh, mode="lines", name=t["fresh_legend"],
        line=dict(color="rgba(100,149,237,0.7)", width=1.5),
        hovertemplate=hover, hoverinfo="text"))
    # Return air temperature line
    fig.add_trace(go.Scatter(
        x=times, y=ret, mode="lines", name=t["return_legend"],
        line=dict(color="rgba(70,70,70,0.5)", width=1.5),
        hovertemplate=hover, hoverinfo="text"))

    # Return air scatter points, colored by zone
    for color, label_key, cond in [
        ("red", "scatter_high", ret > b),
        ("gold", "scatter_mid", (ret >= a) & (ret <= b)),
        ("green", "scatter_low", ret < a),
    ]:
        mask = cond.values
        if mask.any():
            fig.add_trace(go.Scatter(
                x=times[mask], y=ret[mask], mode="markers",
                name=t[label_key].format(a=a, b=b, t=b),
                marker=dict(color=color, size=5, line=dict(width=0.5, color="white")),
                hovertext=[hover[i] for i in range(len(hover)) if mask[i]],
                hoverinfo="text", showlegend=True))

    # 20-minute return-air max points (star)
    fig.add_trace(go.Scatter(
        x=max_pts["_time"], y=max_pts["_ret"], mode="markers+text",
        name=t["star"].format(m=mins),
        marker=dict(color="orange", size=12, symbol="star",
                    line=dict(width=1.5, color="black")),
        text=[f"{v:.1f}" for v in max_pts["_ret"]],
        textposition="top center", textfont=dict(size=9, color="black"),
        hovertext=[t["star_hover"].format(m=mins, t=tt.strftime("%H:%M:%S"), v=v)
                   for tt, v in zip(max_pts["_time"], max_pts["_ret"])],
        hoverinfo="text", showlegend=True))

    # The two threshold lines
    fig.add_hline(y=a, line_dash="dash", line_color="green", line_width=2,
                  annotation_text=t["line_target"].format(a=a),
                  annotation_position="top right",
                  annotation=dict(font_size=13, font_color="green"))
    fig.add_hline(y=b, line_dash="dash", line_color="red", line_width=2,
                  annotation_text=t["line_trigger"].format(b=b),
                  annotation_position="top right",
                  annotation=dict(font_size=13, font_color="red"))

    # Brand line, hugging the top-left edge of the plot area
    fig.add_annotation(
        text=APP_NAME, xref="paper", yref="paper",
        x=0.0, y=1.0, xanchor="left", yanchor="bottom",
        showarrow=False, font=dict(size=9, color="gray"))

    title_text = (t["title"].format(f=display_name(base_name), d=day_str)
                  + "<br><sup>" + t["subtitle"].format(n=down, t=b, a=a, b=b, m=mins) + "</sup>")

    fig.update_layout(
        title=dict(text=title_text, x=0.5, font=dict(size=16)),
        xaxis=dict(title=t["x_axis"], tickformat="%H:%M", dtick=3600000,
                   tickangle=-45, gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(title=t["y_axis"], gridcolor="rgba(200,200,200,0.3)",
                   range=[y_bot - 1, y_top + 1]),
        legend=dict(orientation="v", x=1.02, y=0.5,
                    xanchor="left", yanchor="middle", font=dict(size=11)),
        plot_bgcolor="white", paper_bgcolor="white",
        width=1500, height=760,
        margin=dict(l=60, r=210, t=100, b=100),
    )
    return fig


# ------------------------------------------------------------------ per-day processing
def process_day(df, day_str, time_col, f_col, r_col, cfg, lang,
                out_dir, base_name, a, b):
    t = TXT[lang]
    mins = int(cfg["analysis"]["max_interval_minutes"])
    down = int(cfg["analysis"]["downsample_every"])
    fr = cfg["sensor_ranges"]

    day_df = df[df["_time"].dt.strftime("%Y/%m/%d") == day_str].copy()
    day_df[f_col] = pd.to_numeric(day_df[f_col], errors="coerce")
    day_df[r_col] = pd.to_numeric(day_df[r_col], errors="coerce")
    day_df = day_df.dropna(subset=[f_col, r_col])
    day_df = day_df[
        (day_df[f_col] >= fr["fresh_air_min"]) & (day_df[f_col] <= fr["fresh_air_max"]) &
        (day_df[r_col] >= fr["return_air_min"]) & (day_df[r_col] <= fr["return_air_max"])
    ]
    if day_df.empty:
        print(t["no_data_day"].format(d=day_str))
        return

    sampled = day_df.iloc[::down].copy()
    sampled["_fresh"] = sampled[f_col]
    sampled["_ret"] = sampled[r_col]

    # Return-air max point per N minutes
    day_df["_bin"] = day_df["_time"].dt.floor(f"{mins}min")
    max_pts = day_df.loc[day_df.groupby("_bin")[r_col].idxmax()].sort_values("_time").copy()
    max_pts["_ret"] = max_pts[r_col]

    ymd = day_str.replace("/", "")
    out_base = os.path.join(out_dir, f"{base_name}_{ymd}")
    chart_path = out_base + "_chart.html"

    fig = make_chart(sampled, max_pts, base_name, day_str, cfg, lang, a, b)
    fig.write_html(chart_path, include_plotlyjs="cdn")

    print(t["processing"].format(d=day_str))
    print(t["chart_saved"].format(p=chart_path))

    fresh, ret = sampled["_fresh"], sampled["_ret"]
    print(t["rows"].format(n=len(sampled)))
    print(t["fresh"])
    print(t["min"].format(v=fresh.min()))
    print(t["max"].format(v=fresh.max()))
    print(t["avg"].format(v=fresh.mean()))
    print(t["return"])
    print(t["min"].format(v=ret.min()))
    print(t["max"].format(v=ret.max()))
    print(t["avg"].format(v=ret.mean()))
    print(t["cnt_high"].format(t=b, n=int((ret > b).sum())))
    print(t["cnt_mid"].format(a=a, b=b, n=int(((ret >= a) & (ret <= b)).sum())))
    print(t["cnt_low"].format(a=a, n=int((ret < a).sum())))
    return chart_path


# ------------------------------------------------------------------ main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    cfg = load_config()
    lang = cfg["language"]
    t = TXT[lang]
    a = float(cfg["alarms"].get("target_temp", 23.0))
    b = float(cfg["alarms"].get("trigger_temp", 28.5))
    if a >= b:
        print(t["swap_warn"].format(a=a, b=b))
        a, b = b, a
    mins = int(cfg["analysis"].get("max_interval_minutes", 20))

    print("=" * 62)
    print(f"  {APP_NAME}")
    print(t["banner_lang"].format(lang=lang, a=a, b=b, m=mins))
    print("=" * 62)

    # 1) Get the data file: drag & drop -> command line arg; otherwise dialog / manual input
    data_path = None
    if len(sys.argv) > 1:
        cand = sys.argv[1].strip().strip('"')
        if os.path.isfile(cand):
            data_path = cand
        else:
            print(t["file_not_found"].format(p=cand))
    if data_path is None:
        data_path = choose_file(lang)
    if not data_path:
        print(t["no_file"])
        wait_exit(lang)
        return 1

    print(t["data_file"].format(p=data_path))

    # 2) Read the CSV
    try:
        df = read_csv(data_path, cfg.get("csv", {}))
    except Exception as e:
        print(t["read_error"].format(e=e))
        wait_exit(lang)
        return 1
    df.columns = [str(c).strip() for c in df.columns]

    # 3) Resolve the column mapping
    col_cfg = cfg.get("columns", {})
    try:
        time_col = resolve_column(df, col_cfg.get("time_column", 0), "time_column")
        f_col = resolve_column(df, col_cfg.get("fresh_air_column", 27), "fresh_air_column")
        r_col = resolve_column(df, col_cfg.get("return_air_column", 28), "return_air_column")
    except ValueError as e:
        print(t["col_error"].format(e=e))
        wait_exit(lang)
        return 1
    print(t["col_info"].format(t=time_col, f=f_col, r=r_col))

    # 4) Parse time and list all dates
    df["_time"] = parse_time_col(df[time_col])
    df = df.dropna(subset=["_time"])
    if df.empty:
        print(t["time_error"])
        wait_exit(lang)
        return 1
    days = sorted(df["_time"].dt.strftime("%Y/%m/%d").unique())
    if not days:
        print(t["no_dates"])
        wait_exit(lang)
        return 1

    # 5) Select the dates to export (e.g. 1-5)
    selected = choose_days(days, lang)
    if not selected:
        print(t["empty"])
        wait_exit(lang)
        return 1

    out_dir = cfg.get("output_dir") or os.path.dirname(os.path.abspath(data_path))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(data_path))[0]

    # 6) Generate a chart for each selected day
    print("=" * 62)
    chart_paths = []
    for day in selected:
        try:
            p = process_day(df, day, time_col, f_col, r_col, cfg, lang,
                            out_dir, base_name, a, b)
            if p:
                chart_paths.append(p)
        except Exception as e:
            print(t["process_error"].format(d=day, e=e))
        print("-" * 62)
    print(t["done"])
    final_open_and_exit(chart_paths, lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
