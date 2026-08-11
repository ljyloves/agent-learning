"""Seed a synthetic molecular-and-cell biology question bank.

Revision ID: 20260811_0003
Revises: 20260810_0002
Create Date: 2026-08-11
"""

from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260811_0003"
down_revision: str | None = "20260810_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MOCK_SOURCE_ID = "bio016-molecular-cell-mock-bank"
SEED_NAMESPACE = uuid.UUID("cae2841b-d8d1-47a7-9631-5df57b621a4c")
COMPETENCY_BY_VARIANT = ("BIO-C1", "BIO-C2", "BIO-C3", "BIO-C2")


CONCEPTS = [
    {
        "knowledge_point_code": "BIO-M1-K01",
        "title": "细胞中的水",
        "correct": "细胞鲜重中含量最多的化合物通常是水。",
        "distractors": [
            "结合水可自由流动并直接参与物质运输。",
            "自由水含量升高通常意味着细胞代谢减弱。",
            "水只作为溶剂，不参与细胞内的化学反应。",
        ],
        "blank_stem": "细胞鲜重中含量最多的化合物是____。",
        "blank_answer": "水",
        "explanation": "水是活细胞鲜重中含量最多的化合物，自由水还能参与运输和多种代谢反应。",
    },
    {
        "knowledge_point_code": "BIO-M1-K01",
        "title": "无机盐的作用",
        "correct": "无机盐常以离子形式存在，并参与维持细胞的渗透压和酸碱平衡。",
        "distractors": [
            "细胞中的无机盐都以难溶化合物形式存在。",
            "无机盐是细胞生命活动的主要能源物质。",
            "无机盐含量很少，因此不会影响细胞功能。",
        ],
        "blank_stem": "细胞中大多数无机盐以____形式存在。",
        "blank_answer": "离子",
        "explanation": "无机盐含量虽少，但许多以离子形式参与渗透压、酸碱平衡和化合物组成。",
    },
    {
        "knowledge_point_code": "BIO-M1-K01",
        "title": "蛋白质的基本单位",
        "correct": "组成蛋白质的基本单位是氨基酸。",
        "distractors": [
            "氨基酸通过磷酸二酯键连接成蛋白质。",
            "蛋白质的功能只取决于氨基酸数量。",
            "所有蛋白质都由完全相同的氨基酸序列组成。",
        ],
        "blank_stem": "组成蛋白质的基本单位是____。",
        "blank_answer": "氨基酸",
        "explanation": "氨基酸经脱水缩合形成肽链，氨基酸种类、数量、排列和空间结构共同影响蛋白质功能。",
    },
    {
        "knowledge_point_code": "BIO-M1-K01",
        "title": "核酸的组成",
        "correct": "核酸的基本单位是核苷酸。",
        "distractors": [
            "DNA和RNA所含的五碳糖完全相同。",
            "核酸只分布在真核细胞的细胞核中。",
            "核苷酸由氨基酸、五碳糖和碱基组成。",
        ],
        "blank_stem": "核酸的基本组成单位是____。",
        "blank_answer": "核苷酸",
        "explanation": "一个核苷酸由磷酸、五碳糖和含氮碱基组成，核酸包括DNA和RNA。",
    },
    {
        "knowledge_point_code": "BIO-M1-K02",
        "title": "细胞膜结构",
        "correct": "磷脂双分子层构成细胞膜的基本支架。",
        "distractors": [
            "细胞膜中的蛋白质均匀覆盖在膜的两侧。",
            "细胞膜是静止不动且完全对称的结构。",
            "细胞膜只允许水分子通过。",
        ],
        "blank_stem": "构成细胞膜基本支架的是____。",
        "blank_answer": "磷脂双分子层",
        "explanation": "流动镶嵌模型认为磷脂双分子层是基本支架，蛋白质以不同方式分布其中。",
    },
    {
        "knowledge_point_code": "BIO-M1-K02",
        "title": "线粒体功能",
        "correct": "线粒体是有氧呼吸的主要场所。",
        "distractors": [
            "线粒体是光合作用产生氧气的场所。",
            "所有原核细胞都具有结构完整的线粒体。",
            "线粒体基质是蛋白质合成的唯一场所。",
        ],
        "blank_stem": "真核细胞进行有氧呼吸的主要场所是____。",
        "blank_answer": "线粒体",
        "explanation": "有氧呼吸第二、第三阶段主要在线粒体基质和内膜上进行。",
    },
    {
        "knowledge_point_code": "BIO-M1-K02",
        "title": "核糖体功能",
        "correct": "核糖体是细胞合成蛋白质的场所。",
        "distractors": [
            "核糖体具有双层膜结构。",
            "核糖体只存在于动物细胞中。",
            "核糖体负责细胞内脂质的分解。",
        ],
        "blank_stem": "细胞内合成蛋白质的场所是____。",
        "blank_answer": "核糖体",
        "explanation": "核糖体无膜结构，广泛存在于原核和真核细胞中，是翻译和蛋白质合成的场所。",
    },
    {
        "knowledge_point_code": "BIO-M1-K02",
        "title": "细胞核功能",
        "correct": "细胞核是遗传信息库，也是细胞代谢和遗传的控制中心。",
        "distractors": [
            "核膜阻止所有大分子在核质之间运输。",
            "染色质和染色体是两种成分完全不同的物质。",
            "没有细胞核的细胞一定不能进行任何代谢。",
        ],
        "blank_stem": "真核细胞中储存主要遗传信息的结构是____。",
        "blank_answer": "细胞核",
        "explanation": "细胞核中DNA携带主要遗传信息，并通过基因表达调控细胞生命活动。",
    },
    {
        "knowledge_point_code": "BIO-M1-K03",
        "title": "被动运输",
        "correct": "被动运输顺浓度梯度进行，通常不消耗细胞代谢产生的能量。",
        "distractors": [
            "自由扩散必须依赖膜上载体蛋白。",
            "协助扩散可以逆浓度梯度运输物质。",
            "被动运输速率与膜两侧浓度差无关。",
        ],
        "blank_stem": "物质顺浓度梯度且不消耗细胞代谢能量的运输方式称为____。",
        "blank_answer": "被动运输",
        "explanation": "自由扩散和协助扩散都属于被动运输，其共同特征是顺浓度梯度且不直接耗能。",
    },
    {
        "knowledge_point_code": "BIO-M1-K03",
        "title": "主动运输",
        "correct": "主动运输可以逆浓度梯度转运物质，并需要能量和载体蛋白。",
        "distractors": [
            "主动运输只能将物质运出细胞。",
            "主动运输不受温度和呼吸作用影响。",
            "氧气进入细胞的方式属于主动运输。",
        ],
        "blank_stem": "物质逆浓度梯度跨膜运输的典型方式是____。",
        "blank_answer": "主动运输",
        "explanation": "主动运输需要膜上载体蛋白和能量，可使细胞维持膜两侧特定物质的浓度差。",
    },
    {
        "knowledge_point_code": "BIO-M1-K03",
        "title": "渗透作用",
        "correct": "水分子可通过半透膜由相对低浓度溶液一侧向相对高浓度溶液一侧扩散。",
        "distractors": [
            "渗透作用只发生在动物细胞中。",
            "植物细胞吸水时原生质层一定与细胞壁分离。",
            "发生渗透作用不需要存在半透膜。",
        ],
        "blank_stem": "水分子通过半透膜进行的扩散称为____。",
        "blank_answer": "渗透作用",
        "explanation": "渗透作用发生的条件包括半透膜和膜两侧溶液存在浓度差。",
    },
    {
        "knowledge_point_code": "BIO-M1-K04",
        "title": "酶的催化作用",
        "correct": "酶通过降低化学反应的活化能提高反应速率。",
        "distractors": [
            "酶能提高化学反应产物的总能量。",
            "酶在反应前后数量和性质一定发生永久改变。",
            "酶可以使热力学上不能发生的反应发生。",
        ],
        "blank_stem": "酶通过降低化学反应的____来提高反应速率。",
        "blank_answer": "活化能",
        "explanation": "酶不能改变反应平衡和能量总变化，其催化本质是降低活化能。",
    },
    {
        "knowledge_point_code": "BIO-M1-K04",
        "title": "酶的作用条件",
        "correct": "温度和pH会影响酶的活性，过高温度可能使酶空间结构破坏。",
        "distractors": [
            "低温会使所有酶永久失活。",
            "任何酶的最适温度和最适pH都相同。",
            "提高底物浓度可无限提高酶促反应速率。",
        ],
        "blank_stem": "高温导致酶活性降低，通常是因为酶的____遭到破坏。",
        "blank_answer": "空间结构",
        "explanation": "酶活性受温度、pH、底物浓度等因素影响，高温可能导致蛋白质类酶变性。",
    },
    {
        "knowledge_point_code": "BIO-M1-K04",
        "title": "ATP的作用",
        "correct": "ATP是细胞生命活动的直接能源物质。",
        "distractors": [
            "ATP是细胞内唯一的储能物质。",
            "ATP分子中不含磷酸基团。",
            "ATP合成只能发生在线粒体中。",
        ],
        "blank_stem": "细胞生命活动常用的直接能源物质是____。",
        "blank_answer": "ATP",
        "explanation": "ATP与ADP快速相互转化，在吸能反应和放能反应之间传递能量。",
    },
    {
        "knowledge_point_code": "BIO-M1-K05",
        "title": "有氧呼吸",
        "correct": "有氧呼吸能将有机物较彻底地氧化分解并释放能量。",
        "distractors": [
            "有氧呼吸全过程都在线粒体中完成。",
            "有氧呼吸第一阶段不产生ATP。",
            "氧气直接参与有氧呼吸每一个阶段。",
        ],
        "blank_stem": "有氧呼吸第一阶段进行的场所是____。",
        "blank_answer": "细胞质基质",
        "explanation": "有氧呼吸第一阶段在细胞质基质进行，后续阶段主要在线粒体中进行。",
    },
    {
        "knowledge_point_code": "BIO-M1-K05",
        "title": "无氧呼吸",
        "correct": "无氧呼吸只释放有机物中的少量能量。",
        "distractors": [
            "乳酸发酵会产生酒精和二氧化碳。",
            "无氧呼吸只能发生在微生物中。",
            "无氧呼吸产生的ATP一定多于有氧呼吸。",
        ],
        "blank_stem": "人体骨骼肌细胞无氧呼吸的主要产物是____。",
        "blank_answer": "乳酸",
        "explanation": "无氧呼吸在细胞质基质中进行，动物细胞通常产生乳酸，释放能量较少。",
    },
    {
        "knowledge_point_code": "BIO-M1-K05",
        "title": "光合作用光反应",
        "correct": "光反应阶段可产生ATP和NADPH，并释放氧气。",
        "distractors": [
            "光反应阶段直接合成大量葡萄糖。",
            "光反应阶段只在叶绿体基质中进行。",
            "光反应阶段不需要色素吸收光能。",
        ],
        "blank_stem": "光合作用光反应的主要场所是叶绿体的____。",
        "blank_answer": "类囊体薄膜",
        "explanation": "叶绿体类囊体薄膜上的色素和酶参与光反应，形成ATP、NADPH并释放氧气。",
    },
    {
        "knowledge_point_code": "BIO-M1-K05",
        "title": "光合作用碳反应",
        "correct": "碳反应阶段利用ATP和NADPH将二氧化碳转化为有机物。",
        "distractors": [
            "碳反应阶段只能在完全黑暗条件下进行。",
            "碳反应阶段的场所是类囊体薄膜。",
            "碳反应阶段不受二氧化碳浓度影响。",
        ],
        "blank_stem": "光合作用固定二氧化碳的反应主要发生在叶绿体的____。",
        "blank_answer": "基质",
        "explanation": "碳反应在叶绿体基质中进行，利用光反应产物完成二氧化碳固定和还原。",
    },
    {
        "knowledge_point_code": "BIO-M1-K06",
        "title": "细胞周期",
        "correct": "连续分裂的细胞从一次分裂完成到下一次分裂完成经历一个细胞周期。",
        "distractors": [
            "所有细胞都持续进行细胞周期。",
            "分裂期通常占细胞周期的绝大部分。",
            "DNA复制主要发生在有丝分裂后期。",
        ],
        "blank_stem": "真核细胞DNA复制主要发生在细胞周期的____。",
        "blank_answer": "分裂间期",
        "explanation": "细胞周期包括分裂间期和分裂期，DNA复制在分裂间期完成。",
    },
    {
        "knowledge_point_code": "BIO-M1-K06",
        "title": "有丝分裂染色体行为",
        "correct": "有丝分裂后期着丝粒分裂，姐妹染色单体分开并移向细胞两极。",
        "distractors": [
            "有丝分裂前期同源染色体联会。",
            "有丝分裂中期核膜和核仁重新出现。",
            "有丝分裂末期染色体数目加倍且不再恢复。",
        ],
        "blank_stem": "有丝分裂中染色体的着丝粒排列在赤道板上的时期是____。",
        "blank_answer": "中期",
        "explanation": "中期染色体着丝粒排列在赤道板，后期着丝粒分裂并移向两极。",
    },
    {
        "knowledge_point_code": "BIO-M1-K06",
        "title": "植物细胞胞质分裂",
        "correct": "高等植物细胞分裂末期在赤道板位置形成细胞板。",
        "distractors": [
            "高等植物细胞通过缢裂方式完成胞质分裂。",
            "细胞板最终发育成两个子细胞的细胞膜。",
            "植物细胞分裂不需要细胞器参与。",
        ],
        "blank_stem": "高等植物细胞有丝分裂末期形成的新结构是____。",
        "blank_answer": "细胞板",
        "explanation": "高尔基体相关囊泡在赤道板位置形成细胞板，细胞板进一步形成新的细胞壁。",
    },
    {
        "knowledge_point_code": "BIO-M1-K06",
        "title": "减数分裂",
        "correct": "减数分裂过程中染色体复制一次而细胞连续分裂两次。",
        "distractors": [
            "减数分裂产生的子细胞染色体数与母细胞相同。",
            "同源染色体分离发生在减数第二次分裂后期。",
            "减数分裂过程中不会发生非姐妹染色单体交换。",
        ],
        "blank_stem": "减数第一次分裂后期发生分离的是____。",
        "blank_answer": "同源染色体",
        "explanation": "减数第一次分裂的核心特征是同源染色体分离，使染色体数目减半。",
    },
    {
        "knowledge_point_code": "BIO-M1-K07",
        "title": "细胞分化",
        "correct": "细胞分化的实质通常是基因的选择性表达。",
        "distractors": [
            "同一个体不同体细胞含有完全不同的遗传物质。",
            "细胞分化后细胞形态改变但功能一定不变。",
            "已经分化的植物细胞不可能表现全能性。",
        ],
        "blank_stem": "细胞分化的实质通常是基因的____。",
        "blank_answer": "选择性表达",
        "explanation": "同一个体多数体细胞遗传信息相同，不同基因选择性表达导致结构和功能差异。",
    },
    {
        "knowledge_point_code": "BIO-M1-K07",
        "title": "细胞衰老与凋亡",
        "correct": "细胞凋亡是由基因决定的细胞自动结束生命的过程。",
        "distractors": [
            "细胞衰老时所有酶活性都会升高。",
            "细胞凋亡只会对生物体产生不利影响。",
            "被病原体感染细胞的清除一定属于细胞坏死。",
        ],
        "blank_stem": "由基因决定的细胞自动结束生命的过程称为细胞____。",
        "blank_answer": "凋亡",
        "explanation": "细胞凋亡受遗传机制调控，对个体发育和维持内环境稳定具有重要意义。",
    },
    {
        "knowledge_point_code": "BIO-M1-K07",
        "title": "癌细胞特征",
        "correct": "癌细胞能够无限增殖，且细胞膜表面部分糖蛋白减少。",
        "distractors": [
            "癌细胞的遗传物质不会发生任何改变。",
            "癌细胞只能在原发部位生长而不能扩散。",
            "正常细胞中的原癌基因和抑癌基因都没有生理功能。",
        ],
        "blank_stem": "能够无限增殖并可能发生扩散的异常细胞称为____。",
        "blank_answer": "癌细胞",
        "explanation": "原癌基因和抑癌基因异常可导致细胞癌变，癌细胞具有无限增殖、形态改变和易扩散等特点。",
    },
]


