"""
SportsLax RAG 引擎
基于向量检索的体育法律知识库检索模块
支持：国际体育法律条款、CAS仲裁案例、WADA反兴奋剂规则、运动员权利保护等
"""
import os
from typing import Optional
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.logger_handler import logger
from model.factory import embed_model
from rag.obsidian_loader import load_vault_documents

# 向量库持久化路径
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")


# ─────────────────────────────────────────────
# 内置体育法律知识库（静态 RAG 语料）
# ─────────────────────────────────────────────
SPORTS_LAW_KNOWLEDGE = [
    # ── CAS 仲裁 ──────────────────────────────
    Document(
        page_content="""体育仲裁法院（CAS）是总部位于瑞士洛桑的国际体育仲裁机构，
由国际奥委会于1984年设立。CAS仲裁具有终局性，裁决可在155个国家通过《纽约公约》强制执行。
主要受理：反兴奋剂上诉、资格纠纷、合同争议、转会纠纷及奥运会现场仲裁。
上诉时效：通常为21天，奥运期间为24小时。
仲裁费用：1000瑞士法郎起，普通程序约需1–3年，快速程序3–6个月。""",
        metadata={"source": "CAS基础知识", "category": "仲裁机构", "language": "zh"}
    ),
    Document(
        page_content="""CAS仲裁程序分为四类：
1. 普通仲裁（OA）：处理当事方之间的原始纠纷，适用于合同、侵权等。
2. 上诉仲裁（AAA）：对国际体育联合会或国家奥委会决定的上诉。
3. 临时仲裁（Ad Hoc）：奥运会及大型赛事期间的紧急仲裁，24小时内出裁决。
4. 调解（Mediation）：非对抗性争议解决，成功率约80%。
仲裁地为洛桑，适用瑞士私法；当事方可协议选择适用法律。""",
        metadata={"source": "CAS程序规则", "category": "仲裁程序", "language": "zh"}
    ),

    # ── WADA 反兴奋剂 ──────────────────────────
    Document(
        page_content="""世界反兴奋剂机构（WADA）制定《世界反兴奋剂条例》（Code），
当前版本为2021年版，适用于超过200个国家和地区。
禁用清单（Prohibited List）每年1月1日更新，分为三类：
- S类：任何时间禁用物质（合成代谢类固醇、肽类激素、利尿剂等）
- 赛内禁用物质（兴奋剂、麻醉剂等）
- 特定运动禁用物质（射击项目中的β受体阻断剂）
运动员须承担"严格责任"——无论是否故意，阳性结果均构成违规。""",
        metadata={"source": "WADA条例", "category": "反兴奋剂", "language": "zh"}
    ),
    Document(
        page_content="""反兴奋剂违规（ADRV）的处罚标准：
- 首次违规：通常禁赛4年（故意）或2年（非故意）
- 特定物质首次违规：最高2年，可降至警告
- 再次违规：禁赛期加倍，最高永久禁赛
减轻情节：无重大过失、举报协助、及时认罪（可减少25%）
治疗用途豁免（TUE）：需在使用前30天申请，紧急情况事后申请
申诉路径：国家反兴奋剂组织 → 国际体育联合会 → CAS""",
        metadata={"source": "WADA处罚规则", "category": "反兴奋剂", "language": "zh"}
    ),

    # ── FIFA / 足球转会 ────────────────────────
    Document(
        page_content="""FIFA转会纠纷解决机制：
争议解决室（DRC）处理球员与俱乐部之间的合同纠纷，包括：
- 合同单方终止（正当理由 vs 无正当理由）
- 工资拖欠（超过2个月可构成正当理由终止）
- 培训赔偿（12–21岁球员转会时向培训俱乐部支付）
- 团结机制（转会费的5%分配给青训俱乐部）
DRC裁决后可向CAS上诉；涉及国际转会须通过FIFA转会匹配系统（TMS）。
赛季中保护期：合同头3年（年龄<28岁）或头2年不得无故终止。""",
        metadata={"source": "FIFA转会规则", "category": "足球法律", "language": "zh"}
    ),

    # ── 运动员资格与国籍 ──────────────────────
    Document(
        page_content="""运动员资格与国籍代表规则：
- 奥林匹克宪章第41条：运动员须持有代表国国籍；改变国籍代表须经IOC批准。
- 等待期：通常3年，特殊情况（出生国/成长国）可豁免。
- 双重国籍：允许，但只能代表一国参赛。
- FIFA国籍规则：曾代表A国参加正式国际比赛后，须等5年才能转换国籍代表。
- 归化运动员：各单项联合会有独立规定，部分设有上限配额。
国籍争议的申诉机构：相关国际单项联合会 → CAS。""",
        metadata={"source": "运动员资格规则", "category": "资格与国籍", "language": "zh"}
    ),

    # ── 运动员权利保护 ────────────────────────
    Document(
        page_content="""运动员基本权利保护框架：
1. 正当程序权：在任何纪律程序中享有被告知、申辩和上诉的权利。
2. 隐私权：反兴奋剂检测须符合《欧洲人权公约》第8条。
3. 劳动权：职业运动员通常受劳动法保护（各国不同，部分国家运动员被认定为雇员）。
4. 肖像权与商业权利：运动员对自身形象拥有权利，须警惕赞助合同中的排他条款。
5. 安全保障权：运动员有权拒绝不安全的训练或比赛条件。
6. 平等参与权：禁止基于性别、种族、残障等理由歧视。
国际运动员委员会（IOC Athletes' Commission）提供政策倡导渠道。""",
        metadata={"source": "运动员权利", "category": "运动员保护", "language": "zh"}
    ),

    # ── 赛事合同与赞助 ────────────────────────
    Document(
        page_content="""体育赛事合同与赞助法律要点：
- 赞助合同须明确：独家性范围、地域、期限、媒体使用权、肖像授权范围。
- 模糊条款风险：注意"全球独家"与"区域独家"的区别，避免冲突赞助。
- 解约条款：因不可抗力（如赛事取消）、违约（绩效未达标）的解约条件。
- 代言合同：包含"道德条款"（morality clause），运动员负面新闻可触发解约。
- 分成协议：联赛收入分配须审查计算方式与审计权利。
- 形象权保护：未经授权使用运动员肖像可构成侵权，赔偿可达实际损失3倍。""",
        metadata={"source": "体育合同法", "category": "合同与商业", "language": "zh"}
    ),

    # ── 反歧视与平等 ──────────────────────────
    Document(
        page_content="""体育领域反歧视与平等原则：
- IOC《奥林匹克宪章》第6条：禁止任何形式歧视。
- UEFA、FIFA反歧视规程：罚款、积分扣除、赛事停办等处罚。
- 性别平等：CAS已多次裁定，技术上的性别检测（如雄激素规则）须符合比例原则。
- 残障运动员：残奥会运动员享有与奥运会同等的法律保护框架。
- 种族歧视：FIFA/UEFA可对俱乐部因球迷行为予以处罚（替代责任）。
- 性骚扰：国际奥委会《安全运动框架》要求各国奥委会建立投诉机制。""",
        metadata={"source": "体育反歧视规则", "category": "平等与反歧视", "language": "zh"}
    ),

    # ── 保险与伤害赔偿 ────────────────────────
    Document(
        page_content="""运动员伤害与保险法律：
- 职业运动员伤害：雇主（俱乐部）通常负有工伤赔偿责任。
- 伤害豁免协议：仅对普通过失有效，重大过失或故意伤害不可豁免。
- 第三方责任：因对方运动员故意或严重违规导致的伤害可提起民事诉讼。
- 强制保险：多数职业联赛要求俱乐部为运动员购买意外伤害险。
- 职业终结保险：保障因伤永久丧失运动能力的运动员。
- 赛事组织者责任：对观众和参赛者的安全负有注意义务（duty of care）。""",
        metadata={"source": "运动员保险与伤害", "category": "伤害与保险", "language": "zh"}
    ),

    # ── 媒体转播权 ────────────────────────────
    Document(
        page_content="""体育媒体转播权法律框架：
- 转播权属于赛事组织者（版权法保护）；未经授权转播构成侵权。
- 分层授权：地区/全球、独家/非独家、平台类型（电视/网络/移动端）。
- 简短报道权（Short Reporting Right）：新闻报道目的可使用不超过90秒片段。
- OTT平台须遵守各国广播许可要求。
- 赛事现场直播的街拍、社媒传播须注意平台对UGC的政策差异。
- 争议案例：CAS常见裁决认为，地理封锁不影响运动员在赛地分享自身比赛片段的权利。""",
        metadata={"source": "媒体转播权", "category": "媒体与版权", "language": "zh"}
    ),

    # ── 运动员经纪人制度 ──────────────────────
    Document(
        page_content="""运动员经纪人法律制度：
- FIFA经纪人（球员代理人）：2023年新规要求在FIFA Football Agent Platform（FFAP）注册，
  通过测试方可执业；代理费上限：合同总额的3%（由俱乐部支付）或10%（由球员支付）。
- 其他体育项目：国际单项联合会各有不同规定，ITF（网球）、FIBA（篮球）均有经纪人认证制度。
- 利益冲突：经纪人不得同时代理买卖双方，须披露任何关联关系。
- 合同纠纷：经纪人与运动员之间的合同纠纷通常由所在国法院或相关仲裁机构处理。
- 未成年人保护：为未成年运动员提供经纪服务须取得监护人同意，部分国家设有额外限制。""",
        metadata={"source": "运动员经纪人规则", "category": "经纪人制度", "language": "zh"}
    ),

    # ── 未成年运动员保护 ──────────────────────
    Document(
        page_content="""未成年运动员法律保护框架：
- 国际劳工组织（ILO）公约：禁止对儿童进行有害劳动，体育培训不得剥夺受教育权利。
- FIFA转会规则第19条：严格限制未满18岁球员的国际转会，仅允许以下三种例外情况：
  1. 随家长因非足球原因跨国迁居；2. 欧盟/欧洲经济区成员国间年满16岁球员转会；
  3. 距离俱乐部50公里内跨境生活。
- 培训合同：各国对未成年人签署专业体育合同的年龄下限有明确规定（通常16岁以上）。
- 人身保护：国际奥委会《安全运动框架》要求各奥委会建立未成年运动员保护政策，
  包括举报机制、背景调查要求和教练行为守则。
- 案例警示：美国体操队性虐待案（Nassar案）推动了各国加强对未成年运动员的法律保护。""",
        metadata={"source": "未成年运动员保护", "category": "未成年人保护", "language": "zh"}
    ),

    # ── 体育仲裁完整流程 ──────────────────────
    Document(
        page_content="""CAS仲裁完整流程指南（上诉仲裁为例）：
第一步 — 确认上诉资格：
  - 须为国际体育联合会或国家奥委会的决定；
  - 申请人须穷尽内部申诉程序（除非规则允许直接上诉）。
第二步 — 提交上诉状（Statement of Appeal）：
  - 时限：通常为收到决定书后21天（合同中可约定其他期限）；
  - 须包含：当事方信息、被上诉决定、上诉理由概述、仲裁员提名。
第三步 — 提交上诉理由书（Appeal Brief）：
  - 时限：提交上诉状后10天内；
  - 须包含：详细事实陈述、法律论据、证据目录、证人/专家名单。
第四步 — 答辩：被上诉方提交答辩书（20天内）。
第五步 — 听证：可申请口头听证；在线听证亦可接受。
第六步 — 裁决：普通程序约1-3年；快速程序3-6个月；Ad Hoc 24小时。
注意事项：全程须委托在CAS名单上的律师；裁决公开发布于CAS官网。""",
        metadata={"source": "CAS仲裁流程", "category": "仲裁程序", "language": "zh"}
    ),

    # ── 兴奋剂检测程序 ────────────────────────
    Document(
        page_content="""反兴奋剂检测程序与运动员权利：
赛内检测（In-Competition Testing）：
  - 通常在比赛结束后1小时内由DCO（兴奋剂控制官）通知运动员；
  - 运动员有权要求陪同人员在场，但不可拒绝检测（拒绝等同阳性）；
  - 样本分为A瓶和B瓶；A瓶检测阳性后，运动员可申请B瓶复检（须在规定时间内提出）。
赛外检测（Out-of-Competition Testing）：
  - WADA"运动员行踪信息系统"（ADAMS）要求国家/国际级运动员每季度提前申报行踪；
  - 一年内三次"未能完成检测"（Whereabouts Failure）可构成ADRV。
运动员在检测中的权利：
  - 有权获得DCO资质证明；
  - 有权选择检测设施；
  - 有权对检测过程提出书面异议（不影响样本收集）；
  - A瓶阳性通知后，有权收到完整的实验室文件包（Laboratory Documentation Package）。""",
        metadata={"source": "反兴奋剂检测程序", "category": "反兴奋剂", "language": "zh"}
    ),

    # ── 体育赌博与比赛操纵 ────────────────────
    Document(
        page_content="""体育比赛操纵与赌博法律规制：
- 国际框架：《马卡托尼公约》（Council of Europe Convention on the Manipulation of Sports Competitions，2014年）
  是全球首个专门针对比赛操纵的国际条约。
- 常见形式：故意输球（打假球）、局部操纵（特定时间段让分）、内幕信息交易。
- 处罚：各单项联合会对操纵比赛的处罚通常为禁赛5年至终身；
  刑事责任：多国已将操纵体育比赛列为刑事犯罪（最高可判数年有期徒刑）。
- 运动员义务：须向所属联合会/俱乐部报告任何操纵接触（不报告本身亦构成违规）；
  通常禁止在自身参与的比赛中进行任何投注。
- 证据标准：与反兴奋剂相同，适用"comfortable satisfaction"标准（低于刑事证明标准）。
- 中国相关案例：中国足协对多起假球案处以终身禁赛，并移送司法机关追究刑责。""",
        metadata={"source": "比赛操纵与赌博", "category": "比赛操纵", "language": "zh"}
    ),

    # ── 运动员退役与社会保障 ──────────────────
    Document(
        page_content="""运动员退役及社会保障法律议题：
- 退役运动员劳动权：职业运动员退役后能否享有失业救济取决于各国是否认定其为"雇员"；
  部分国家（如法国、德国）已立法明确职业运动员的雇员身份。
- 养老金：部分职业联赛（NBA、NFL等）设有专属养老金计划；
  国际运动员通常缺乏类似保障，须自行规划。
- 脑震荡/职业伤病赔偿：NFL脑震荡集体诉讼（10亿美元和解）是职业伤病诉讼里程碑；
  运动员须注意合同中"伤病豁免条款"的范围。
- 肖像权与退役后收入：退役后赞助合同通常终止，但部分合同含"退役后条款"；
  传奇球员/运动员的历史形象使用权是近年新兴法律议题（如NBA球员协会集体授权）。
- 转型支持：IOC"运动员365"计划为退役运动员提供职业转型培训和法律援助资源。""",
        metadata={"source": "运动员退役保障", "category": "运动员保护", "language": "zh"}
    ),
]


