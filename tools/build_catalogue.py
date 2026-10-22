"""Build app/seeds/catalogue.json from the V3.1 prototype's data model.

The V3.1 bilingual prototype (PPWR_资料收集与批复系统_V3.1_中英对照.html) defines the
16 categories / 69 data items (+ the 4 Art 5 evidence items of V4.2 = 73), the TD V1.5 section map and the DoC V2.3 structure.
`tools/v31_prototype_data.json` is a verbatim dump of its JS constants. This script
turns it into the platform's catalogue: English-first, Chinese kept for the
bilingual labels, with the field definitions, applicability keys and evidence
type codes the platform needs.

    python3 tools/build_catalogue.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "v31_prototype_data.json"
OUT = ROOT / "app" / "seeds" / "catalogue.json"

# Which PPWR requirement an item evidences. "core" items are always applicable;
# the others follow the project's applicability matrix (app/applicability.py).
ARTICLE = {
    4: "a5", 5: "a6", 6: "a7", 7: "a8", 8: "a9", 9: "a10", 10: "a11", 11: "a12",
}
ARTICLE_OVERRIDE = {
    "C04-17": "a5pfas", "C04-18": "a5pfas", "C15-60": "a5pfas", "C15-61": "a5pfas",
    "C15-62": "a7", "C11-44": "a11", "C07-25": "a8", "C08-28": "a9",
}

# Items the platform assembles itself — they are never "collected" from the client.
SYSTEM_ITEMS = {
    "C02-06": "Built from the packaging BOM (Packaging & BOM tab).",
    "C14-55": "Built from the evidence vault — every file carries its Evidence ID.",
    "C16-67": "Cross-references are generated with the TD from approved items and evidence.",
    "C16-68": "Generated from the applicability matrix (Overview tab).",
}

# Items collected once per project rather than per packaging unit.
PROJECT_LEVEL = {"C12-46", "C14-54", "C14-55", "C16-66", "C16-67", "C16-68", "C16-69"}

# Suggested evidence type code (evidence_id_structure.png):
# DRW Drawing · TST Test report · DCL Declaration · MSD Material spec · PHO Photo
# BOM · CAL Calculation · plus REC Record · CRT Certificate · RPT Assessment report
EVIDENCE_CODE = {
    "C01-01": "BOM", "C01-02": "BOM", "C01-03": "DCL", "C01-04": "REC", "C01-05": "PHO",
    "C02-06": "BOM", "C02-07": "MSD", "C02-08": "DCL", "C02-09": "DCL",
    "C03-10": "DRW", "C03-11": "DRW", "C03-12": "DRW", "C03-13": "MSD", "C03-14": "REC",
    "C03-15": "RPT", "C04-16": "TST", "C04-17": "TST", "C04-18": "DCL",
    "C05-19": "RPT", "C05-20": "TST", "C05-21": "RPT", "C06-22": "CAL", "C06-23": "CRT",
    "C07-24": "TST", "C07-25": "PHO", "C08-26": "RPT", "C08-27": "TST", "C08-28": "PHO",
    "C09-29": "RPT", "C09-30": "TST", "C09-31": "REC", "C09-32": "TST", "C09-33": "RPT",
    "C09-34": "RPT", "C09-35": "CAL", "C09-36": "RPT", "C10-37": "RPT", "C10-38": "TST",
    "C10-39": "RPT", "C11-40": "PHO", "C11-41": "PHO", "C11-42": "PHO", "C11-43": "PHO",
    "C11-44": "PHO", "C11-45": "PHO", "C12-46": "RPT", "C12-47": "REC", "C12-48": "RPT",
    "C12-49": "REC", "C12-50": "REC", "C13-51": "REC", "C13-52": "REC", "C13-53": "REC",
    "C14-54": "REC", "C14-55": "REC", "C15-56": "DCL", "C15-57": "MSD", "C15-58": "DCL",
    "C15-59": "TST", "C15-60": "DCL", "C15-61": "DCL", "C15-62": "CRT", "C15-63": "DCL",
    "C15-64": "DCL", "C15-65": "DCL", "C16-66": "DCL", "C16-67": "REC", "C16-68": "RPT",
    "C16-69": "REC",
}

# English legal basis (the prototype's `legal` mixes article refs with Chinese notes).
LEGAL_EN = {
    "C01-01": "Annex VIII points 1 and 4 (unique identification); Art 15(5); Annex VII 2(a)", "C01-02": "Annex VII (identification in the TD)",
    "C01-03": "Annex VII; Art 15(4) series production stays in conformity",
    "C01-04": "Art 10 minimisation; Art 24 empty space; Annex IV",
    "C01-05": "Annex VII (identification and verification)",
    "C02-06": "Art 6(1)(2), Annex II criteria; Art 10", "C02-07": "Art 6; Art 5(4) evidence chain",
    "C02-08": "Art 5(4); Annex II", "C02-09": "Art 6(9) components compatible with collection, sorting and recycling; Art 5(4)",
    "C03-10": "Art 6(1); Art 10(1); Annex VII 2(b)", "C03-11": "Art 6(1); Art 10(1); Annex VII 2(b)",
    "C03-12": "Art 12 labelling; Art 15(5)-(6); Art 6(9) component compatibility", "C03-13": "Annex VII point 3 (manufacturing)",
    "C03-14": "Annex VII point 3 (manufacturing)", "C03-15": "Art 6(1), Art 10(1); Annex IV; Annex VII 2(c)",
    "C04-16": "Art 5(4): Pb+Cd+Hg+Cr(VI) ≤ 100 mg/kg from 12 Aug 2026",
    "C04-17": "Art 5(5): PFAS limits for food-contact packaging (25 ppb / 250 ppb / 50 ppm)",
    "C04-18": "Art 5(5) applicability; Regulation (EC) 1935/2004 where food-contact",
    "C05-19": "Art 6(1)-(3), Annex II; design-for-recycling condition from 1 Jan 2030 (Art 6(2)); Art 6(9) TD",
    "C05-20": "Art 6(9) integrated / separate components", "C05-21": "Art 6(4) — method before the delegated acts apply",
    "C06-22": "Art 7 (plastic packaging only), from 1 Jan 2030", "C06-23": "Art 7(3), 7(6) and 7(8) calculation and verification of recycled content",
    "C07-24": "Art 8 (biobased feedstock in plastic packaging)", "C07-25": "Art 8; Art 12 labelling of claims",
    "C08-26": "Art 9: tea/coffee pods, fruit stickers, very lightweight bags (from 12 Feb 2028)",
    "C08-27": "Art 9; Annex III; EN 13432 industrial composting", "C08-28": "Art 12(1) compostable-packaging label; Art 9",
    "C09-29": "Art 10(1) from 1 Jan 2030; Annex IV performance criteria",
    "C09-30": "Annex IV — product protection", "C09-31": "Annex IV — manufacturing process",
    "C09-32": "Annex IV — logistics", "C09-33": "Annex IV — packaging functionality",
    "C09-34": "Annex IV — information, hygiene and safety",
    "C09-35": "Art 24: empty space ratio ≤ 50 % (grouped, transport, e-commerce) from 2030",
    "C09-36": "Art 10(2)-(3): double walls, false bottoms; design rights before 11 Feb 2025",
    "C10-37": "Art 11 (reusable packaging criteria)", "C10-38": "Art 11(1)(c)(d)",
    "C10-39": "Art 11(1)(e)(f); Annex VI", "C11-40": "Art 15(6) manufacturer name / trade name / trademark and postal address",
    "C11-41": "Art 15(5) type, batch or serial number",
    "C11-42": "Art 12(1) harmonised material-composition label (from 12 Aug 2028 or 24 months after the implementing act)",
    "C11-43": "Art 12(1) optional QR code / digital data carrier; Art 12(2) for reusable packaging", "C11-44": "Art 12(2) reusable-packaging label; Art 12(1) deposit-and-return label",
    "C11-45": "Art 12(9)-(10) national EPR / DRS identification", "C12-46": "Annex VII point 2: risk analysis",
    "C12-47": "Art 15(4) re-assessment when design or supply changes", "C12-48": "Art 39(2) DoC continuously updated",
    "C12-49": "Art 10 conclusion maintained", "C12-50": "Art 12 labelling maintained",
    "C13-51": "Art 15(4); Annex VII point 3", "C13-52": "Art 15(4); Annex VII point 3",
    "C13-53": "Art 15(4); Annex VII point 3",
    "C14-54": "Annex VII 2(d); Art 36–37 harmonised standards and common specifications",
    "C14-55": "Annex VII 2(f) test reports; Annex VIII", "C15-56": "Art 16 supplier information obligations; Art 15(2) conformity assessment",
    "C15-57": "Art 6; Art 5(4)", "C15-58": "Art 5(4); Annex II", "C15-59": "Art 5(4) (≤ 100 mg/kg)",
    "C15-60": "Art 5(5)", "C15-61": "Art 5(5); Regulation (EC) 1935/2004", "C15-62": "Art 7",
    "C15-63": "Art 6", "C15-64": "Art 6(3); Art 5(4)", "C15-65": "Art 15(4) change notification",
    "C16-66": "Art 39 + Annex VIII (EU declaration of conformity)",
    "C16-67": "Annex VII / VIII — conclusions ↔ evidence", "C16-68": "Annex VII — rationale for N/A items",
    "C16-69": "Annex VII point 4 — manufacturer approval before the DoC is signed",
}

SEL = "sel"
FIELDS_EN = {
    "C01-01": [("upi", "UPI — unique packaging identifier", "text"),
               ("pkgName", "Packaging name / description", "text"),
               ("pkgType", "Packaging level (sales / grouped / transport / e-commerce)", "text")],
    "C01-02": [("sku", "Packaged product / SKU / model range", "text")],
    "C01-03": [("sup", "Packaging supplier", "text"), ("site", "Manufacturing site", "text"),
               ("country", "Country of manufacture", "text")],
    "C01-04": [("mass", "Total packaging mass (g)", "text"), ("dims", "Dimensions L × W × H (mm)", "text")],
    "C01-05": [("ref", "Photo / artwork reference", "text")],
    "C03-10": [("docno", "Drawing number / revision", "text")],
    "C03-11": [("docno", "Drawing number / revision", "text")],
    "C03-12": [("docno", "Artwork number / revision", "text")],
    "C03-13": [("docno", "Specification number / revision", "text")],
    "C03-14": [("docno", "Control plan number / revision", "text")],
    "C03-15": [("rationale", "Design rationale (protection, logistics, function, information)", "ta")],
    "C04-16": [("res", "Result — sum of Pb+Cd+Hg+Cr(VI) (mg/kg)", "text"),
               ("method", "Test method (e.g. EN 13657 digestion + ICP-OES)", "text")],
    "C04-17": [("app", "PFAS applicability", SEL, ["Not applicable (non food-contact)",
                                                    "Applicable (food-contact)", "To be confirmed"]),
               ("note", "Rationale / result", "ta")],
    "C04-18": [("app", "Food-contact status", SEL, ["No — not food-contact", "Yes — food-contact",
                                                     "To be confirmed"])],
    "C05-19": [("concl", "Recyclability assessment conclusion", "ta")],
    "C05-21": [("method", "Method / standard applied (e.g. EN 13430 used as guidance)", "text")],
    "C06-22": [("app", "Recycled-content applicability", SEL, ["Not applicable (no plastic part)",
                                                                "Applicable (plastic packaging)",
                                                                "To be confirmed"]),
               ("pcr", "Recycled content (%) — plastic part", "text")],
    "C07-24": [("app", "Biobased feedstock", SEL, ["Not applicable", "Applicable (biobased claim)",
                                                    "To be confirmed"])],
    "C08-26": [("app", "Compostability (Art 9 packaging)", SEL, ["Not applicable",
                                                                  "Applicable (Art 9 packaging)",
                                                                  "To be confirmed"])],
    "C09-29": [("concl", "Minimisation assessment conclusion", "ta")],
    "C09-35": [("note", "Empty-space ratio assessment", "ta")],
    "C09-36": [("app", "Double wall / false bottom", SEL, ["None", "Present — exemption applies",
                                                            "Present — to be assessed"])],
    "C10-37": [("app", "Single-use or reusable", SEL, ["Single-use (not applicable)", "Reusable",
                                                        "To be confirmed"])],
    "C11-40": [("loc", "Position of the information on the artwork", "text")],
    "C14-54": [],
    "C16-66": [("docNo", "EU DoC number", "text"), ("tdNo", "TD number / version", "text"),
               ("sign", "Signatory (name, function)", "text"), ("place", "Place of issue", "text")],
    "C16-69": [("prep", "Prepared by", "text"), ("rev", "Reviewed by", "text"),
               ("appr", "Approved by", "text")],
}

TABLES = {
    "C14-54": ["Standard / specification", "Edition", "Clause", "Requirement covered", "Evidence"],
}

# Short, practical "what good looks like" hints shown on the item page.
EXAMPLES = {
    "C01-01": "UPI format PU-001 within packaging system PS-001; every SKU must trace to ≥ 1 UPI.",
    "C01-05": "JPG/PNG ≥ 1024×768, plain background, natural light, scale reference; name PU-001-C001-PHO-001.",
    "C02-07": "e.g. Corrugated fibreboard, B-flute, 250 g/m² — supplier TDS as PDF.",
    "C03-10": "Drawing revision must match the artwork revision.",
    "C04-16": "Third-party report (ICP-OES / ICP-MS) covering every component incl. inks and adhesives, "
              "dated within 24 months. Example: Pb < 20, Cd < 10, Hg < 10, Cr(VI) < 10 → sum < 50 mg/kg ✓",
    "C04-17": "Non food-contact packaging: record 'Not applicable' with the reason.",
    "C05-19": "Mono-material paper: EN 13430 material-recycling route — material ID, main-component mass "
              "share, collection/sorting, compatibility of inks, adhesives, coatings and labels.",
    "C06-22": "Plastic parts only: plastic mass (g), PCR mass (g), PCR %, with ISCC PLUS / RCS chain of custody.",
    "C09-29": "Address each Annex IV criterion separately; if no further reduction is possible, give the "
              "technical reason.",
    "C09-30": "ISTA / ASTM transport, stacking, drop and compression tests.",
    "C12-46": "Risk of non-conformity per applicable article — likelihood, impact, control.",
    "C14-54": "EN 13427–EN 13432 (former PPWD harmonised standards — under the PPWR used as guidance only, "
              "no presumption of conformity, Commission FAQ 2026), EN 13657 + ICP-OES for heavy metals.",
    "C15-56": "Signed supplier declaration per key component, dated and referencing PPWR (EU) 2025/40.",
    "C16-66": "DoC number with year-month, e.g. DoC-2026-09-PS001; signed by a person with authority.",
    "C16-69": "Prepared (compliance engineer) → Reviewed (QA) → Approved (management).",
}

# ---------------------------------------------------------------------------
# Bilingual, product-neutral rationale. The prototype texts were written for one demo
# product (a paper colour card) and some dates/limits were imprecise; these overrides
# are checked against the adopted text of Regulation (EU) 2025/40 (OJ L, 22.1.2025).
# ---------------------------------------------------------------------------
CAT_LOGIC = {
    2: ("Art 6 recyclability is assessed per packaging unit on its material composition, including integrated and "
        "separate components (Art 6(9), Annex II); Art 10 minimisation needs a mass/volume baseline (Annex IV Part B). "
        "Annex VII 2(b) requires the materials of components. The complete BOM is the quantitative backbone of all assessments.",
        "Art 6 可回收性按包装单元的材料组成评估，须涵盖集成组件与分离组件（Art 6(9)、Annex II）；Art 10 最小化需要质量/体积基线"
        "（Annex IV Part B）。Annex VII 2(b) 要求技术文档包含各组件材料。完整 BOM 是所有定量评估的基础。"),
    4: ("Art 5(4): the sum of Pb, Cd, Hg and Cr(VI) in packaging or packaging components shall not exceed 100 mg/kg "
        "(applies from 12 Aug 2026, Art 71). Art 5(5): from 12 Aug 2026 food-contact packaging must stay below 25 ppb for "
        "any PFAS (targeted analysis), 250 ppb for the sum of targeted PFAS and 50 ppm for total PFAS incl. polymeric PFAS. "
        "Art 5(6): compliance shall be demonstrated in the technical documentation (Annex VII).",
        "Art 5(4)：包装或包装组件中铅、镉、汞、六价铬四项浓度之和不得超过 100 mg/kg（2026-08-12 起适用，Art 71）。Art 5(5)：自 "
        "2026-08-12 起，食品接触包装中任一 PFAS（靶向分析）须 < 25 ppb、靶向 PFAS 总和 < 250 ppb、含聚合物 PFAS 的总 PFAS < 50 ppm。"
        "Art 5(6)：符合性须在技术文档（Annex VII）中证明。"),
    5: ("Art 6(1): all packaging shall be recyclable. The design-for-recycling condition (Art 6(2)(a)) and grades A/B/C apply "
        "from 1 Jan 2030 or 24 months after the delegated acts enter into force, whichever is later; recycled at scale from "
        "1 Jan 2035; only grades A/B from 1 Jan 2038 (Art 6(3)). Until the delegated acts exist, document the method used; "
        "EN 13430 can serve as guidance but no longer gives presumption of conformity (Commission FAQ 2026).",
        "Art 6(1)：所有包装须可回收。按设计可回收条件（Art 6(2)(a)）及 A/B/C 分级自 2030-01-01 或授权法案生效后 24 个月（以较晚者为准）"
        "适用；规模化回收自 2035-01-01；2038-01-01 起仅 A/B 级可投放（Art 6(3)）。授权法案出台前，记录实际采用的方法；EN 13430 可作为"
        "指引，但已不再产生符合性推定（欧盟委员会 FAQ 2026）。"),
    6: ("Art 7 sets minimum recycled content for the plastic part of packaging from 1 Jan 2030 or 3 years after the "
        "implementing act on calculation/verification (whichever later): 30 % contact-sensitive PET, 10 % other "
        "contact-sensitive, 30 % single-use plastic beverage bottles, 35 % other plastic packaging; higher targets from 2040. "
        "Plastic parts < 5 % of the unit weight are exempt (Art 7(5)(b)). Not applicable when the unit contains no plastic.",
        "Art 7 对包装中的塑料部分设定最低再生含量：自 2030-01-01 或计算/验证实施法案生效后 3 年（以较晚者为准）——接触敏感 PET 30%、"
        "其他接触敏感塑料 10%、一次性塑料饮料瓶 30%、其他塑料包装 35%；2040 年起目标提高。塑料部分低于包装单元总重 5% 的豁免"
        "（Art 7(5)(b)）。包装单元不含塑料时不适用。"),
    7: ("Art 8 contains no obligation for manufacturers today: the Commission reviews biobased plastic packaging by "
        "12 Feb 2028 and may propose requirements. Record N/A unless a biobased claim is made; substantiate any claim.",
        "Art 8 目前未对制造商设定义务：欧盟委员会将于 2028-02-12 前评估生物基塑料包装并可能提出要求。未作生物基声明时记录 N/A；"
        "如作声明，须有证据支持。"),
    8: ("Art 9(1): by 12 Feb 2028, packaging under Art 3(1)(1)(f) (e.g. tea/coffee bags and single-serve units) and sticky "
        "labels on fruit and vegetables must be compatible with industrial composting (Annex III); other packaging, incl. "
        "biodegradable plastics, must be designed for material recycling (Art 9(3)). Record N/A with rationale if out of scope.",
        "Art 9(1)：2028-02-12 前，Art 3(1)(1)(f) 所列包装（如茶包/咖啡包及单份装单元）和果蔬贴纸须满足工业堆肥要求（Annex III）；"
        "其他包装（含可生物降解塑料）须按材料回收设计（Art 9(3)）。不在范围内时记录 N/A 及理由。"),
    9: ("Art 10(1): by 1 Jan 2030 weight and volume must be reduced to the minimum necessary for functionality. Annex IV Part A "
        "lists eight performance criteria (product protection, manufacturing processes, logistics, functionality, information, "
        "hygiene and safety, legal requirements, recycled content/recyclability/re-use); Part B defines what the TD must contain. "
        "Art 24: max. 50 % empty-space ratio for grouped, transport and e-commerce packaging from 1 Jan 2030 (or 3 years after "
        "the implementing act).",
        "Art 10(1)：2030-01-01 前，包装重量和体积须降至确保功能所需的最低限度。Annex IV Part A 列出八项性能准则（产品保护、制造工艺、"
        "物流、功能性、信息要求、卫生与安全、法律要求、再生含量/可回收性/重复使用），Part B 规定技术文档须包含的内容。Art 24：组合、"
        "运输及电商包装的空隙率自 2030-01-01（或实施法案生效后 3 年）起不得超过 50%。"),
    10: ("Art 11(1) lists nine cumulative conditions for packaging to be considered reusable; compliance is demonstrated in the "
         "Annex VII technical information (Art 11(3)). Single-use packaging records N/A with rationale.",
         "Art 11(1) 列出包装被视为可重复使用须同时满足的九项条件，符合性在 Annex VII 技术资料中证明（Art 11(3)）。一次性包装记录 N/A "
         "及理由。"),
    11: ("Art 12(1): harmonised material-composition label from 12 Aug 2028 or 24 months after the implementing acts (whichever "
         "later); reusable-packaging label from 12 Feb 2029 (Art 12(2)). Art 15(5)-(6) already apply from 12 Aug 2026: type/"
         "batch/serial number and the manufacturer's name and postal address on the packaging (or via QR / accompanying document).",
         "Art 12(1)：统一材料成分标签自 2028-08-12 或实施法案生效后 24 个月（以较晚者为准）起适用；可重复使用包装标签自 2029-02-12 起"
         "（Art 12(2)）。Art 15(5)-(6) 自 2026-08-12 起已适用：包装须标注型号/批号/序列号，以及制造商名称和邮寄地址（或通过二维码/随附文件提供）。"),
    13: ("Art 15(4) and Annex VII point 3: the manufacturing process and its monitoring must keep series production in "
         "conformity with the technical documentation. Incoming inspection, in-process QC and release records evidence this.",
         "Art 15(4) 与 Annex VII 第 3 点：制造过程及其监控须确保量产包装持续符合技术文档。来料检验、过程 QC 与放行记录是证据链。"),
}

# Item rationale overrides (EN, ZH) where the prototype text was product-specific or imprecise.
LOGIC = {
    "C01-01": ("The unique identification of the packaging (Annex VIII point 1) is the index used throughout the TD and the "
               "DoC; without it no conclusion can be anchored to a specific packaging.",
               "包装的唯一识别（Annex VIII 第 1 点）是贯穿技术文档与 DoC 的索引；没有它，任何结论都无法落到具体包装上。"),
    "C02-09": ("Inks, adhesives and coatings may contain heavy metals or hinder recycling of the main body; Art 6(9) requires "
               "all components to be compatible with collection, sorting and recycling.",
               "油墨、胶黏剂和涂层可能含重金属或妨碍主体材料回收；Art 6(9) 要求所有组件与收集、分选、回收工艺相容。"),
    "C05-19": ("Recyclability assessment of the unit and its components: material identification, main-component mass shares, "
               "collection/sorting stream and recycling-process compatibility. Record the method used until the delegated acts "
               "on design-for-recycling criteria apply; the conclusion feeds TD §7.",
               "包装单元及其组件的可回收性评估：材料识别、主要组件质量占比、收集分选流向、回收工艺相容性。在设计可回收授权法案适用前，"
               "记录实际采用的方法；结论填入 TD §7。"),
    "C06-22": ("Required only for the plastic part of packaging (Art 7). Record plastic mass, recycled (post-consumer) mass and "
               "the calculation basis, or the N/A / exemption rationale (no plastic part, or plastic < 5 % of unit weight).",
               "仅针对包装中的塑料部分（Art 7）。记录塑料质量、消费后再生料质量及计算依据，或记录 N/A / 豁免理由（无塑料部分，或塑料低于"
               "单元重量 5%）。"),
    "C06-23": ("Where Art 7 applies: show that the recycled input meets Art 7(3) and that the calculation will follow the "
               "implementing act under Art 7(8) once adopted.",
               "Art 7 适用时：证明再生原料满足 Art 7(3) 条件，并在 Art 7(8) 实施法案通过后按其方法计算与验证。"),
    "C07-24": ("Art 8 sets no manufacturer obligation today. Record N/A unless a biobased claim is made; substantiate any claim "
               "(e.g. biobased carbon content by a recognised method).",
               "Art 8 目前无制造商义务。除非作出生物基声明，否则记录 N/A；如作声明须提供证据（如按公认方法测定生物基碳含量）。"),
    "C08-26": ("Decide whether the packaging is one of the formats in Art 9(1) (by 12 Feb 2028 compostable); otherwise record "
               "N/A with the rationale.",
               "判断包装是否属于 Art 9(1) 所列形式（2028-02-12 前须可堆肥）；否则记录 N/A 及理由。"),
    "C09-29": ("Summary conclusion consolidating the eight Annex IV Part A criteria and the Part B elements (calculation of the "
               "minimum weight/volume, reason preventing further reduction per criterion, tests/studies). Feeds TD §11.",
               "最小化评估总结论：汇总 Annex IV Part A 八项准则及 Part B 要素（最低重量/体积计算、各准则下无法进一步减量的设计原因、"
               "测试/研究）。结论填入 TD §11。"),
    "C09-30": ("Shows the design requirement for product protection (Annex IV criterion 1) that prevents further reduction, "
               "e.g. drop, compression or transport tests.",
               "说明产品保护（Annex IV 准则 1）对设计的要求为何阻止进一步减量，如跌落、压缩或运输测试。"),
    "C09-33": ("Functionality requirements (Annex IV criterion 4) — opening, closing, dispensing, display — that determine the "
               "structure.", "功能性要求（Annex IV 准则 4）——开启、闭合、取用、展示——对结构的决定作用。"),
    "C09-35": ("Record whether Art 24 applies (grouped, transport, e-commerce: ≤ 50 % from 2030; sales packaging: empty space "
               "reduced to the minimum necessary by 12 Feb 2028, Art 24(4)) and the method used.",
               "记录 Art 24 是否适用（组合、运输、电商包装：2030 起 ≤ 50%；销售包装：2028-02-12 前空隙须降至必要最低，Art 24(4)）及所用方法。"),
    "C10-37": ("Single-use packaging → N/A. If reusability is claimed, all nine Art 11(1) conditions must be demonstrated.",
               "一次性包装 → N/A。如声明可重复使用，须证明满足 Art 11(1) 全部九项条件。"),
    "C11-41": ("Carrier of the type, batch or serial number or other identification element required by Art 15(5).",
               "Art 15(5) 要求的型号、批号、序列号或其他识别元素的载体与方案。"),
    "C11-42": ("How material composition and sorting information appear on-pack today, and the plan for the harmonised Art 12(1) "
               "label once the implementing act applies.",
               "当前包装上材料成分与分选信息的呈现方式，以及实施法案适用后切换为 Art 12(1) 统一标签的计划。"),
    "C11-43": ("If a QR code / data carrier is used, record its content and destination and bind it to the packaging identity.",
               "如使用二维码/数据载体，记录其内容与跳转目标，并与包装身份绑定。"),
    "C11-45": ("Record national identification requirements (EPR symbol, national DRS symbol) for the target markets.",
               "记录目标市场的国家识别要求（EPR 标识、国家押金回收标识）。"),
    "C15-62": ("Supplier counterpart of C06-22/23; N/A when the unit has no plastic part.",
               "C06-22/23 的供应商侧证据；包装单元无塑料部分时为 N/A。"),
}

# The four Art 5 evidence items of the V4.2 prototype ("Art 5 证明文件专项目"):
# a home for certificates, CoCs and declarations that had no landing place before.
EXTRA_ITEMS = [
    {"id": "C04-70", "cat": 4, "article": "a5", "evidence_code": "TST",
     "name": "Heavy-metal CoC / Third-party Test Report (evidence)",
     "name_zh": "重金属 CoC / 第三方检测报告（证明文件）",
     "requirement": "Third-party lab report or supplier CoC for Pb, Cd, Hg and Cr(VI)",
     "requirement_zh": "第三方实验室出具的 Pb、Cd、Hg、Cr(VI) 检测报告或供应商 CoC 证书",
     "form_zh": "CoC 证书 / 第三方检测报告（PDF）",
     "legal": "Art 5(4) ≤ 100 mg/kg; Art 5(6) and Annex VII 2(f) — test reports in the TD",
     "logic": "The landing place for the original heavy-metal certificate or test report behind C04-16. Record report "
              "number, laboratory, date and scope so TD §6 and the Evidence Register (§17) can cite it.",
     "logic_zh": "C04-16 结论背后的重金属证书或检测报告原件的正式落点。登记报告编号、实验室、日期与覆盖范围，供 TD §6 与证据登记表（§17）引用。",
     "td": "TD §6, §17 / T05, T16",
     "fields": [("cocno", "CoC / report number", "CoC / 报告编号", "text"),
                ("lab", "Laboratory / issuer", "检测机构 / 签发方", "text"),
                ("rdate", "Report date (YYYY-MM-DD)", "报告日期（YYYY-MM-DD）", "text"),
                ("scope", "Scope covered (packaging / components / inks)", "覆盖范围（包装 / 组件 / 油墨）", "text"),
                ("res", "Result — sum of Pb+Cd+Hg+Cr(VI) (mg/kg)", "检测结果（四项总和 mg/kg）", "text"),
                ("note", "Remarks", "备注", "ta")],
     "example": "HM-2026-014-ICPOES · accredited lab · 2026-08-30 · card + inks + adhesive · sum < 50 mg/kg"},
    {"id": "C04-71", "cat": 4, "article": "a5pfas", "evidence_code": "TST",
     "name": "PFAS Test Report / Compliance Declaration (evidence)",
     "name_zh": "PFAS 检测报告 / 符合性声明（证明文件）",
     "requirement": "Targeted / total-fluorine PFAS test report or supplier PFAS declaration",
     "requirement_zh": "PFAS 靶向分析 / 总氟检测报告或供应商 PFAS 符合性声明",
     "form_zh": "检测报告 / PFAS Declaration（PDF）",
     "legal": "Art 5(5) (food-contact packaging, from 12 Aug 2026); Art 5(6) TD",
     "logic": "The landing place for the PFAS test report or declaration behind C04-17. If total fluorine exceeds 50 mg/kg, "
              "Art 5(5)(c) entitles the manufacturer to proof from the supplier of how much is PFAS vs non-PFAS fluorine.",
     "logic_zh": "C04-17 背后的 PFAS 检测报告或声明的正式落点。若总氟超过 50 mg/kg，制造商可依 Art 5(5)(c) 要求供应商提供 PFAS 与非 PFAS 氟含量的证明。",
     "td": "TD §6, §17 / T05, T16",
     "fields": [("app", "Applicability", "适用性", "sel",
                 ["Applicable (food-contact)", "Not applicable (non food-contact)", "To be confirmed"],
                 ["适用（食品接触）", "不适用（非食品接触）", "待确认"]),
                ("rno", "Report / declaration number", "报告 / 声明编号", "text"),
                ("lab", "Laboratory / issuer", "检测机构 / 签发方", "text"),
                ("method", "Method (targeted PFAS analysis / total fluorine)", "检测方法（靶向 PFAS 分析 / 总氟）", "text"),
                ("val", "Values (ppb / ppm)", "检测值（ppb / ppm）", "text"),
                ("note", "Remarks", "备注", "ta")],
     "example": "Targeted PFAS each < 25 ppb; sum < 250 ppb; total PFAS < 50 ppm — report FCM-PFAS-2026-007"},
    {"id": "C04-72", "cat": 4, "article": "a5pfas", "evidence_code": "DCL",
     "name": "Food-contact Declaration of Compliance (evidence)",
     "name_zh": "食品接触符合性声明（证明文件）",
     "requirement": "Declaration of compliance under the food-contact legislation applicable to the material",
     "requirement_zh": "按材料适用的食品接触法规出具的符合性声明",
     "form_zh": "Food-contact DoC / Declaration（PDF）",
     "legal": "Art 5(5) applicability; Regulation (EC) No 1935/2004 and specific measures (e.g. (EU) No 10/2011 for plastics)",
     "logic": "Written evidence of the food-contact status that decides whether Art 5(5) applies. Food-contact declarations "
              "are governed by the food-contact legislation, not by the PPWR itself.",
     "logic_zh": "证明食品接触属性的书面证据，决定 Art 5(5) 是否适用。食品接触声明受食品接触法规约束，而非 PPWR 本身。",
     "td": "TD §6, §17 / T05, T16",
     "fields": [("declno", "Declaration number", "声明编号", "text"),
                ("issuer", "Issuer", "签发方", "text"),
                ("scope", "Materials / conditions of use covered", "覆盖的材料 / 使用条件", "text"),
                ("note", "Remarks", "备注", "ta")],
     "example": "FCM-DoC-2026-007 · issued by the laminate supplier · PE/PET laminate, 10 days at 40 °C"},
    {"id": "C04-73", "cat": 4, "article": "a5", "evidence_code": "DCL",
     "name": "Art 5 Statement of Conformity (consolidated)",
     "name_zh": "Art 5 物质要求符合性汇总声明",
     "requirement": "Consolidated statement linking the heavy-metal, PFAS and food-contact evidence",
     "requirement_zh": "把重金属、PFAS 与食品接触证据串联的汇总声明",
     "form_zh": "符合性声明（Art 5 Statement of Conformity）",
     "legal": "Art 5(4)-(6); Art 39 + Annex VIII (the DoC covers Art 5) — a separate statement is good practice",
     "logic": "Optional summary that ties C04-70/71/72 into one conclusion referenced by TD §6. The EU DoC itself already "
              "declares Art 5; this statement is a recommended practice, not a separate legal document.",
     "logic_zh": "把 C04-70/71/72 汇总为一项结论供 TD §6 引用的可选文件。EU DoC 本身已声明 Art 5 符合性；本声明属于建议做法，并非单独的法定文件。",
     "td": "TD §6, §17, §20 / T05, T16",
     "fields": [("stno", "Statement number / version", "声明编号 / 版本", "text"),
                ("issuer", "Issued by (manufacturer / supplier)", "出具方（制造商 / 供应商）", "text"),
                ("date", "Date of issue (YYYY-MM-DD)", "签发日期（YYYY-MM-DD）", "text"),
                ("basis", "Basis (evidence IDs, methods)", "符合性依据（证据编号、方法）", "ta"),
                ("concl", "Conclusion", "符合性结论", "ta")],
     "example": "SOC-PPWR-2026-001 V1.0 — Art 5(4): sum < 50 mg/kg (HM-2026-014); Art 5(5): not food-contact → N/A"},
]

EXTRA_SAMPLES = {
    "C04-70": """<p><b>Example · 示例：heavy-metal report register</b></p>
