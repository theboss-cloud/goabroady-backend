# backend/routes/meta.py
from flask import Blueprint, jsonify

meta_bp = Blueprint("meta", __name__, url_prefix="/api")

# 直接在代码里维护一份“唯一真源”的枚举
OPTIONS = {
    # 学籍状态 / 学历层级 / 年级
    "status": [
        {"value":"studying","label":"在校"},
        {"value":"graduated","label":"已毕业"},
    ],
    "degree_levels": [
        {"value":"junior_college","label":"专科"},
        {"value":"bachelor","label":"本科"},
        {"value":"master","label":"硕士"},
        {"value":"phd","label":"博士"},
    ],
    "years": [
        {"value":"year1","label":"大一/研一"},
        {"value":"year2","label":"大二/研二"},
        {"value":"year3","label":"大三"},
        {"value":"year4","label":"大四"},
    ],

    # 学校层次 / 专业大类
    "school_tiers": [
        {"value":"double_first_class","label":"双一流/985/211"},
        {"value":"regular","label":"普通本科"},
        {"value":"junior_college","label":"高职/专科"},
        {"value":"overseas_top","label":"海外名校"},
    ],
    "major_categories": [
        {"value":"business","label":"商科"},
        {"value":"cs","label":"计算机/数据"},
        {"value":"engineering","label":"工程"},
        {"value":"design","label":"设计"},
        {"value":"finance","label":"金融"},
        {"value":"law","label":"法律"},
    ],

    # 成绩体系 / 语言类型
    "gpa_scales": [
        {"value":"4","label":"4分制"},
        {"value":"5","label":"5分制"},
        {"value":"100","label":"百分制"},
    ],
    "lang_types": [
        {"value":"none","label":"无"},
        {"value":"ielts","label":"IELTS 雅思"},
        {"value":"toefl","label":"TOEFL iBT"},
        {"value":"duolingo","label":"Duolingo"},
    ],

    # 预算 / 奖学金
    "budget_buckets": [
        {"value":"<=10w","label":"≤ ¥10万/年"},
        {"value":"10-15w","label":"¥10–15万/年"},
        {"value":"15-20w","label":"¥15–20万/年"},
        {"value":"20-30w","label":"¥20–30万/年"},
        {"value":">30w","label":"≥ ¥30万/年"},
    ],
    "yes_no": [
        {"value":"yes","label":"需要"},
        {"value":"no","label":"不需要"},
    ],

    # 大区 / 国家（国家含 region 便于前端联动）
    "regions": [
        {"value":"europe","label":"欧洲"},
        {"value":"north_america","label":"北美"},
        {"value":"asia","label":"亚洲"},
        {"value":"oceania","label":"大洋洲"},
    ],
    "countries": [
        {"value":"uk","label":"英国","region":"europe"},
        {"value":"ie","label":"爱尔兰","region":"europe"},
        {"value":"de","label":"德国","region":"europe"},
        {"value":"fr","label":"法国","region":"europe"},
        {"value":"nl","label":"荷兰","region":"europe"},
        {"value":"us","label":"美国","region":"north_america"},
        {"value":"ca","label":"加拿大","region":"north_america"},
        {"value":"au","label":"澳大利亚","region":"oceania"},
        {"value":"sg","label":"新加坡","region":"asia"},
        {"value":"hk","label":"中国香港","region":"asia"},
        {"value":"mo","label":"中国澳门","region":"asia"},
    ],
}

@meta_bp.get("/meta/options")
def meta_options():
    """统一元数据接口：AssessmentWizard 直接请求这里。"""
    return jsonify(OPTIONS)