def build_vector_store(docs: list[Document] | None = None, force_rebuild: bool = False) -> Chroma:
    """
    构建或加载向量知识库
    若已存在持久化数据则直接加载，否则用内置语料构建。

    Args:
        docs: 可选，指定要建库的文档列表（供 file watcher 重建时使用）
        force_rebuild: True 时强制清空并重建向量库（用于 vault 文档更新后）
    """
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

    # 判断是否已有持久化数据
    is_existing = os.path.exists(os.path.join(CHROMA_PERSIST_DIR, "chroma.sqlite3"))

    # 强制重建：先清空旧数据
    if force_rebuild and is_existing:
        import shutil
        shutil.rmtree(CHROMA_PERSIST_DIR, ignore_errors=True)
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        is_existing = False
        logger.info("[RAG] 强制重建：已清空旧向量库")

    # 加载 Obsidian vault 文档（每次重建都重新读取文件系统）
    vault_docs = load_vault_documents()
    if vault_docs:
        logger.info(f"[RAG] 加载 {len(vault_docs)} 个 Obsidian vault 文档")

    if is_existing and docs is None:
        logger.info("[RAG] 加载已有向量知识库...")
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embed_model,
            collection_name="sports_law"
        )

    # 新建或追加文档
    # 启动时冷建：内置知识 + vault
    # file watcher 触发：传入 docs（仅 vault）
    if docs is None:
        source_docs = SPORTS_LAW_KNOWLEDGE + vault_docs
        logger.info(
            f"[RAG] 冷启动：内置 {len(SPORTS_LAW_KNOWLEDGE)} 条 + "
            f"vault {len(vault_docs)} 条 → 构建向量库"
        )
    else:
        source_docs = docs + vault_docs
        logger.info(f"[RAG] 追加构建：自定义 {len(docs)} 条 + vault {len(vault_docs)} 条")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", "。", "；", " "]
    )
    chunks = splitter.split_documents(source_docs)
    logger.info(f"[RAG] 切分文档 {len(chunks)} 个分块，开始向量化...")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embed_model,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name="sports_law"
    )
    logger.info("[RAG] 向量知识库构建完成")
    return vectorstore