<table class="ex-tbl"><tr><th>Field 项目</th><th>Example 填写示例</th></tr>
<tr><td>Report no. 报告编号</td><td>HM-2026-014-ICPOES</td></tr>
<tr><td>Laboratory 检测机构</td><td>ISO/IEC 17025 accredited lab 认可实验室</td></tr>
<tr><td>Date 报告日期</td><td>2026-08-30</td></tr>
<tr><td>Scope 覆盖范围</td><td>Card + inks + adhesive (4 components) 纸卡 + 油墨 + 胶黏剂（4 个组件）</td></tr>
<tr><td>Result 结果</td><td>Pb &lt; 20, Cd &lt; 10, Hg &lt; 10, Cr(VI) &lt; 10 → sum &lt; 50 mg/kg ✓</td></tr></table>""",
    "C04-71": """<p><b>Example · 示例：PFAS evidence register</b></p>
<table class="ex-tbl"><tr><th>Field 项目</th><th>Food-contact 食品接触</th><th>Not food-contact 非食品接触</th></tr>
<tr><td>Applicability 适用性</td><td>Applicable 适用</td><td>Not applicable — Art 5(5) 不适用</td></tr>
<tr><td>Evidence 证据</td><td>Targeted PFAS + total fluorine report 靶向 PFAS + 总氟报告</td><td>Record N/A rationale 记录 N/A 理由</td></tr>
<tr><td>Values 检测值</td><td>each &lt; 25 ppb; sum &lt; 250 ppb; total &lt; 50 ppm</td><td>—</td></tr></table>""",
    "C04-72": """<p><b>Example · 示例：food-contact declaration</b></p>
