#!/usr/bin/env python3
"""V76 editorial corrections applied *after* the capture-verified module build.

Source files are unpacked from atlas-source-v23.tar.gz on each build.
Only existing public entries are refined; no images, URLs, slugs, IDs or approval
records are changed. Avoid guessed company performance or external HTTP checks.
"""
from __future__ import annotations
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
SOURCE=BASE/"app"/"source_index.json"
MODULES=BASE/"app"/"module_catalog.json"

# Original URL serves as the identity guard against silently rewriting unrelated sources.
SITES={
 "sick":("https://www.sick.com/us/en/",
  "SICK 的公开产品方向涵盖工业传感器与机器安全系统。本案例聚焦技术型买家的信息任务：如何从自动化应用进入传感器产品分类，再查找具体规格、安全相关资料和后续咨询入口。它是网站信息架构的编辑观察，不代表对产品性能或认证范围的独立核验。"),
 "vestas":("https://www.vestas.com/en",
  "Vestas 的业务内容围绕风力发电机及相关服务展开。研究重点是大型设备企业如何在网页中衔接实物尺度、机型系列、应用环境与后续服务，让采购或项目团队能继续查阅具体产品资料。设备影像能够解释场景，但不能仅凭画面证明发电效率或项目结果。"),
 "onshape":("https://www.onshape.com/en/",
  "Onshape 面向工程设计团队提供云端 CAD、产品数据和协作工作流。本案例研究软件网站如何使用真实产品界面和任务场景，让工程师理解建模、版本管理及团队协作的关系。建议对照产品功能说明逐项核实，不把抽象的效率表述当成经过测试的收益。"),
 "molex":("https://www.molex.com/en-us/products/industrial-solutions",
  "Molex 的工业解决方案涉及连接器、电缆、供电与自动化配套。本案例将其作为规格密集型产品目录研究：专业访客需要按应用、连接方式和技术条件缩小选择范围，并能继续获取产品资料。设计分析关注可发现性，不推断页面未提供的兼容性或环境等级。"),
 "mcmaster-carr":("https://www.mcmaster.com/",
  "McMaster-Carr 的网站以工业零部件和维护、维修、运营采购目录为核心。这里研究搜索优先的信息组织、规格筛选以及从需求到具体零件的短路径。优秀的产品查找体验依赖清楚的分类与参数标注；本案例不以截图推断库存、交付速度或采购转化表现。"),
 "quickparts":("https://quickparts.com/",
  "Quickparts 的公开服务覆盖 CNC、增材制造及从样件到生产的制造需求。这个案例适合比较两类访客路径：已有明确技术资料、准备提交加工需求的团队，以及仍在评估工艺与批量适配性的团队。研究关注服务说明与询价入口衔接，不对实际报价或交期作推断。")
}

