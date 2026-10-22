from uuid import uuid4
from sqlalchemy import select,text
from sqlalchemy.dialects.postgresql import insert
from app.analysis.config import DEFINITIONS,CONFIG_TYPES,validate_rule,default_profile
from app.models.entities import AnalysisRule


def bootstrap_rules(session):
    # 不覆盖已有编号的任何版本或用户配置。
    existing=set(session.scalars(select(AnalysisRule.code)))
    added=0
    for definition in default_profile()['rules']:
        if definition['code'] in existing:continue
        payload={k:v for k,v in definition.items() if k!='required_for_normal'}
        payload.update(id=uuid4(),enabled=True)
        statement=insert(AnalysisRule).values(**payload).on_conflict_do_nothing(constraint='uq_rule_code_version')
        added+=len(session.execute(statement.returning(AnalysisRule.id)).all())
    session.commit()
    return {'added':added,'warning':default_profile()['warning']}


def selected_rules(session):
    unknown=session.scalar(select(AnalysisRule.code).where(AnalysisRule.enabled.is_(True),AnalysisRule.code.not_in(list(DEFINITIONS))).limit(1))
    if unknown:raise ValueError(f'存在未注册的启用规则：{unknown}，请停用或注册后重试')
    grouped={}
    for rule in session.scalars(select(AnalysisRule).where(AnalysisRule.code.in_(DEFINITIONS))):
        grouped.setdefault(rule.code,[]).append(rule)
    if set(DEFINITIONS)-grouped.keys():raise ValueError('请先初始化全部演示规则，再执行分析')
    selected=[]
    for code,versions in grouped.items():
        active=[r for r in versions if r.enabled]
        if len(active)>1:raise ValueError(f'{code}有多个启用版本，请保留一个启用版本')
        rule=active[0] if active else max(versions,key=lambda r:tuple(int(x) for x in r.version.split('.')))
        validate_rule(rule)
        selected.append(rule)
    return selected


def rule_payload(rule):
    return {'id':str(rule.id),'code':rule.code,'name':rule.name,'version':rule.version,'enabled':rule.enabled,
            'function_key':rule.function_key,'applicable_states':rule.applicable_states,'input_parameters':rule.input_parameters,
            'configuration':rule.configuration,'config_schema':CONFIG_TYPES[rule.code].model_json_schema(),
            'required_for_normal':True,'warning':default_profile()['warning']}


def publish_version(session,code,options):
    if code not in DEFINITIONS:raise ValueError('未知规则编号')
    if not session.scalar(select(text('pg_try_advisory_xact_lock(1862400302)'))):raise ValueError('规则正在修改，请稍后重试')
    versions=list(session.scalars(select(AnalysisRule).where(AnalysisRule.code==code).with_for_update()))
    if not versions:raise ValueError('请先初始化规则')
    if any(r.version==options.version for r in versions):raise ValueError('版本号已存在，请使用新版本号')
    if tuple(map(int,options.version.split('.')))<=max(tuple(map(int,r.version.split('.'))) for r in versions):raise ValueError('新版本必须高于历史版本')
    definition=DEFINITIONS[code]
    rule=AnalysisRule(code=code,name=definition['name'],version=options.version,
                      configuration=options.configuration,applicable_states=options.applicable_states,
                      input_parameters=definition['input_parameters'],function_key=definition['function_key'],enabled=options.enabled)
    validate_rule(rule)
    for old in versions:old.enabled=False
    session.add(rule);session.commit();session.refresh(rule)
    return rule
