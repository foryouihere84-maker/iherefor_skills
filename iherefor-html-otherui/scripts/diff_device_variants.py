#!/usr/bin/env python3
"""从两份设备稿的 design_document 里 diff 同名「容器/控件」的几何尺寸差异，
自动生成 ``adaptiveLayout.sizeVariants[]``。

背景：同一设计在 Lanhu 里同时有 ``xx`` 与 ``xx-iPad`` 两份稿时，这两份稿是**两套并列的
独立参考** —— iPad 组件的宽、高照 ``xx-iPad`` 稿自身取值，与 ``xx`` 稿没有派生关系。
跨设备的几何尺寸差异必须逐档声明在 ``adaptiveLayout.sizeVariants[]``，``audit_adaptive.py``
的 ``sizeInvariance`` 才按分档白名单放行（且只许跨设备分档，同设备内仍然强制相等）。

本脚本做的事就是把「人工读两份稿、一个一个比宽高、手写 sizeVariants」这个机械活自动化：
按**图层名**对齐两份稿，diff 出宽或高不同的同名「容器/形状/组」图层，产出可直接粘贴进
实现计划 ``adaptiveLayout.sizeVariants`` 的 JSON 数组。

**边界（刻意不 diff 的东西）：**
- **文本层**（``type == "text"`` 或带 ``style.typography``）—— 字号/字体差异走 ``typeFacts``
  溯源，不进 sizeVariants（``sizeInvariance`` 只审计几何宽高）。
- **位置（x / y）** —— sizeVariants 只管宽高；位置由位置轴（贴父/居中/比例）管。
- **半径、描边、阴影** —— 样式恒量，不进 sizeVariants。

输入是 ``lanhu_get_design_document``（depth 建议 99）的返回体 JSON，各落一份盘后传入：
    python3 scripts/diff_device_variants.py \\
        --phone <xx.document.json> --tablet <xx-iPad.document.json>

输出缺省打印到 stdout（人类可读），``--output`` 写 JSON（可直接粘进 sizeVariants）。

匹配策略：按**图层名**对齐，同名多实例只取第一个（报告里标注实例数）。名字在两份稿里
不一致（设计师改了名）的图层不会被 diff 出来 —— 那是人工核对的事，本脚本不做模糊匹配，
避免把两个不相干的图层错误配对。

退出码：0 = 成功（含「无差异」）；2 = 用法或读取错误。
"""
import argparse
import json
import sys
from pathlib import Path

# 尺寸差异小于这个阈值视为「同一值」，不产出分档条目（吸收 1x/2x 换算的末位浮点噪声）。
EPSILON = 0.5

# 分档条目的 values key：用「设备 + 代表性宽度采样」命名，与 windowSamples[].id 约定一致。
# phone 稿取 compact 竖屏、tablet 稿取 regular 竖屏作为两个代表采样。
DEFAULT_PHONE_SAMPLE = "phone-compact"
DEFAULT_TABLET_SAMPLE = "tablet-regular-portrait"


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _has_typography(layer):
    style = layer.get("style")
    if isinstance(style, dict) and style.get("typography"):
        return True
    return layer.get("type") == "text"


def collect_containers(layers):
    """展开图层树，收集「非文本、有几何尺寸」的容器层。

    返回 ``{name: {"count": N, "width": w, "height": h, "type": t}}`` —— 同名多实例只保留
    第一个，并记下实例数，供调用方判断「这个名字是不是会歧义」。
    """
    out = {}

    def walk(nodes):
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            name = node.get("name")
            rect = node.get("rect")
            if (name and isinstance(rect, dict)
                    and _is_number(rect.get("width")) and _is_number(rect.get("height"))
                    and not _has_typography(node)):
                width = float(rect["width"])
                height = float(rect["height"])
                existing = out.get(name)
                if existing is None:
                    out[name] = {"count": 1, "width": width, "height": height,
                                 "type": node.get("type") or "unknown"}
                else:
                    existing["count"] += 1
            walk(node.get("children"))

    walk(layers)
    return out