# id: (verified site id, existing module title, improved description, design learning).
# In particular, the prior summary for these modules was often identical to its title.
MODULES_EDIT={
 "skydio-drone-products":("skydio","Autonomous drone portfolio",
  "Skydio 的官方产品列表可用于研究自主无人机的机型导航。阅读时应区分硬件型号、业务应用、配套软件与具体规格资料，检查产品卡片是否帮助访问者继续做选择，而不是把所有型号当成同一类产品。",
  "从机型入口继续观察应用和技术资料之间的链接关系；图像本身不能证明飞行性能或可部署范围。"),
 "figure-robotics-figure-03":("figure-robotics","Figure humanoid hardware",
  "Figure 的人形机器人产品资料是硬件介绍型页面研究样本。可按外形、能力描述、演示影像与可核查的技术信息分层阅读，区分页面实际展示的机器人形态和需要额外依据的运行能力。",
  "产品特写适合说明形态与部件；关于自治能力、速度或部署效果，应回到明确的官方技术说明。"),
 "tekna-machines-cnc-range":("tekna-machines","CNC machining range comparison",
  "Tekna 的 CNC 设备系列入口适合检验工业目录的型号可发现性。可以比较产品家族的分类方式、相关工艺说明和进入详细技术参数的路径，并记录哪些信息必须进入具体型号页面才能核对。",
  "先帮助访客找到合适系列，再进入型号规格；不能根据产品图片推断加工精度或产能。"),
 "aixtron-deposition-products":("aixtron","Semiconductor deposition portfolio",
  "AIXTRON 的产品目录围绕半导体沉积设备及技术家族展开。专业买家可借助页面理解产品类别，再继续查阅适用工艺、系统范围和更详细的官方产品资料。",
  "把技术类别、设备系列与下一步资料入口分层，不用未经核实的性能数字代替选型依据。"),
 "formlabs-form4-product":("formlabs","High-end 3D printer product detail",
  "Formlabs Form 4 产品页适合研究设备型落地页如何把打印机外形、应用示例、材料选择和技术资料排成连续的阅读路径。评审时要分清视觉展示与官方规格声明。",
  "将概览、适用材料、设备规格及询问渠道分别标注；没有来源时不复述精度、速度等数值。"),
 "saronic-autonomous-vessels":("saronic","Autonomous vessel families",
  "Saronic 的自主船艇产品系列页可以用于观察大型硬件产品如何被划分成可比较的家族。应检查每一类产品的用途说明、配置差异与继续查看细节的入口，而不是仅比较船艇图片的视觉冲击力。",
  "多产品并列时先明确差异维度；图像不足以验证航程、自主等级或实际交付记录。"),
 "prima-power-automation-robotics":("prima-power","Sheet metal automation solutions",
  "Prima Power 的自动化与机器人技术内容提供了设备、生产线与工艺关联的研究入口。可以观察网站如何将单机设备、搬运或自动化环节组织成可理解的制造工作流。",
  "用工序和系统关系解释解决方案，具体产能、适用材料和设备兼容性应以官方规格为准。"),
 "helion-fusion-technology":("helion","Fusion technology explanation",
  "Helion 的聚变技术介绍页适合研究高门槛科学主题的内容分层。可以观察示意图、关键概念、技术过程与研究进展的叙述顺序，辨别哪些是原理解释，哪些是需要外部证据的研发结果。",
  "将科学原理图与已验证成果明确分开；技术愿景和插画不等于商业应用已经实现。"),
 "kvadrat-textile-products":("kvadrat","Commercial textile material library",
  "Kvadrat 的面料产品目录展示了材料型网站的不同筛选需求。设计研究应区分面料纹理与颜色的视觉发现、系列归类，以及进入具体材料规格和项目应用说明的路径。",
  "通过产品图建立材料感知，选择依据仍应包括材料型号、用途和官方技术资料。"),
 "snohetta-architecture-projects":("snohetta","Architecture project directory",
  "Snøhetta 的建筑项目目录是案例集合型导航研究样本。可以比较项目缩略图、名称、类别与项目详情入口如何协同工作，避免把不同建筑项目只按视觉风格混在一起。",
  "项目视觉引导发现，专业研究还应继续核对背景、设计条件与公开项目资料。"),
 "xometry-3d-printing-service":("xometry","Instant quoting with process proof",
  "Xometry 的 3D 打印服务页面适合分析制造工艺说明与询价入口的衔接。评审时先找到可用工艺、材料及设计约束，再观察报价流程在何处出现以及提示用户准备哪些文件。",
  "制造服务的转化路径应解释输入条件；页面含询价入口并不代表能获得即时或固定报价。"),
 "rosler-mass-finishing":("rosler","Surface finishing machine catalog",
  "Rösler 的表面处理设备目录可以用于研究工业设备分类。用户需要从表面处理任务进入设备类别，再获取工艺适用性和更具体的机器资料；图片仅提供识别线索。",
  "以加工需求组织产品家族，再链接可核对的技术参数，避免空泛的处理效果承诺。"),
 "cfs-energy-fusion-system":("cfs-energy","Fusion tokamak systems",
  "Commonwealth Fusion Systems 的聚变设备技术页面适合研究复杂工程系统的解释顺序。可以比较设备与磁体影像、系统组成说明以及技术进展信息的相互关系。",
  "将工程装置形态、工作原理与里程碑分开表达；大型设备画面不能替代实验结果验证。"),
 "prima-power-production-lines":("prima-power","Automated manufacturing line journey",
  "Prima Power 的自动化制造产线内容有助于研究从设备到生产流程的完整讲述。设计观察重点是不同工序、输送与系统集成节点是否具有可理解的先后关系。",
  "用阶段化说明解释工艺依赖与系统组成，别用没有来源的节拍或产出数字填充页面。"),
 "fictiv-process-stages":("fictiv","Four-stage production flow",
  "Fictiv 的生产流程分阶段解释数字制造服务，从前期技术资料到工厂执行之间存在多个确认步骤。该模块用来研究如何把复杂的服务过程拆为访客能依次理解的环节。",
  "核对每一步的输入资料、协作责任与下一步行动；研究只覆盖已采集截图所显示的部分，不推断未展示的流程细节。"),
 "xometry-rfq-first":("xometry","Quote-first service hero",
  "Xometry 的 CNC 制造服务页提供了询价入口与工艺说明并列的研究样本。可以观察用户如何在查看加工能力时直接进入项目需求提交，以及何处补充材料和规格要求。",
  "把行动入口和技术条件放在同一决策上下文中；不要把页面存在报价入口解释成承诺报价结果。"),
 "hexagon-capability":("hexagon","Engineering capabilities",
  "Hexagon 制造智能相关能力页面适合研究跨软硬件服务的体系表达。可以沿产品开发、制造与质量环节追踪不同技术能力的关联，而不只看一个公司级能力口号。",
  "用制造流程与买家任务组织技术模块，明确每种能力指向的具体产品或官方说明。"),
 "arburg-product-family":("arburg","Machine range introduction",
  "ARBURG 的工业设备产品世界展示了机器、机器人和相关制造技术的组合。研究时可从设备家族开始，再比较型号入口、适用任务以及是否提供详细参数与支持资料。",
  "产品系列应承担粗筛，具体规格与配置需到对应设备页面核实，不应从系列示意图推断能力。")
}

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
    src=read(SOURCE);modules=read(MODULES)
    sites={entry["id"]:entry for entry in src["sites"]}
    notes={entry["id"]:entry for entry in src["notes"]}
    by_id={entry["id"]:entry for entry in modules}
    assert len(sites)==len(src["sites"]) and len(by_id)==len(modules)
    for sid,(official,summary) in SITES.items():
        row=sites[sid]
        assert row["url"]==official,(sid,"source changed unexpectedly")
        assert len(summary)>=90,(sid,"insufficient editorial detail")
        row["summary"]=summary
    updated_notes=0
    for mid,(sid,title,summary,lesson) in MODULES_EDIT.items():
        row=by_id[mid]
        assert row["site_id"]==sid and row["title"]==title,(mid,"different public module")
        assert row.get("url","").startswith("https://"),mid
        assert len(summary)>=70 and len(lesson)>=32,mid
        assert summary.strip()!=title.strip(),mid
        row["summary"]=summary
        row["lesson"]=lesson
        if mid in notes:
            assert notes[mid]["site_id"]==sid,mid
            notes[mid]["summary"]=summary
            notes[mid]["lesson"]=lesson
            updated_notes+=1
    # This run cannot change media assets, source links, primary keys or drafts.
    write(SOURCE,src)
    write(MODULES,modules)
    print("V76 curated",len(SITES),"source summaries,",len(MODULES_EDIT),
          "module analyses,",updated_notes,"source notes; originals kept intact")

if __name__=="__main__":
    main()
