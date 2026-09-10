#!/usr/bin/env python3
"""Compare HTML reference and native-app screenshots without changing either input."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reference', required=True)
    ap.add_argument('--actual', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--threshold', type=int, default=8)
    args = ap.parse_args()
    ref = Image.open(args.reference).convert('RGBA')
    actual = Image.open(args.actual).convert('RGBA')
    result = {'schemaVersion': 1, 'reference': str(Path(args.reference).resolve()), 'actual': str(Path(args.actual).resolve()), 'threshold': args.threshold, 'status': 'pass'}
    if ref.size != actual.size:
        result.update({'status': 'fail', 'reason': 'size-mismatch', 'referenceSize': ref.size, 'actualSize': actual.size})
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2)); return 1
    diff = ImageChops.difference(ref, actual)
    pixels = diff.load(); changed = 0; total = ref.size[0] * ref.size[1]
    for y in range(ref.size[1]):
        for x in range(ref.size[0]):
            if max(pixels[x, y]) > args.threshold: changed += 1
    ratio = changed / total if total else 0
    result.update({'width': ref.size[0], 'height': ref.size[1], 'changedPixels': changed, 'totalPixels': total, 'changedRatio': ratio})
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
