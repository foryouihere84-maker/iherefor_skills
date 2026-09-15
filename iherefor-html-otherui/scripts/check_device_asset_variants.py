#!/usr/bin/env python3
"""对比两份设备稿（``xx`` 与 ``xx-iPad``）的资源目录，产出「必须按稿分档」的资源清单。

背景（血的教训）：同一设计在 Lanhu 里同时有 ``xx`` 与 ``xx-iPad`` 两份稿时，这两份稿的
资源是**两套独立文件**，不是同一张图换分辨率。实测「目的」页的手机稿 hero 是 123KB 的
393×365，iPad 稿是 231KB 的 810×396，md5 完全不同；返回按钮手机 32×32、iPad 44×44；
CTA 手机是灰、iPad 是蓝。**直接把手机稿的资源复用到 iPad 档，会得到低清、比例错误、
甚至颜色错的画面**（fill 差异主因），而且不会报错 —— 只有像素 diff 里的大面积填充差异
能暴露它，肉眼极易漏判。

所以「资源按稿分档」必须有一个**机器可执行的门**：逐字节比对两份稿同名资源的 md5，
md5 不同的就是**分档资源**，实现时各用各的、不得跨设备复用。这份清单就是判据 ——
凡是出现在清单里的资源，实现侧若手机与 iPad 共用了同一个语义名，即判违规。

边界（刻意不做的）：
- 不判「是否该分档」—— md5 不同只说明「不同文件」，可能只是状态栏 mock 图（两稿都
  不实现）。是否复用由实现侧的 resource-policy.json 声明 + 本清单交叉核对，本脚本只负
  责**把差异事实摆出来**，不做「该不该复用」的臆断。
- 只比对**同名**源文件（``img_4.png`` vs ``img_4.png``）。设计师改名、增删文件的差异，
  靠其它门（资源完整性）抓，本脚本不做模糊匹配，避免把不相干文件错配。

用法：
    python3 scripts/check_device_asset_variants.py \\
        --phone-dir <page>/source/img --tablet-dir <page>-ipad/source/img \\
        --output <run>/diff/asset-variants.json

退出码：0 = 成功（含「有 variant」也是 0，判违规由调用方结合实现侧声明决定）；
2 = 用法或读取错误。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:  # 没装 PIL 也能出 md5 清单，只是没有像素尺寸
    HAS_PIL = False


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _pixel_size(path):
    if not HAS_PIL:
        return None
    try:
        with Image.open(path) as im:
            return {"width": im.width, "height": im.height}
    except Exception:
        return None


def _ls_images(directory):
    """列出目录下的图片文件 → {name: abs_path}（只看 img_*.png 这类图片）。"""
    directory = Path(directory)
    result = {}
    if not directory.is_dir():
        return result
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            result[p.name] = p
    return result


def compare_asset_dirs(phone_dir, tablet_dir):
    phone = _ls_images(phone_dir)
    tablet = _ls_images(tablet_dir)

    variants = []
    phone_only = sorted(set(phone) - set(tablet))
    tablet_only = sorted(set(tablet) - set(phone))

    for name in sorted(set(phone) & set(tablet)):
        pm = _md5(phone[name])
        tm = _md5(tablet[name])
        if pm == tm:
            continue  # 逐字节相同 → 可安全共享，无需分档
        variants.append({
            "sourceName": name,
            "phone": {"md5": pm, "pixelSize": _pixel_size(phone[name]),
                      "bytes": phone[name].stat().st_size},
            "tablet": {"md5": tm, "pixelSize": _pixel_size(tablet[name]),
                       "bytes": tablet[name].stat().st_size},
        })

    return {
        "schemaVersion": 1,
        "phoneDir": str(phone_dir),
        "tabletDir": str(tablet_dir),
        "sameCount": len(set(phone) & set(tablet)) - len(variants),
        "variantCount": len(variants),
        "variants": variants,
        "phoneOnly": phone_only,
        "tabletOnly": tablet_only,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone-dir", required=True,
                        help="手机稿（xx）的 img 资源目录")
    parser.add_argument("--tablet-dir", required=True,
                        help="iPad 稿（xx-iPad）的 img 资源目录")
    parser.add_argument("--output", help="写 JSON 的路径；缺省打到 stdout")
    args = parser.parse_args(argv)

    payload = compare_asset_dirs(args.phone_dir, args.tablet_dir)

    out_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(out_text + "\n", encoding="utf-8")
        # stdout 输出人类可读摘要
        print(f"资源分档差异：{payload['variantCount']} 个分档、"
              f"{payload['sameCount']} 个可共享、"
              f"仅手机 {len(payload['phoneOnly'])}、仅 iPad {len(payload['tabletOnly'])}")
        for v in payload["variants"]:
            ps = v["phone"]["pixelSize"]
            ts = v["tablet"]["pixelSize"]
            print(f"  {v['sourceName']}: 手机 {ps} ({v['phone']['bytes']}B) "
                  f"vs iPad {ts} ({v['tablet']['bytes']}B) —— 必须分档")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
