# AutoDL 会话 46638：环境、数据与复现实验

> 历史会话说明：46638 已不可连接。2026-09-06 当前入口为 43850，但该实例未挂载本文件所述的8月完整数据盘。当前状态请先读 `docs/autodl-current-state-2026-09-06.zh-CN.md`，不要直接照本文件假设 SECOND-CC 与后期 artifacts 已存在。

## 1. 登录

```powershell
ssh -p 46638 root@connect.bjb1.seetacloud.com
```

本机已配置公钥免密登录。SSH 配置或文档中不要记录私钥、AutoDL 密码或访问令牌。

## 2. 学术资源加速

仅在需要访问 GitHub、Hugging Face 等学术资源时执行：

```bash
source /etc/network_turbo
```

当前 SECOND-CC 数据和 GLiNER 依赖已经下载完成，常规复现实验不需要再次联网。

## 3. 项目与环境

```bash
cd /root/autodl-tmp/MGA
```

MGA / Parser 环境：

```bash
source /root/autodl-tmp/conda-envs/mga/bin/activate
export PYTHONPATH=/root/autodl-tmp/MGA/src
```

SegEarth-OV-3 环境：

```bash
source /root/autodl-tmp/conda-envs/segearth-ov3/bin/activate
export PYTHONPATH=/root/autodl-tmp/MGA/src
```

SegEarth-OV-3：

- 仓库：`/root/autodl-tmp/third_party/SegEarth-OV-3`
- 权重：`/root/autodl-tmp/third_party/SegEarth-OV-3/weights/sam3/sam3.pt`

## 4. SECOND-CC 数据

- 压缩包：`/root/autodl-tmp/datasets/SECOND-CC/SECOND-CC-AUG.zip`
- 解压目录：`/root/autodl-tmp/datasets/SECOND-CC/extracted/SECOND-CC-AUG`
- MD5：`ca930ddb819d68a797938b940d1711f1`
- 200 场景事实图：`/root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1`

检查数据：

```bash
md5sum /root/autodl-tmp/datasets/SECOND-CC/SECOND-CC-AUG.zip
find /root/autodl-tmp/datasets/SECOND-CC/extracted/SECOND-CC-AUG/test/sem/A \
  -maxdepth 1 -type f | wc -l
```

预期：

- MD5 与上述值一致；
- 测试集语义标签 A 为 1227 张。

## 5. 跑一条/小批量测试

先激活 SegEarth 环境：

```bash
source /root/autodl-tmp/conda-envs/segearth-ov3/bin/activate
cd /root/autodl-tmp/MGA
export PYTHONPATH=/root/autodl-tmp/MGA/src
```

复用正式缓存跑 1 个场景：

```bash
python scripts/run_with_class_map_file.py \
  --script scripts/run_semantic_evidence_experiments_v3.py \
  --class-map-file configs/semantic_class_maps/second_cc_v2.json -- \
  --samples /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evaluation_samples.jsonl \
  --output-dir /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/recheck-one \
  --cache-dir /root/autodl-tmp/mga-cache/segearth-ov3-secondcc-200-v3 \
  --hidden-entities "tree,low vegetation,water" \
  --max-scenes 1
```

该命令会输出四组方法的汇总。因为缓存已经存在，单场景检查不需要重新运行 SegEarth。

若要强制重新分割测试，请使用一个新的、明确命名的缓存目录，不要覆盖正式缓存：

```bash
--cache-dir /root/autodl-tmp/mga-cache/segearth-ov3-secondcc-debug
```

## 6. 重新生成可视化

```bash
python scripts/render_semantic_evidence_visualizations.py \
  --samples /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evaluation_samples.jsonl \
  --cache-dir /root/autodl-tmp/mga-cache/segearth-ov3-secondcc-200-v3 \
  --output-dir /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evidence-v3/visualizations \
  --class-map-file configs/semantic_class_maps/second_cc_v2.json \
  --max-scenes 200 \
  --overview-limit 24
```

逐场景图只保存在服务器；本地只保留 `overview.png` 和 `manifest.json`。

## 7. Parser v3 复现

```bash
source /root/autodl-tmp/conda-envs/mga/bin/activate
cd /root/autodl-tmp/MGA
export PYTHONPATH=/root/autodl-tmp/MGA/src
export HF_HOME=/root/autodl-tmp/cache/huggingface
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

python scripts/run_with_class_map_file.py \
  --script scripts/evaluate_semantic_parser_v2.py \
  --class-map-file configs/semantic_class_maps/second_cc_v2.json -- \
  --samples /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/parser_all_samples.jsonl \
  --surface-map-file configs/parser_surface_forms/second_cc_v3.json \
  --output /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/parser_report_v3.json \
  --model-name urchade/gliner_small-v2.1 \
  --threshold 0.30 \
  --device cuda
```

## 8. 服务器关机前检查

```bash
test -f /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evidence-v3/summary.json
test -f /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evidence-v3/bootstrap_summary.json
test -f /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evidence-v3/visualizations/overview.png
find /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/evidence-v3/visualizations/per_scene \
  -maxdepth 1 -type f -name '*.png' | wc -l
```

预期三个 `test` 均成功，逐场景图数量为 200。确认本地汇总文件哈希一致后再关机。