def diff(phone, tablet, phone_sample, tablet_sample, phone_name, tablet_name,
         phone_image_id, tablet_image_id):
    """按图层名对齐 diff，返回 (entries, report)。"""
    entries = []
    report = {"phone": {"name": phone_name, "layers": len(phone)},
              "tablet": {"name": tablet_name, "layers": len(tablet)},
              "compared": 0, "differs": 0, "onlyPhone": [], "onlyTablet": [],
              "diffs": []}
    common = sorted(set(phone) & set(tablet))
    report["compared"] = len(common)
    report["onlyPhone"] = sorted(set(phone) - set(tablet))
    report["onlyTablet"] = sorted(set(tablet) - set(phone))

    for name in common:
        p = phone[name]
        t = tablet[name]
        dw = abs(t["width"] - p["width"])
        dh = abs(t["height"] - p["height"])
        if dw <= EPSILON and dh <= EPSILON:
            continue
        entries.append({
            "region": name,
            "basis": f"{phone_name} + {tablet_name} 双稿"
                     f"（tablet 稿 image_id={tablet_image_id}）",
            "values": {
                phone_sample: {"width": round(p["width"], 2),
                               "height": round(p["height"], 2)},
                tablet_sample: {"width": round(t["width"], 2),
                                "height": round(t["height"], 2)},
            },
            "why": (f"{tablet_name} 稿中该容器宽高为 "
                    f"{round(t['width'], 2)}×{round(t['height'], 2)}，"
                    f"照 tablet 稿取值，与 {phone_name} 稿无派生关系"),
        })
        report["diffs"].append({
            "region": name, "dw": round(dw, 2), "dh": round(dh, 2),
            "phoneInstances": p["count"], "tabletInstances": t["count"],
        })
        report["differs"] += 1
    return entries, report


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="从两份设备稿 diff 尺寸差异，生成 adaptiveLayout.sizeVariants[]")
    ap.add_argument("--phone", dest="phone", required=True,
                    help="phone 稿的 design_document JSON（xx.document.json）")
    ap.add_argument("--tablet", dest="tablet", required=True,
                    help="tablet 稿的 design_document JSON（xx-iPad.document.json）")
    ap.add_argument("--phone-sample", dest="phone_sample", default=DEFAULT_PHONE_SAMPLE,
                    help=f"phone 稿对应的采样 id（缺省 {DEFAULT_PHONE_SAMPLE}）")
    ap.add_argument("--tablet-sample", dest="tablet_sample", default=DEFAULT_TABLET_SAMPLE,
                    help=f"tablet 稿对应的采样 id（缺省 {DEFAULT_TABLET_SAMPLE}）")
    ap.add_argument("--output", help="把 sizeVariants 数组写入该路径（JSON）")
    ap.add_argument("--max-entries", dest="max_entries", type=int, default=0,
                    help="最多产出多少条（0 表示不限制）")
    args = ap.parse_args(argv)

    phone_path, tablet_path = Path(args.phone), Path(args.tablet)
    data = {}
    for label, path in (("phone", phone_path), ("tablet", tablet_path)):
        try:
            data[label] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"找不到 {label} 稿的 document：{path}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"{label} 稿的 document 不是合法 JSON：{exc}", file=sys.stderr)
            return 2

    phone_name = data["phone"].get("name") or phone_path.stem
    tablet_name = data["tablet"].get("name") or tablet_path.stem
    phone_image_id = data["phone"].get("imageId") or ""
    tablet_image_id = data["tablet"].get("imageId") or ""

    phone_containers = collect_containers(data["phone"].get("layers") or [])
    tablet_containers = collect_containers(data["tablet"].get("layers") or [])

    entries, report = diff(phone_containers, tablet_containers,
                           args.phone_sample, args.tablet_sample,
                           phone_name, tablet_name,
                           phone_image_id, tablet_image_id)

    if args.max_entries and len(entries) > args.max_entries:
        entries = entries[:args.max_entries]

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
        print(f"sizeVariants 写入了 {out}（{len(entries)} 条）")
        return 0

    # 人类可读摘要
    print(f"phone 稿 {report['phone']['name']}：{report['phone']['layers']} 个容器")
    print(f"tablet 稿 {report['tablet']['name']}：{report['tablet']['layers']} 个容器")
    print(f"同名容器 {report['compared']} 个，尺寸有差异 {report['differs']} 个")
    if report["onlyPhone"]:
        print(f"仅 phone 稿有（tablet 稿缺）: {report['onlyPhone']}")
    if report["onlyTablet"]:
        print(f"仅 tablet 稿有（phone 稿缺）: {report['onlyTablet']}")
    if not entries:
        print("没有需要分档的尺寸差异")
        return 0
    print("尺寸有差异的同名容器：")
    for item in report["diffs"]:
        extra = ""
        if item["phoneInstances"] > 1 or item["tabletInstances"] > 1:
            extra = f"  [实例数 phone {item['phoneInstances']}/tablet {item['tabletInstances']}，只取首个]"
        print(f"  - {item['region']}: 宽差 {item['dw']}pt / 高差 {item['dh']}pt{extra}")
    print("sizeVariants 片段（可直接粘进 adaptiveLayout.sizeVariants）：")
    print(json.dumps(entries, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
