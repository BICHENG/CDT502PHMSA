# 资料来源 / Sources

研究采用美国管道与危险品安全管理局（PHMSA）公布的配气事故和年度管网资料。

- [事故数据与历史档案](https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data)
- [年度管网资料](https://www.phmsa.dot.gov/data-and-statistics/pipeline/gas-distribution-gas-gathering-gas-transmission-hazardous-liquids)
- [采用快照的来源地址、文件哈希与大小](data/sources.json)

<h2 id="snapshots">采用版本 / Snapshots</h2>

主事故快照包含 1,550 份报告、468 个原始字段；另一完整快照包含 1,592 份，用于版本敏感性。材料库存采用 1990–2024 年，安装年代库存采用 2004–2024 年；每里程比较使用 2010–2024 年对应材料的主管道及主管道阀事故。冻结资料用于复现本报告，不代表网站访问当天的最新发布。

<h2 id="definitions">原始定义 / Reporting definitions</h2>

- [配气事故填报说明，Rev 9-2023](https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2023-12/Current_GD_Incident_Instructions_PHMSA%20F%207100.1_2023-09%20and%20Beyond.pdf)：第 8 页人员分类，第 11 页场地，第 13 页材料。
- [配气年报填报说明，Rev 6-2023](https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2023-12/Current_2023_GD_Annual_Instructions_PHMSA%20F%207100.1-1%20%28rev%206-2023%29%20CY%202023.pdf)：第 5 页材料分类与内衬修复铸铁。
- [地区等级定义，49 CFR 192.5](https://www.govinfo.gov/content/pkg/CFR-2025-title49-vol3/pdf/CFR-2025-title49-vol3-sec192-5.pdf)

<h2 id="unit">长度与时间的单位 / Mileage and time</h2>

累计规模 E = ∑ Lᵧ × 1 年。每万英里·年伤亡报告率 = 10,000 × C / E，其中 C 为相应材料、时期和部件的伤亡报告数，Lᵧ 为年度在用里程。以下官方报告同样按一定里程、每年表达事故率；本研究独立确定自己的事故范围和分母。

- [PHMSA Pipeline Safety Update，2012，图 10，PDF 第 46 页](https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/docs/Pipeline%20Safety%20Update%20Oct%202012.pdf#page=46)
- [PHMSA/Volpe 环境评估，2022，表 8，PDF 第 53 页](https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2023-07/Tier-1-PHMSA-2022-0123-0001.pdf#page=53)
