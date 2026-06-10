TA 会在正式发布包中把约 70 张公开小样本图和 labels.csv 放在这里。

这些样例只用于本地自测和理解数据格式，不参与排行榜计分。排行榜分数来自服务器排行榜评测集上的 Macro-F1。

目录格式：

```text
bench/devset/images/xxx.jpg
bench/devset/labels.csv
```

labels.csv 格式：

```csv
filename,label
xxx.jpg,3
```