def stable_id(kind: str, number: int, detail: int = 0) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, f"bio016:{kind}:{number}:{detail}"))


def build_seed_rows() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    questions: list[dict] = []
    options: list[dict] = []
    knowledge_links: list[dict] = []
    competency_links: list[dict] = []

    for concept_index, concept in enumerate(CONCEPTS):
        for variant in range(4):
            number = concept_index * 4 + variant + 1
            question_id = stable_id("question", number)
            question_type = "single_choice"
            answer: str
            stem: str

            if variant < 2:
                stem_prefix = (
                    f"关于{concept['title']}，下列叙述正确的是（ ）。"
                    if variant == 0
                    else f"某同学复习“{concept['title']}”时整理了四条笔记，其中正确的是（ ）。"
                )
                raw_options = [concept["correct"], *concept["distractors"]]
                offset = (concept_index + variant) % 4
                arranged_options = raw_options[offset:] + raw_options[:offset]
                correct_position = arranged_options.index(concept["correct"])
                answer = "ABCD"[correct_position]
                stem = stem_prefix
                for position, content in enumerate(arranged_options):
                    options.append(
                        {
                            "id": stable_id("option", number, position),
                            "question_id": question_id,
                            "label": "ABCD"[position],
                            "content": content,
                            "position": position,
                        }
                    )
            elif variant == 2:
                question_type = "true_false"
                is_correct_statement = concept_index % 2 == 0
                statement = (
                    concept["correct"]
                    if is_correct_statement
                    else concept["distractors"][0]
                )
                stem = f"判断下列叙述是否正确：{statement}"
                answer = "正确" if is_correct_statement else "错误"
            else:
                question_type = "fill_blank"
                stem = concept["blank_stem"]
                answer = concept["blank_answer"]

            questions.append(
                {
                    "id": question_id,
                    "parent_question_id": None,
                    "source_id": MOCK_SOURCE_ID,
                    "question_type": question_type,
                    "stem": stem,
                    "answer": answer,
                    "explanation": concept["explanation"],
                    "position": number - 1,
                }
            )
            knowledge_links.append(
                {
                    "question_id": question_id,
                    "knowledge_point_code": concept["knowledge_point_code"],
                }
            )
            competency_links.append(
                {
                    "question_id": question_id,
                    "competency_code": COMPETENCY_BY_VARIANT[variant],
                }
            )

    return questions, options, knowledge_links, competency_links