<table class="ex-tbl"><tr><th>Field 项目</th><th>Example 填写示例</th></tr>
<tr><td>Declaration no. 声明编号</td><td>FCM-DoC-2026-007</td></tr>
<tr><td>Issuer 签发方</td><td>Laminate supplier 复合膜供应商</td></tr>
<tr><td>Scope 范围</td><td>PET/PE laminate; fatty foods, 10 d at 40 °C 复合膜；脂肪类食品，40 °C 10 天</td></tr></table>""",
    "C04-73": """<p><b>Example · 示例：Art 5 statement of conformity (good practice 建议做法)</b></p>
<table class="ex-tbl"><tr><th>Field 项目</th><th>Example 填写示例</th></tr>
<tr><td>Statement 声明</td><td>SOC-PPWR-2026-001 V1.0</td></tr>
<tr><td>Basis 依据</td><td>Art 5(4): HM-2026-014 (sum &lt; 50 mg/kg); Art 5(5): not food-contact → N/A</td></tr>
<tr><td>Conclusion 结论</td><td>Meets the applicable Art 5 requirements 满足适用的 Art 5 要求</td></tr></table>""",
}


def _field(spec, zh_labels: dict) -> dict:
    """spec: (k, label, type[, options]) or, for EXTRA_ITEMS, (k, label, label_zh, type[, options, options_zh])."""
    if len(spec) >= 4 and spec[2] not in ("text", "ta", SEL) and spec[3] in ("text", "ta", SEL):
        k, label, label_zh, typ, *rest = spec
    else:
        k, label, typ, *rest = spec
        label_zh = zh_labels.get(k, "")
    f = {"k": k, "label": label, "label_zh": label_zh, "type": typ}
    if typ == SEL:
        f["options"] = rest[0]
        if len(rest) > 1:
            f["options_zh"] = rest[1]
    return f


def main() -> None:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    cats = []
    for c in src["CATS"]:
        en, zh = CAT_LOGIC.get(c["id"], (src["CAT_EN_LOGIC"].get(str(c["id"]), ""), c["logic"]))
        cats.append({
            "id": c["id"], "name": c["en"], "name_zh": c["name"],
            "logic": en, "logic_zh": zh, "td": c["td"],
            "article": ARTICLE.get(c["id"], "core"),
            "sample_html": src["SAMPLES_CAT"].get(str(c["id"]), ""),
        })
    items = []
    for it in src["ITEMS"]:
        en = src["ITEM_EN"][it["id"]]
        zh_fields = {f["k"]: f for f in it.get("fields", [])}
        fields = []
        for spec in FIELDS_EN.get(it["id"], []):
            f = _field(spec, {k: v.get("l", "") for k, v in zh_fields.items()})
            zo = zh_fields.get(spec[0], {}).get("o")
            if f["type"] == SEL and zo and len(zo) == len(f["options"]):
                f["options_zh"] = zo
            fields.append(f)
        logic_en, logic_zh = LOGIC.get(it["id"], (en["lg"], it["logic"]))
        items.append({
            "id": it["id"], "cat": it["cat"], "name": en["n"], "name_zh": it["name"],
            "requirement": en["r"], "requirement_zh": it.get("req", ""), "form_zh": it.get("form", ""),
            "legal": LEGAL_EN[it["id"]], "logic": logic_en, "logic_zh": logic_zh, "td": it["td"],
            "fields": fields, "table": TABLES.get(it["id"]),
            "article": ARTICLE_OVERRIDE.get(it["id"], ARTICLE.get(it["cat"], "core")),
            "evidence_code": EVIDENCE_CODE[it["id"]],
            "system": SYSTEM_ITEMS.get(it["id"]),
            "scope": "project" if it["id"] in PROJECT_LEVEL else "unit",
            "example": EXAMPLES.get(it["id"], ""),
            "sample_html": src["SAMPLES"].get(it["id"], ""),
        })
    for x in EXTRA_ITEMS:
        items.append({
            "id": x["id"], "cat": x["cat"], "name": x["name"], "name_zh": x["name_zh"],
            "requirement": x["requirement"], "requirement_zh": x["requirement_zh"], "form_zh": x["form_zh"],
            "legal": x["legal"], "logic": x["logic"], "logic_zh": x["logic_zh"], "td": x["td"],
            "fields": [_field(s, {}) for s in x["fields"]], "table": None,
            "article": x["article"], "evidence_code": x["evidence_code"], "system": None,
            "scope": "unit", "example": x["example"], "sample_html": EXTRA_SAMPLES.get(x["id"], ""),
        })
    items.sort(key=lambda i: (i["cat"], i["id"]))
    names = {"T00": "Cover Information 封面信息表"}
    extra_ids = [x["id"] for x in EXTRA_ITEMS]
    td_sections = []
    for s in src["TD_SECTIONS"]:
        ids = list(s["items"])
        if s["no"] in ("6", "17"):
            ids += [i for i in extra_ids if i not in ids]
        td_sections.append({"no": s["no"], "name": names.get(s["no"], s["nm"]), "items": ids})
    OUT.write_text(json.dumps({"categories": cats, "items": items, "td_sections": td_sections},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(cats)} categories, {len(items)} items, "
          f"{len(td_sections)} TD sections")


if __name__ == "__main__":
    main()
