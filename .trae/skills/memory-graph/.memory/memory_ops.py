import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

MEMORY_DIR = os.path.dirname(__file__)
SHORT_TERM_MEMORY_DURATION = 24  # 短期记忆持续时间（小时）
LONG_TERM_MEMORY_THRESHOLD = 0.8  # 转为长期记忆的权重阈值

def load_json(filename: str) -> Dict:
    path = os.path.join(MEMORY_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"last_updated": datetime.now().strftime("%Y-%m-%d")}

def save_json(filename: str, data: Dict) -> None:
    path = os.path.join(MEMORY_DIR, filename)
    data['last_updated'] = datetime.now().strftime("%Y-%m-%d")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _calculate_forgetting_curve(last_accessed: str, memory_type: str = 'short_term') -> float:
    """
    计算记忆遗忘曲线
    基于艾宾浩斯遗忘曲线
    """
    if not last_accessed:
        return 0.5
    
    try:
        last_time = datetime.strptime(last_accessed, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            last_time = datetime.strptime(last_accessed, "%Y-%m-%d")
        except ValueError:
            return 0.5
    
    hours_since_access = (datetime.now() - last_time).total_seconds() / 3600
    
    if memory_type == 'long_term':
        # 长期记忆遗忘较慢
        forgetting_rate = 0.05
    else:
        # 短期记忆遗忘较快
        forgetting_rate = 0.15
    
    # 艾宾浩斯遗忘曲线：R(t) = e^(-t/S)
    retention = max(0.1, min(1.0, pow(2.71828, -hours_since_access * forgetting_rate)))
    return retention

def retrieve_memory(query: str, max_results: int = 5) -> str:
    """
    基于query检索相关记忆
    """
    entities_data = load_json('entities.json')
    relations_data = load_json('relations.json')
    conversations_data = load_json('conversations.json')

    keywords = [w.strip().lower() for w in query.replace('?', ' ').split() if len(w.strip()) > 1]
    results = []

    for entity in entities_data.get('entities', []):
        score = 0
        name_lower = entity.get('name', '').lower()
        props_str = json.dumps(entity.get('properties', {}), ensure_ascii=False).lower()

        for kw in keywords:
            if kw in name_lower:
                score += 10
            if kw in props_str:
                score += 5

        if score > 0:
            # 应用遗忘曲线
            memory_type = entity.get('properties', {}).get('memory_type', 'short_term')
            last_accessed = entity.get('properties', {}).get('last_accessed', '')
            retention = _calculate_forgetting_curve(last_accessed, memory_type)
            score *= retention
            
            # 更新最后访问时间
            entity['properties']['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            entity_type = entity.get('type', 'unknown')
            name = entity.get('name', '')
            props = entity.get('properties', {})
            props_str = ', '.join([f"{k}:{v}" for k, v in list(props.items())[:3]])
            results.append({
                'type': 'entity',
                'score': score,
                'text': f"[{entity_type}] {name} - {props_str}" if props_str else f"[{entity_type}] {name}"
            })

    for rel in relations_data.get('relations', []):
        rel_str = json.dumps(rel, ensure_ascii=False).lower()
        for kw in keywords:
            if kw in rel_str:
                score = rel.get('weight', 0.5) * 5
                # 应用遗忘曲线到关系
                created_time = rel.get('created', '')
                retention = _calculate_forgetting_curve(created_time)
                score *= retention
                
                from_name = _get_entity_name(rel.get('from', ''), entities_data)
                to_name = _get_entity_name(rel.get('to', ''), entities_data)
                results.append({
                    'type': 'relation',
                    'score': score,
                    'text': f"[关系] {from_name} {rel.get('relation', '')} {to_name}"
                })
                break

    for conv in conversations_data.get('conversations', []):
        summary_lower = conv.get('summary', '').lower()
        entities_text = ' '.join(conv.get('entities_text', [])).lower()

        for kw in keywords:
            if kw in summary_lower or kw in entities_text:
                score = 5
                # 应用遗忘曲线到对话
                date_str = conv.get('date', '')
                retention = _calculate_forgetting_curve(date_str)
                score *= retention
                
                date = conv.get('date', 'unknown')
                summary = conv.get('summary', '')
                conclusion = conv.get('conclusion', '')
                text = f"[对话] {date} - {summary}"
                if conclusion:
                    text += f"，结论:{conclusion}"
                results.append({'type': 'conversation', 'score': score, 'text': text})
                break

    # 保存更新后的最后访问时间
    save_json('entities.json', entities_data)
    
    results.sort(key=lambda x: x['score'], reverse=True)
    top_results = results[:max_results]

    if not top_results:
        return "暂无相关记忆"

    output = "=== 相关记忆 ===\n"
    for r in top_results:
        output += f"{r['text']}\n"
    return output

def _get_entity_name(entity_id: str, entities_data: Dict) -> str:
    for e in entities_data.get('entities', []):
        if e.get('id') == entity_id:
            return e.get('name', entity_id)
    return entity_id

def _get_entity_id(entity_name: str, entities_data: Dict) -> Optional[str]:
    for e in entities_data.get('entities', []):
        if e.get('name') == entity_name:
            return e.get('id')
    return None

def _generate_entity_id() -> str:
    return f"e{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def _generate_conv_id() -> str:
    return f"c{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def save_memory(conversation_summary: str, extracted_entities: List[Dict], extracted_relations: List[Dict], emotional_state: str = None, context: str = None) -> str:
    """
    保存对话产生的记忆
    
    参数:
    - emotional_state: 情绪状态 (happy, sad, angry, excited, calm, etc.)
    - context: 情境描述
    """
    entities_data = load_json('entities.json')
    relations_data = load_json('relations.json')
    conversations_data = load_json('conversations.json')

    new_entity_ids = []
    for ent in extracted_entities:
        existing_id = _get_entity_id(ent.get('name', ''), entities_data)
        if existing_id:
            for e in entities_data['entities']:
                if e['id'] == existing_id:
                    e['properties'].update(ent.get('properties', {}))
                    e['properties']['last_seen'] = datetime.now().strftime("%Y-%m-%d")
                    e['properties']['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 检查是否需要从短期记忆转为长期记忆
                    if e['properties'].get('memory_type') == 'short_term':
                        access_count = e['properties'].get('access_count', 0) + 1
                        e['properties']['access_count'] = access_count
                        if access_count >= 3 or e.get('weight', 0) >= LONG_TERM_MEMORY_THRESHOLD:
                            e['properties']['memory_type'] = 'long_term'
                            e['properties']['consolidated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 添加情绪关联
                    if emotional_state:
                        e['properties']['emotional_states'] = e['properties'].get('emotional_states', [])
                        if emotional_state not in e['properties']['emotional_states']:
                            e['properties']['emotional_states'].append(emotional_state)
                    # 添加情境关联
                    if context:
                        e['properties']['contexts'] = e['properties'].get('contexts', [])
                        if context not in e['properties']['contexts']:
                            e['properties']['contexts'].append(context)
                    new_entity_ids.append(existing_id)
                    break
        else:
            new_id = _generate_entity_id()
            new_entity = {
                'id': new_id,
                'type': ent.get('type', 'concept'),
                'name': ent.get('name', ''),
                'properties': ent.get('properties', {})
            }
            new_entity['properties']['first_seen'] = datetime.now().strftime("%Y-%m-%d")
            new_entity['properties']['last_seen'] = datetime.now().strftime("%Y-%m-%d")
            new_entity['properties']['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_entity['properties']['memory_type'] = 'short_term'  # 新记忆默认为短期记忆
            new_entity['properties']['access_count'] = 1
            # 添加情绪关联
            if emotional_state:
                new_entity['properties']['emotional_states'] = [emotional_state]
            # 添加情境关联
            if context:
                new_entity['properties']['contexts'] = [context]
            entities_data['entities'].append(new_entity)
            new_entity_ids.append(new_id)

    for rel in extracted_relations:
        from_name = rel.get('from', '')
        to_name = rel.get('to', '')
        from_id = _get_entity_id(from_name, entities_data)
        to_id = _get_entity_id(to_name, entities_data)

        if not from_id and from_name:
            from_id = _generate_entity_id()
            entities_data['entities'].append({
                'id': from_id,
                'type': 'unknown',
                'name': from_name,
                'properties': {'auto_created': 'true', 'first_seen': datetime.now().strftime("%Y-%m-%d")}
            })

        if not to_id and to_name:
            to_id = _generate_entity_id()
            entities_data['entities'].append({
                'id': to_id,
                'type': 'unknown',
                'name': to_name,
                'properties': {'auto_created': 'true', 'first_seen': datetime.now().strftime("%Y-%m-%d")}
            })

        if from_id and to_id:
            rel_type = rel.get('relation', '关联')
            weight = rel.get('weight', 0.7)

            existing = False
            for r in relations_data['relations']:
                if r.get('from') == from_id and r.get('to') == to_id and r.get('relation') == rel_type:
                    r['weight'] = max(r['weight'], weight)
                    existing = True
                    break

            if not existing:
                relations_data['relations'].append({
                    'from': from_id,
                    'to': to_id,
                    'relation': rel_type,
                    'weight': weight,
                    'created': datetime.now().strftime("%Y-%m-%d")
                })

    conv_id = _generate_conv_id()
    conversation_data = {
        'id': conv_id,
        'date': datetime.now().strftime("%Y-%m-%d"),
        'summary': conversation_summary[:100],
        'entities': new_entity_ids,
        'entities_text': [ent.get('name', '') for ent in extracted_entities],
        'conclusion': extracted_relations[0].get('to', '') if extracted_relations else ''
    }
    # 添加情绪状态
    if emotional_state:
        conversation_data['emotional_state'] = emotional_state
    # 添加情境信息
    if context:
        conversation_data['context'] = context
    conversations_data['conversations'].append(conversation_data)

    save_json('entities.json', entities_data)
    save_json('relations.json', relations_data)
    save_json('conversations.json', conversations_data)

    return f"已保存 {len(extracted_entities)} 个实体, {len(extracted_relations)} 条关系"

def delete_memory(entity_name: str = None, conversation_id: str = None) -> str:
    """
    删除记忆（实体或对话）
    """
    entities_data = load_json('entities.json')
    relations_data = load_json('relations.json')
    conversations_data = load_json('conversations.json')

    deleted_count = 0

    if entity_name:
        entity_id = _get_entity_id(entity_name, entities_data)
        if entity_id:
            entities_data['entities'] = [e for e in entities_data['entities'] if e['id'] != entity_id]
            relations_data['relations'] = [r for r in relations_data['relations'] if r['from'] != entity_id and r['to'] != entity_id]
            deleted_count += 1

    if conversation_id:
        conversations_data['conversations'] = [c for c in conversations_data['conversations'] if c['id'] != conversation_id]
        deleted_count += 1

    save_json('entities.json', entities_data)
    save_json('relations.json', relations_data)
    save_json('conversations.json', conversations_data)

    return f"已删除 {deleted_count} 个记忆项目"

def consolidate_memories() -> str:
    """
    记忆巩固：将重要的短期记忆转换为长期记忆
    模拟大脑的记忆巩固过程
    """
    entities_data = load_json('entities.json')
    consolidated_count = 0

    for entity in entities_data.get('entities', []):
        if entity.get('properties', {}).get('memory_type') == 'short_term':
            access_count = entity.get('properties', {}).get('access_count', 0)
            last_accessed = entity.get('properties', {}).get('last_accessed', '')
            
            # 检查是否满足巩固条件
            if access_count >= 3:
                entity['properties']['memory_type'] = 'long_term'
                entity['properties']['consolidated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                consolidated_count += 1
            elif last_accessed:
                # 检查是否是近期频繁访问的记忆
                try:
                    last_time = datetime.strptime(last_accessed, "%Y-%m-%d %H:%M:%S")
                    hours_since_access = (datetime.now() - last_time).total_seconds() / 3600
                    if hours_since_access < 6 and access_count >= 2:
                        entity['properties']['memory_type'] = 'long_term'
                        entity['properties']['consolidated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        consolidated_count += 1
                except:
                    pass

    save_json('entities.json', entities_data)
    return f"已巩固 {consolidated_count} 个记忆"

def strengthen_memory(entity_name: str) -> str:
    """
    强化记忆：增加记忆的权重和访问计数
    模拟大脑的记忆强化过程
    """
    entities_data = load_json('entities.json')
    entity_id = _get_entity_id(entity_name, entities_data)

    if not entity_id:
        return "未找到该记忆"

    for entity in entities_data['entities']:
        if entity['id'] == entity_id:
            # 增加访问计数
            entity['properties']['access_count'] = entity['properties'].get('access_count', 0) + 1
            # 增加记忆强度
            entity['properties']['strength'] = min(1.0, entity['properties'].get('strength', 0.5) + 0.1)
            # 更新最后访问时间
            entity['properties']['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 如果是短期记忆，检查是否需要转为长期记忆
            if entity['properties'].get('memory_type') == 'short_term':
                if entity['properties']['access_count'] >= 3:
                    entity['properties']['memory_type'] = 'long_term'
                    entity['properties']['consolidated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break

    save_json('entities.json', entities_data)
    return f"已强化记忆: {entity_name}"

def cleanup_memories() -> str:
    """
    记忆清理：清理长期未使用的短期记忆
    模拟大脑的记忆清理过程
    """
    entities_data = load_json('entities.json')
    relations_data = load_json('relations.json')
    conversations_data = load_json('conversations.json')

    cleaned_count = 0
    current_time = datetime.now()

    # 清理长期未使用的短期记忆
    entities_to_keep = []
    for entity in entities_data.get('entities', []):
        memory_type = entity.get('properties', {}).get('memory_type', 'short_term')
        last_accessed = entity.get('properties', {}).get('last_accessed', '')
        
        if memory_type == 'short_term' and last_accessed:
            try:
                last_time = datetime.strptime(last_accessed, "%Y-%m-%d %H:%M:%S")
                hours_since_access = (current_time - last_time).total_seconds() / 3600
                # 如果短期记忆超过24小时未访问，清理掉
                if hours_since_access > SHORT_TERM_MEMORY_DURATION:
                    cleaned_count += 1
                    continue
            except:
                pass
        entities_to_keep.append(entity)

    entities_data['entities'] = entities_to_keep

    # 清理相关的关系
    entity_ids = [e['id'] for e in entities_data['entities']]
    relations_to_keep = []
    for rel in relations_data.get('relations', []):
        if rel.get('from') in entity_ids and rel.get('to') in entity_ids:
            relations_to_keep.append(rel)

    relations_data['relations'] = relations_to_keep

    # 清理空的对话（没有关联实体的对话）
    conversations_to_keep = []
    for conv in conversations_data.get('conversations', []):
        has_valid_entity = False
        for entity_id in conv.get('entities', []):
            if entity_id in entity_ids:
                has_valid_entity = True
                break
        if has_valid_entity:
            conversations_to_keep.append(conv)

    conversations_data['conversations'] = conversations_to_keep

    save_json('entities.json', entities_data)
    save_json('relations.json', relations_data)
    save_json('conversations.json', conversations_data)

    return f"已清理 {cleaned_count} 个记忆"

def organize_memories() -> str:
    """
    记忆整理：合并相似记忆，优化记忆结构
    模拟大脑的记忆整理过程
    """
    entities_data = load_json('entities.json')
    organized_count = 0

    # 按名称分组实体，合并相似的
    entities_by_name = {}
    for entity in entities_data.get('entities', []):
        name = entity.get('name', '').lower()
        if name:
            if name not in entities_by_name:
                entities_by_name[name] = []
            entities_by_name[name].append(entity)

    # 合并相同名称的实体
    merged_entities = []
    for name, entities in entities_by_name.items():
        if len(entities) > 1:
            # 保留第一个实体，合并其他实体的属性
            main_entity = entities[0]
            for other_entity in entities[1:]:
                # 合并属性
                for key, value in other_entity.get('properties', {}).items():
                    if key not in main_entity.get('properties', {}):
                        main_entity['properties'][key] = value
                    elif isinstance(value, list):
                        # 合并列表
                        for item in value:
                            if item not in main_entity['properties'][key]:
                                main_entity['properties'][key].append(item)
                organized_count += 1
            merged_entities.append(main_entity)
        else:
            merged_entities.append(entities[0])

    entities_data['entities'] = merged_entities
    save_json('entities.json', entities_data)

    return f"已整理 {organized_count} 个记忆"

def analyze_memories() -> str:
    """
    记忆分析：生成记忆统计和分析报告
    """
    entities_data = load_json('entities.json')
    relations_data = load_json('relations.json')
    conversations_data = load_json('conversations.json')

    # 统计信息
    total_entities = len(entities_data.get('entities', []))
    total_relations = len(relations_data.get('relations', []))
    total_conversations = len(conversations_data.get('conversations', []))

    # 记忆类型统计
    memory_types = {'short_term': 0, 'long_term': 0}
    for entity in entities_data.get('entities', []):
        memory_type = entity.get('properties', {}).get('memory_type', 'short_term')
        if memory_type in memory_types:
            memory_types[memory_type] += 1

    # 实体类型统计
    entity_types = {}
    for entity in entities_data.get('entities', []):
        entity_type = entity.get('type', 'unknown')
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

    # 情绪统计
    emotions = {}
    for entity in entities_data.get('entities', []):
        emotional_states = entity.get('properties', {}).get('emotional_states', [])
        for emotion in emotional_states:
            emotions[emotion] = emotions.get(emotion, 0) + 1

    # 关系类型统计
    relation_types = {}
    for rel in relations_data.get('relations', []):
        relation_type = rel.get('relation', '关联')
        relation_types[relation_type] = relation_types.get(relation_type, 0) + 1

    # 生成报告
    report = "=== 记忆分析报告 ===\n"
    report += f"总实体数: {total_entities}\n"
    report += f"总关系数: {total_relations}\n"
    report += f"总对话数: {total_conversations}\n"
    report += f"短期记忆: {memory_types['short_term']}\n"
    report += f"长期记忆: {memory_types['long_term']}\n"
    report += "\n实体类型分布:\n"
    for entity_type, count in entity_types.items():
        report += f"- {entity_type}: {count}\n"
    if emotions:
        report += "\n情绪分布:\n"
        for emotion, count in emotions.items():
            report += f"- {emotion}: {count}\n"
    if relation_types:
        report += "\n关系类型分布:\n"
        for relation_type, count in relation_types.items():
            report += f"- {relation_type}: {count}\n"

    # 保存分析报告
    analysis_path = os.path.join(MEMORY_DIR, 'analysis_report.txt')
    with open(analysis_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return f"已生成记忆分析报告，保存至: {analysis_path}"

def export_graph() -> str:
    """
    导出记忆图谱为可视化格式（JSON格式，可用于D3.js等工具）
    """
    entities_data = load_json('entities.json')
    relations_data = load_json('relations.json')

    # 构建节点和边
    nodes = []
    edges = []

    # 添加节点
    for entity in entities_data.get('entities', []):
        node = {
            'id': entity.get('id', ''),
            'label': entity.get('name', ''),
            'type': entity.get('type', 'unknown'),
            'memory_type': entity.get('properties', {}).get('memory_type', 'short_term'),
            'strength': entity.get('properties', {}).get('strength', 0.5),
            'access_count': entity.get('properties', {}).get('access_count', 0)
        }
        nodes.append(node)

    # 添加边
    for rel in relations_data.get('relations', []):
        edge = {
            'source': rel.get('from', ''),
            'target': rel.get('to', ''),
            'label': rel.get('relation', ''),
            'weight': rel.get('weight', 0.5)
        }
        edges.append(edge)

    # 构建图谱数据
    graph_data = {
        'nodes': nodes,
        'edges': edges,
        'metadata': {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'exported_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }

    # 保存图谱数据
    graph_path = os.path.join(MEMORY_DIR, 'graph_export.json')
    with open(graph_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    return f"已导出记忆图谱，保存至: {graph_path}"

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python memory_ops.py retrieve <query>")
        print("       python memory_ops.py save <summary> <entities_json> <relations_json> [--emotion <emotional_state>] [--context <context>]")
        print("       python memory_ops.py delete [--entity <entity_name>] [--conversation <conversation_id>]")
        print("       python memory_ops.py consolidate")
        print("       python memory_ops.py strengthen <entity_name>")
        print("       python memory_ops.py cleanup")
        print("       python memory_ops.py organize")
        print("       python memory_ops.py analyze")
        print("       python memory_ops.py export")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'retrieve' and len(sys.argv) >= 3:
        query = sys.argv[2]
        print(retrieve_memory(query))
    elif cmd == 'save' and len(sys.argv) >= 5:
        summary = sys.argv[2]
        entities = json.loads(sys.argv[3])
        relations = json.loads(sys.argv[4])
        emotional_state = None
        context = None
        for i, arg in enumerate(sys.argv[5:], 5):
            if arg == '--emotion' and i + 1 < len(sys.argv):
                emotional_state = sys.argv[i + 1]
            elif arg == '--context' and i + 1 < len(sys.argv):
                context = sys.argv[i + 1]
        print(save_memory(summary, entities, relations, emotional_state, context))
    elif cmd == 'delete':
        entity_name = None
        conversation_id = None
        for i, arg in enumerate(sys.argv[2:], 2):
            if arg == '--entity' and i + 1 < len(sys.argv):
                entity_name = sys.argv[i + 1]
            elif arg == '--conversation' and i + 1 < len(sys.argv):
                conversation_id = sys.argv[i + 1]
        print(delete_memory(entity_name, conversation_id))
    elif cmd == 'consolidate':
        print(consolidate_memories())
    elif cmd == 'strengthen' and len(sys.argv) >= 3:
        entity_name = sys.argv[2]
        print(strengthen_memory(entity_name))
    elif cmd == 'cleanup':
        print(cleanup_memories())
    elif cmd == 'organize':
        print(organize_memories())
    elif cmd == 'analyze':
        print(analyze_memories())
    elif cmd == 'export':
        print(export_graph())
    else:
        print("Invalid arguments")
