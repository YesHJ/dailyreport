#!/usr/bin/env python3
"""DingTalk fix: create /tmp/dingtalk/webhooks.yaml from config.yaml and add
config webhook_url fallback to generate_report.py. Idempotent; run after restore."""
import os, re, sys

base = "/tmp/ai-task"
cfg_path = os.path.join(base, "config.yaml")
gr_path = os.path.join(base, "scripts", "generate_report.py")

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
print("webhooks.yaml:", "OK" if os.path.exists(wh_path) else "FAILED", wh_path)

# --- 2. Patch generate_report.py: fallback to config webhook_url ---
src = open(gr_path, encoding="utf-8").read()
if "FALLBACK_PATCH_APPLIED" in src:
    print("generate_report.py: already patched")
else:
    needle = "            webhook_url = get_webhook_by_group(webhooks_full, group)\n            if not webhook_url:\n"
    patch = (
        "            webhook_url = get_webhook_by_group(webhooks_full, group)\n"
        "            if not webhook_url:\n"
        "                # FALLBACK_PATCH_APPLIED\n"
        '                webhook_url = dt_cfg.get("webhook_url", "")\n'
        "            if not webhook_url:\n"
    )
    if needle not in src:
        print("PATCH_FAILED: anchor not found in generate_report.py"); sys.exit(1)
    open(gr_path, "w", encoding="utf-8").write(src.replace(needle, patch, 1))
    print("generate_report.py: patched (+config webhook_url fallback)")
# --- 3. Raise max_message_chars so the full report fits (idempotent) ---
cfg_now = open(cfg_path, encoding="utf-8").read()
if "max_message_chars: 4500" in cfg_now:
    open(cfg_path, "w", encoding="utf-8").write(cfg_now.replace("max_message_chars: 4500", "max_message_chars: 6000"))
    print("config.yaml: max_message_chars 4500 -> 6000")
else:
    print("config.yaml: max_message_chars already raised")
sys.exit(0)