def upgrade() -> None:
    question_sources = sa.table(
        "question_sources",
        sa.column("source_id", sa.String),
        sa.column("source_type", sa.String),
        sa.column("name", sa.String),
        sa.column("uri", sa.Text),
        sa.column("external_id", sa.String),
        sa.column("attribution", sa.Text),
        sa.column("license", sa.String),
    )
    questions_table = sa.table(
        "questions",
        sa.column("id", sa.String),
        sa.column("parent_question_id", sa.String),
        sa.column("source_id", sa.String),
        sa.column("question_type", sa.String),
        sa.column("stem", sa.Text),
        sa.column("answer", postgresql.JSONB),
        sa.column("explanation", sa.Text),
        sa.column("position", sa.Integer),
    )
    options_table = sa.table(
        "question_options",
        sa.column("id", sa.String),
        sa.column("question_id", sa.String),
        sa.column("label", sa.String),
        sa.column("content", sa.Text),
        sa.column("position", sa.Integer),
    )
    knowledge_links_table = sa.table(
        "question_knowledge_points",
        sa.column("question_id", sa.String),
        sa.column("knowledge_point_code", sa.String),
    )
    competency_links_table = sa.table(
        "question_core_competencies",
        sa.column("question_id", sa.String),
        sa.column("competency_code", sa.String),
    )

    questions, options, knowledge_links, competency_links = build_seed_rows()
    op.bulk_insert(
        question_sources,
        [
            {
                "source_id": MOCK_SOURCE_ID,
                "source_type": "manual",
                "name": "FlowGate BIO-016 分子与细胞合成测试题库",
                "uri": None,
                "external_id": "BIO-016",
                "attribution": "FlowGate synthetic fixture data; not for real assessment.",
                "license": "CC0-1.0",
            }
        ],
    )
    op.bulk_insert(questions_table, questions)
    op.bulk_insert(options_table, options)
    op.bulk_insert(knowledge_links_table, knowledge_links)
    op.bulk_insert(competency_links_table, competency_links)


def downgrade() -> None:
    question_ids = [row["id"] for row in build_seed_rows()[0]]
    questions_table = sa.table(
        "questions",
        sa.column("id", sa.String),
    )
    question_sources = sa.table(
        "question_sources",
        sa.column("source_id", sa.String),
    )
    op.execute(sa.delete(questions_table).where(questions_table.c.id.in_(question_ids)))
    op.execute(
        sa.delete(question_sources).where(
            question_sources.c.source_id == MOCK_SOURCE_ID
        )
    )
