# 产物契约

## `ui-implementation-plan.json`

文件位置：`.ihereforUI/pages/<page-id>/plans/ui-implementation-plan.json`。旧的工程根目录位置仅兼容读取，不再作为多页面写入位置。

```json
{
  "schemaVersion": 1,
  "source": {
    "html": "...",
    "styles": [],
    "scripts": [],
    "assets": []
  },
  "target": {
    "platform": "ios",
    "framework": "swiftui",
    "language": "swift"
  },
  "referenceViewport": { "width": 393, "height": 852 },
  "canvasTransform": {
    "htmlCssPixels": { "width": 393, "height": 852 },
    "devicePixels": { "width": 1179, "height": 2556 },
    "scale": 3,
    "letterbox": { "x": 0, "y": 0 },
    "systemBars": { "strategy": "mixed", "top": 0, "bottom": 0 },
    "coordinateMapper": {"scaleX":1,"scaleY":1,"origin":{"x":0,"y":0},"letterbox":{"x":0,"y":0},"formula":"targetX=(lanhuX-letterboxX)*scaleX+originX; targetY=(lanhuY-letterboxY)*scaleY+originY; targetWidth=lanhuWidth*scaleX; targetHeight=lanhuHeight*scaleY"}
  },
  "regions": [
    {
      "id": "hero",
      "sourceSelectors": [".group_6"],
      "boundingBox": { "x": 0, "y": 0, "width": 393, "height": 320 },
      "resources": [],
      "styleFacts": {},
      "nativeMapping": ""
    }
  ],
  "imageVerification": [
    {
      "source": "img/img_1.png",
      "lanhuFrame": {"x": 157, "y": 22, "width": 201, "height": 201},
      "mappedFrame": {"x": 0, "y": 0, "width": 0, "height": 0},
      "contentMode": "scaleToFill",
      "naturalSize": {"width": 201, "height": 201},
      "actualFrameEvidence": "actual/image-frames.json"
    }
  ],
  "factSources": {
    "boundingBoxes": "page-facts.json",
    "computedStyles": "page-facts.json",
    "resourceMapping": "ui-implementation-plan.json",
    "diffEvidence": "diff/"
  },
  "components": [],
  "layoutMode": "canvas-overlay",
  "interactionCandidates": [],
  "resourcePolicy": "../runs/<run-id>/resource-policy.json",
  "unsupported": []
}
```

## `delivery-gate.json`

页面级文件位置：`.ihereforUI/pages/<page-id>/runs/<run-id>/review.json` 中记录本次证据，页面 `status.json` 汇总状态；项目级文件位置：`.ihereforUI/reports/delivery-gate.json`。

必须分别记录：

- `reference.status`
- `browser.status`
- `sourceAssets.status`
- `implementation.status`
- `build.status`
- `tests.status`
- `visualDiff.status`
- `unsupported.count`
- `deliveryReady`

任何一项为 `fail`、`not-run` 或存在未审查重大 `unsupported` 时，`deliveryReady` 必须为 `false`。
