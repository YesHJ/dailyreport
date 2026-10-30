#!/usr/bin/env python3
"""DingTalk daily-report fix (idempotent; run after bundle restore, before collect):
1. create /tmp/dingtalk/webhooks.yaml from config.yaml
2. generate_report.py: webhook fallback to config webhook_url
3. config.yaml: max_message_chars 4500 -> 6000
4. generate_report.py: GitHub details use Chinese summary (summary_cn), drop tag spam,
   show '能干什么' line when present
5. collect_github.py: fix glossary producing broken mixed-English ('智能体s', 'reference 库')
"""
import os, re, sys

base = "/tmp/ai-task"
cfg_path = os.path.join(base, "config.yaml")
gr_path = os.path.join(base, "scripts", "generate_report.py")
cg_path = os.path.join(base, "scripts", "collect_github.py")

# --- 1. Create webhooks.yaml from config.yaml dingtalk section ---
cfg = open(cfg_path, encoding="utf-8").read()
m_url = re.search(r'^\s*webhook_url:\s*"([^"]+)"', cfg, re.M)
m_grp = re.search(r'^\s*group:\s*"([^"]+)"', cfg, re.M)
if not m_url:
    print("PATCH_FAILED: no webhook_url in config.yaml"); sys.exit(1)
url = m_url.group(1)
group = m_grp.group(1) if m_grp else "AI群"

os.makedirs("/tmp/dingtalk", exist_ok=True)
wh_path = "/tmp/dingtalk/webhooks.yaml"
already = os.path.exists(wh_path) and url in open(wh_path, encoding="utf-8").read()
if not already:
    with open(wh_path, "w", encoding="utf-8") as f:
        f.write(f"""groups:
  {group}:
    name: "{group}"
    url: "{url}"
    aliases:
      - "{group}"
      - "{group.lower()}"
      - "AI"
""")
print("1) webhooks.yaml: OK")

# --- 2. Webhook fallback in generate_report.py ---
src = open(gr_path, encoding="utf-8").read()
if "FALLBACK_PATCH_APPLIED" in src:
    print("2) webhook fallback: already patched")
else:
    needle = "            webhook_url = get_webhook_by_group(webhooks_full, group)\n            if not webhook_url:\n"
    repl = ("            webhook_url = get_webhook_by_group(webhooks_full, group)\n"
            "            if not webhook_url:\n"
            "                # FALLBACK_PATCH_APPLIED\n"
            '                webhook_url = dt_cfg.get("webhook_url", "")\n'
            "            if not webhook_url:\n")
    if needle not in src:
        print("2) PATCH_FAILED: webhook anchor not found"); sys.exit(1)
    src = src.replace(needle, repl, 1)
    open(gr_path, "w", encoding="utf-8").write(src)
    print("2) webhook fallback: patched")

# --- 3. Raise max_message_chars ---
cfg_now = open(cfg_path, encoding="utf-8").read()
if "max_message_chars: 4500" in cfg_now:
    open(cfg_path, "w", encoding="utf-8").write(cfg_now.replace("max_message_chars: 4500", "max_message_chars: 6000"))
    print("3) config: max_message_chars 4500 -> 6000")
else:
    print("3) config: max_message_chars already raised")

# --- 4. GitHub detail block: Chinese summary + no tag spam + '能干什么' line ---
src = open(gr_path, encoding="utf-8").read()
if "CN_SUMMARY_PATCH_APPLIED" in src:
    print("4) report details: already patched")
else:
    # 4a. speed table uses Chinese short summary
    old_t = '        summary = _short(item.get("summary", "").split("(")[0].split("[")[0].strip(), 40)'
    new_t = ('        # CN_SUMMARY_PATCH_APPLIED\n'
             '        _cn = item.get("summary_cn") or ""\n'
             '        summary = _short(_cn if _cn else item.get("summary", "").split("(")[0].split("[")[0].strip(), 40)')
    # 4b. detail block
    old_d = '        summary_text = item.get("summary", "")\n        meta = item.get("metadata", {})'
    new_d = ('        # CN_SUMMARY_PATCH applied to detail\n'
             '        summary_text = item.get("summary_cn") or item.get("summary", "")\n'
             '        meta = item.get("metadata", {})')
    old_tag = ('        if topics:\n'
               '            lines.append(f"标签: {\' \'.join(f\'#{t}\' for t in topics[:5])}")')
    new_tag = ('        _use = item.get("use_case_cn") or ""\n'
               '        if _use:\n'
               '            lines.append(f"能干什么: {_use}")')
    for old, new in ((old_t, new_t), (old_d, new_d), (old_tag, new_tag)):
        if old not in src:
            print("4) PATCH_FAILED: report anchor not found:", old[:50]); sys.exit(1)
        src = src.replace(old, new, 1)
    # detail quote: allow longer Chinese text
    src = src.replace('lines.append(f"> {_short(summary_text, 120)}")',
                      'lines.append(f"> {_short(summary_text, 160)}")', 1)
    open(gr_path, "w", encoding="utf-8").write(src)
    print("4) report details: patched (中文简介 + 能干什么, 去掉标签行)")

# --- 5. Fix glossary artifacts in collect_github.py (only affects fallback text) ---
src = open(cg_path, encoding="utf-8").read()
if '"agents": "智能体"' not in src:
    src = src.replace('"agent": "智能体",', '"agents": "智能体",\n    "agent": "智能体",', 1)
    open(cg_path, "w", encoding="utf-8").write(src)
    print("5) collector glossary: patched")
else:
    print("5) collector glossary: already patched")

print("ALL PATCHES OK")
