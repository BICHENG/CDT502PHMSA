# 第三章计算复核包

本包保存本轮计算代码、运行所需的分析表、冻结参数及逐份报告预测。解压后，在解压目录执行下列命令，即可核对已有结果，无需下载原始数据或重新拟合模型。

```powershell
python -m pip install -r requirements.txt
python work/p322_completion/models/verify_artifacts.py
```

使用 Python 3.12；原运行环境为 Python 3.12.13。依赖版本见 `requirements.txt`，仅需 NumPy、pandas、SciPy、scikit-learn 和 threadpoolctl；安装工具会解析它们的依赖。

## 直接复核的范围

验证程序从保存的系数、中位数、标准化参数、类别编码、聚类中心和校准参数重新计算分数，核对 50 组逐份预测：16 种输入在早期和后期各一组、6 种聚类表示在早期和后期各一组、3 种校准方法在早期和后期各一组。另核对早期输入选择、112 份后期报告的真实结局与分类数量、原四方法的 AP 和 Brier，以及 9 个既有输入文件的 SHA-256。

通过标准为最大分数绝对误差小于 `1e-12`，最终分类为 TP=8、FP=21、FN=7、TN=76。验证结果写入 `work/p322_completion/models/verification.json`，逐组误差写入同目录的 `saved_parameter_readback.csv`。验证程序不拟合模型，不重新选择输入、校准方法或分类门槛。

## 完整重跑所需的公开原始数据

原始 PHMSA 下载包含报告联系人姓名、邮箱、电话和叙述，因此未随本包分发。分析表仅保留报告编号、运营商编号、设施属性、时间和结局等分析字段。本包的 `research/inputs/sources.json` 仅摘录原来源清单中的主数据条目，删去其他数据和文档条目，原始数据校验值保持不变。

- 官方资料说明：[PHMSA 事故数据](https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data)。
- 原研究使用的官方附件：[DOT 数据目录中的固定 ZIP 附件](https://datahub.transportation.gov/api/views/27nc-rsge/files/fba42a19-f78d-44c9-9a76-4bacfc15fba0?content=true)，来源清单记录于 2026-11-04 重新下载。
- 保存位置：`research/inputs/data/incident_primary.zip`，需先创建 `research/inputs/data/`。
- 文件大小：1,566,027 字节。
- SHA-256：`89c21d2ea6f5cb8ff6daad6ac60160608671a7b49c218bf9f917bfb88a2ce5a1`。

可用 PowerShell 的 `Get-FileHash research/inputs/data/incident_primary.zip -Algorithm SHA256` 检查。程序会再次验证该哈希。若官方附件变化，请寻找同一校验值的存档版本；直接采用更新的数据快照不属于本包的原结果复现。

取得匹配的原始 ZIP 后，按下列顺序完整重跑。输出覆盖解压目录内的本轮计算产物，宜保留原 ZIP 作为参照。

```powershell
python work/p322_completion/models/complete_models.py
python work/p322_completion/models/supplement_checks.py
python work/p322_completion/models/verify_artifacts.py
```

`complete_models.py` 重建 693 份主管道及主管道阀报告，开展 16 种输入比较、621 份完整物理资料的聚类对照、校准、条件关联和后期误差分析。早期输入比较为 337 份拟合、244 份验证，选定后用 581 份重拟合，后期评价 112 份。聚类对照分别使用 299 份最早完整记录训练，以及 521 份早期完整记录的既有冻结中心，后期评价 100 份。

`supplement_checks.py` 从已存分数计算配对区间及原始／校准分数的错误数量，并整理原四方法参照；它不拟合预测模型。该脚本本身无需原始 ZIP，但须保留本包的代码、输入表和冻结结果。

## 随机设置和继承范围

| 项目 | 固定设置或继承方式 |
|---|---|
| 本轮输入模型 | L2 逻辑回归，`C=0.2`；种子 `20261111`；预处理仅在相应训练记录拟合 |
| 配对区间 | 按运营商配对重抽样 2,000 次；种子 `20261111`；条件于冻结模型 |
| 条件关联区间 | 训练运营商重抽样并重新拟合 1,000 次；种子 `20261111` |
| 聚类 | K-means 三组；种子 `20261109`，`n_init=50`；早期验证中心重新拟合，最终 521 份早期记录的中心从既有结果继承，并逐份核对归组 |
| 钢塑比较 | 继承既有共同、交互及分开模型的后期预测、指标和配对区间；本轮不重新拟合钢塑模型。本包可核对这些继承文件的原始哈希 |
| 原四方法 | 继承 1,550 份原研究中 264 份后期报告的常数、部件经验、原 GLM、随机森林分数；本包重算 AP、Brier，不重新拟合这四种方法。原 GLM 与本轮 L2 逻辑回归属于不同分析 |

输入选择容差、校准选择和分类门槛规则见 `work/p322_completion/models/protocol.md`；冻结选择见 `selection_frozen.json`。完整重跑保留原有早期选择规则，不根据后期结果重选。运行时间戳会更新，不能用整个输出 JSON 的字节相等代替数值复核。

## 文件与打包

`MANIFEST.json` 列出随包文件的相对路径、字节数和 SHA-256。除来源清单摘录及本 README、依赖清单、打包脚本外，其余文件均逐字节复制自现有分析产物。保留了原相对目录，代码中的导入与路径不作改写。分析目录名中的 `course_sweep` 和 `course_visual_lab` 是既有计算路径；包内只取相应 CSV／JSON，不含课程文件、教师材料、浏览器记录或原始联络人资料。

在原工作区执行 `python work/p322_completion/repro/build_bundle.py`，或在解压目录执行 `python build_bundle.py`，可重新生成 `p322_reproducibility.zip`。打包器使用明确文件白名单，并在临时解压目录运行 `verify_artifacts.py`。验证报告另存为打包器所在目录的 `bundle_verification.json`。本次打包验收只运行此项保存结果复核，未重新运行完整实验。
