"""一次性脱敏脚本 — 替换 P0 文件中的真实地名。"""
import os, json

BASE = r"D:\Projects\Urban_Industry_Assistant"

# 映射表（长串优先，避免部分匹配）
MAP = [
    ("杭州市桐庐县", "中国东南某县"),
    ("杭州桐庐", "中国东南某县"),
    ("桐庐县", "中国东南某县"),
    ("桐庐", "中国东南某县"),
    ("30 公里到杭州", "距省会城市约 30 公里"),
    ("距杭州", "距省会城市"),
    ("到杭州", "到省会城市"),
    ("钱塘江流域", "中国东南地区"),
    ("浙北", "中国东南地区"),
    ("浙西", "中国东南地区"),
    ("富春江镇", "城镇一"),
    ("富春江", "主要河流"),
    ("富春", "主要河流"),
    ("桐君街道", "街道一"),
    ("旧县街道", "街道二"),
    ("城南街道", "街道三"),
    ("凤川街道", "街道四"),
    ("横村镇", "城镇二"),
    ("江南镇", "城镇三"),
    ("分水镇", "城镇四"),
    ("瑶琳镇", "城镇五"),
    ("百江镇", "城镇六"),
    ("莪山畲族乡", "乡镇一"),
    ("钟山乡", "乡镇二"),
    ("新合乡", "乡镇三"),
    ("合村乡", "乡镇四"),
    ("Tonglu County", "East County"),
]

def replace_in_file(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    changed = False
    for old, new in MAP:
        if old in content:
            content = content.replace(old, new)
            changed = True
    if changed:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
    return changed

files = [
    "src/prompts/system_prompt.py",
    "src/services/policy_service.py",
    "src/services/eval_service.py",
    "src/services/gene_service.py",
    "src/api/config_routes.py",
    "src/api/map_routes.py",
    "src/main.py",
    "src/config.py",
    "static/index.html",
    "static/app.js",
]

for f in files:
    fpath = os.path.join(BASE, f)
    if os.path.exists(fpath):
        ok = replace_in_file(fpath)
        print("  " + ("OK" if ok else "--") + " " + f)

# XZQ geojson
geojson_map = {
    "桐君街道": "街道一", "旧县街道": "街道二",
    "城南街道": "街道三", "凤川街道": "街道四",
    "富春江镇": "城镇一", "横村镇": "城镇二",
    "江南镇": "城镇三", "分水镇": "城镇四",
    "瑶琳镇": "城镇五", "百江镇": "城镇六",
    "莪山畲族乡": "乡镇一", "钟山乡": "乡镇二",
    "新合乡": "乡镇三", "合村乡": "乡镇四",
}
geojson_path = os.path.join(BASE, "static", "XZQ_wgs84.geojson")
with open(geojson_path, 'r', encoding='utf-8') as f:
    d = json.load(f)
for feat in d["features"]:
    n = feat["properties"]["name"]
    feat["properties"]["name"] = geojson_map.get(n, n)
with open(geojson_path, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False)
print("  OK static/XZQ_wgs84.geojson (" + str(len(d['features'])) + " features)")

# PRD v2.0
prd_path = os.path.join(BASE, "specs", "src", "prd_v2.0.md")
if os.path.exists(prd_path):
    replace_in_file(prd_path)
    print("  OK specs/src/prd_v2.0.md")

# PPT
ppt_path = os.path.join(BASE, "outputs", "PPT_方案_城市用地价值评估与产业适配Agent.md")
if os.path.exists(ppt_path):
    replace_in_file(ppt_path)
    print("  OK PPT")

print("\nDone.")
