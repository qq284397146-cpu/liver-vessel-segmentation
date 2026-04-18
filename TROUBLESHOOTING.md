# 踩坑记录

## 2026-04-18 | liver_vessels 模型权重缺失
**环境**：3D Slicer 5.10.0 + TotalSegmentator，Windows
**错误**：FileNotFoundError: ...Dataset008_HepaticVessel/...checkpoint_final.pth
**原因**：liver_vessels 是附加任务，需单独下载权重
**解决**：
```python
from totalsegmentator.download_pretrained_weights import download_pretrained_weights
download_pretrained_weights(8)
```
**耗时**：约10分钟排查

---

## 20xx-xx-xx | [下一个问题标题]
...