def get_rag_retriever(k: int = 5):
    """
    获取 RAG 检索器
    Returns:
        LangChain Retriever 对象
    """
    vectorstore = build_vector_store()
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )


def retrieve_sports_law(query: str, k: int = 5) -> list[dict]:
    """
    根据查询语句从向量知识库中检索相关体育法律知识
    Args:
        query: 查询文本
        k: 返回结果数量
    Returns:
        检索结果列表，每项包含 content 和 metadata
    """
    try:
        retriever = get_rag_retriever(k=k)
        docs = retriever.invoke(query)
        results = []
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "未知来源"),
                "category": doc.metadata.get("category", "未分类")
            })
        logger.info(f"[RAG] 检索到 {len(results)} 条相关知识")
        return results
    except Exception as e:
        logger.error(f"[RAG] 检索失败: {e}")
        return []


def add_custom_documents(documents: list[Document]) -> bool:
    """
    向知识库追加自定义文档
    Args:
        documents: 文档列表
    Returns:
        是否成功
    """
    try:
        vectorstore = build_vector_store()
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        chunks = splitter.split_documents(documents)
        vectorstore.add_documents(chunks)
        logger.info(f"[RAG] 成功追加 {len(chunks)} 个分块到知识库")
        return True
    except Exception as e:
        logger.error(f"[RAG] 追加文档失败: {e}")
        return False
