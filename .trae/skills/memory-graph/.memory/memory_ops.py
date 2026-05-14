import json
import os
import configparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

try:
    from neo4j import GraphDatabase, exceptions
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

MEMORY_DIR = os.path.join(os.path.dirname(__file__), '.memory')
CONFIG_PATH = os.path.join(MEMORY_DIR, 'neo4j_config.ini')

SHORT_TERM_MEMORY_DURATION = 24  # 短期记忆持续时间（小时）
LONG_TERM_MEMORY_THRESHOLD = 0.8  # 转为长期记忆的权重阈值

def load_neo4j_config() -> Dict:
    """加载Neo4j配置"""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return {
        'host': config.get('neo4j', 'host', fallback='localhost'),
        'port': config.getint('neo4j', 'port', fallback=7687),
        'username': config.get('neo4j', 'username', fallback='neo4j'),
        'password': config.get('neo4j', 'password', fallback='password'),
        'database': config.get('neo4j', 'database', fallback='neo4j')
    }

class Neo4jMemoryGraph:
    """基于Neo4j的记忆图谱管理器"""
    
    def __init__(self):
        self.config = load_neo4j_config()
        self.driver = None
        self._connect()
    
    def _connect(self):
        """建立Neo4j连接"""
        if not NEO4J_AVAILABLE:
            return
        try:
            uri = f"bolt://{self.config['host']}:{self.config['port']}"
            self.driver = GraphDatabase.driver(
                uri,
                auth=(self.config['username'], self.config['password']),
                database=self.config['database']
            )
            # 验证连接
            with self.driver.session() as session:
                session.run("RETURN 1")
        except Exception as e:
            print(f"Neo4j连接失败: {e}")
            self.driver = None
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
    
    def _calculate_forgetting_curve(self, last_accessed: str, memory_type: str = 'short_term') -> float:
        """计算记忆遗忘曲线"""
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
            forgetting_rate = 0.05
        else:
            forgetting_rate = 0.15
        
        retention = max(0.1, min(1.0, pow(2.71828, -hours_since_access * forgetting_rate)))
        return retention
    
    def create_entity(self, name: str, entity_type: str = 'concept', properties: Dict = None) -> str:
        """创建实体节点"""
        if not self.driver:
            return "Neo4j不可用"
        
        properties = properties or {}
        properties['name'] = name
        properties['type'] = entity_type
        properties['first_seen'] = datetime.now().strftime("%Y-%m-%d")
        properties['last_seen'] = datetime.now().strftime("%Y-%m-%d")
        properties['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        properties['memory_type'] = 'short_term'
        properties['access_count'] = 1
        
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (e:Entity {name: $name, type: $type, first_seen: $first_seen, 
                                last_seen: $last_seen, last_accessed: $last_accessed,
                                memory_type: $memory_type, access_count: $access_count})
                RETURN e.name AS name, ID(e) AS id
                """,
                **properties
            )
            record = result.single()
            return record['name'] if record else None
    
    def get_entity(self, name: str) -> Optional[Dict]:
        """获取实体信息"""
        if not self.driver:
            return None
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {name: $name})
                RETURN e
                """,
                name=name
            )
            record = result.single()
            if record:
                return record['e']._properties
            return None
    
    def update_entity(self, name: str, properties: Dict) -> str:
        """更新实体属性"""
        if not self.driver:
            return "Neo4j不可用"
        
        properties['last_accessed'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {name: $name})
                SET e += $properties
                RETURN e.name AS name
                """,
                name=name,
                properties=properties
            )
            record = result.single()
            return record['name'] if record else None
    
    def create_relation(self, from_name: str, relation_type: str, to_name: str, weight: float = 0.7) -> bool:
        """创建实体之间的关系"""
        if not self.driver:
            return False
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Entity {name: $from_name}), (b:Entity {name: $to_name})
                MERGE (a)-[r:RELATION {type: $relation_type}]->(b)
                ON CREATE SET r.weight = $weight, r.created = $created
                ON MATCH SET r.weight = max(r.weight, $weight)
                RETURN r
                """,
                from_name=from_name,
                to_name=to_name,
                relation_type=relation_type,
                weight=weight,
                created=datetime.now().strftime("%Y-%m-%d")
            )
            return result.single() is not None
    
    def retrieve_memory(self, query: str, max_results: int = 5) -> str:
        """检索相关记忆"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        keywords = [w.strip().lower() for w in query.replace('?', ' ').split() if len(w.strip()) > 1]
        results = []
        
        with self.driver.session() as session:
            for keyword in keywords:
                # 搜索实体
                entity_results = session.run(
                    """
                    MATCH (e:Entity)
                    WHERE toLower(e.name) CONTAINS $keyword OR 
                          toLower(e.type) CONTAINS $keyword
                    RETURN e
                    ORDER BY e.access_count DESC
                    LIMIT 10
                    """,
                    keyword=keyword
                )
                
                for record in entity_results:
                    entity = record['e']._properties
                    retention = self._calculate_forgetting_curve(
                        entity.get('last_accessed', ''),
                        entity.get('memory_type', 'short_term')
                    )
                    score = (entity.get('access_count', 1) * 10) * retention
                    
                    entity_type = entity.get('type', 'unknown')
                    name = entity.get('name', '')
                    props = {k: v for k, v in entity.items() if k not in ['name', 'type']}
                    props_str = ', '.join([f"{k}:{v}" for k, v in list(props.items())[:3]])
                    
                    results.append({
                        'type': 'entity',
                        'score': score,
                        'text': f"[{entity_type}] {name} - {props_str}" if props_str else f"[{entity_type}] {name}"
                    })
                
                # 搜索关系
                relation_results = session.run(
                    """
                    MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                    WHERE toLower(a.name) CONTAINS $keyword OR 
                          toLower(b.name) CONTAINS $keyword OR
                          toLower(r.type) CONTAINS $keyword
                    RETURN a, r, b
                    ORDER BY r.weight DESC
                    LIMIT 10
                    """,
                    keyword=keyword
                )
                
                for record in relation_results:
                    a = record['a']._properties
                    r = record['r']._properties
                    b = record['b']._properties
                    
                    retention = self._calculate_forgetting_curve(r.get('created', ''))
                    score = (r.get('weight', 0.5) * 5) * retention
                    
                    results.append({
                        'type': 'relation',
                        'score': score,
                        'text': f"[关系] {a.get('name')} {r.get('type', '关联')} {b.get('name')}"
                    })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        top_results = results[:max_results]
        
        if not top_results:
            return "暂无相关记忆"
        
        output = "=== 相关记忆 ===\n"
        for r in top_results:
            output += f"{r['text']}\n"
        
        return output
    
    def save_memory(self, conversation_summary: str, extracted_entities: List[Dict], 
                    extracted_relations: List[Dict], emotional_state: str = None, 
                    context: str = None) -> str:
        """保存对话产生的记忆"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        created_entities = 0
        created_relations = 0
        
        with self.driver.session() as session:
            # 创建或更新实体
            for ent in extracted_entities:
                name = ent.get('name', '')
                entity_type = ent.get('type', 'concept')
                props = ent.get('properties', {})
                
                result = session.run(
                    """
                    MERGE (e:Entity {name: $name})
                    ON CREATE SET e.type = $entity_type, 
                                  e.first_seen = $now_date,
                                  e.last_seen = $now_date,
                                  e.last_accessed = $now_datetime,
                                  e.memory_type = 'short_term',
                                  e.access_count = 1
                    ON MATCH SET e.last_seen = $now_date,
                                 e.last_accessed = $now_datetime,
                                 e.access_count = e.access_count + 1
                    RETURN e.access_count AS access_count, e.memory_type AS memory_type
                    """,
                    name=name,
                    entity_type=entity_type,
                    now_date=datetime.now().strftime("%Y-%m-%d"),
                    now_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                record = result.single()
                if record:
                    access_count = record['access_count']
                    memory_type = record['memory_type']
                    
                    # 检查是否需要转为长期记忆
                    if memory_type == 'short_term' and access_count >= 3:
                        session.run(
                            """
                            MATCH (e:Entity {name: $name})
                            SET e.memory_type = 'long_term',
                                e.consolidated_at = $now_datetime
                            """,
                            name=name,
                            now_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                
                created_entities += 1
            
            # 创建关系
            for rel in extracted_relations:
                from_name = rel.get('from', '')
                to_name = rel.get('to', '')
                relation_type = rel.get('relation', '关联')
                weight = rel.get('weight', 0.7)
                
                # 确保目标实体存在
                session.run(
                    """
                    MERGE (e:Entity {name: $name})
                    ON CREATE SET e.type = 'unknown',
                                  e.first_seen = $now_date,
                                  e.last_seen = $now_date,
                                  e.last_accessed = $now_datetime,
                                  e.memory_type = 'short_term',
                                  e.access_count = 1
                    """,
                    name=to_name,
                    now_date=datetime.now().strftime("%Y-%m-%d"),
                    now_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                session.run(
                    """
                    MATCH (a:Entity {name: $from_name}), (b:Entity {name: $to_name})
                    MERGE (a)-[r:RELATION {type: $relation_type}]->(b)
                    ON CREATE SET r.weight = $weight, r.created = $now_date
                    ON MATCH SET r.weight = max(r.weight, $weight)
                    """,
                    from_name=from_name,
                    to_name=to_name,
                    relation_type=relation_type,
                    weight=weight,
                    now_date=datetime.now().strftime("%Y-%m-%d")
                )
                
                created_relations += 1
            
            # 创建对话节点
            session.run(
                """
                CREATE (c:Conversation {
                    id: $conv_id,
                    date: $now_date,
                    summary: $summary,
                    emotional_state: $emotional_state,
                    context: $context
                })
                """,
                conv_id=f"c{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                now_date=datetime.now().strftime("%Y-%m-%d"),
                summary=conversation_summary[:100],
                emotional_state=emotional_state,
                context=context
            )
        
        return f"已保存 {created_entities} 个实体, {created_relations} 条关系"
    
    def delete_memory(self, entity_name: str = None, conversation_id: str = None) -> str:
        """删除记忆"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        deleted_count = 0
        
        with self.driver.session() as session:
            if entity_name:
                result = session.run(
                    """
                    MATCH (e:Entity {name: $name})
                    DETACH DELETE e
                    RETURN COUNT(*) AS count
                    """,
                    name=entity_name
                )
                record = result.single()
                deleted_count += record['count'] if record else 0
            
            if conversation_id:
                result = session.run(
                    """
                    MATCH (c:Conversation {id: $conv_id})
                    DETACH DELETE c
                    RETURN COUNT(*) AS count
                    """,
                    conv_id=conversation_id
                )
                record = result.single()
                deleted_count += record['count'] if record else 0
        
        return f"已删除 {deleted_count} 个记忆项目"
    
    def consolidate_memories(self) -> str:
        """记忆巩固"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.memory_type = 'short_term' AND e.access_count >= 3
                SET e.memory_type = 'long_term',
                    e.consolidated_at = $now_datetime
                RETURN COUNT(*) AS count
                """,
                now_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            record = result.single()
            count = record['count'] if record else 0
        
        return f"已巩固 {count} 个记忆"
    
    def strengthen_memory(self, entity_name: str) -> str:
        """强化记忆"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {name: $name})
                SET e.access_count = e.access_count + 1,
                    e.strength = CASE WHEN e.strength IS NULL THEN 0.6 ELSE min(1.0, e.strength + 0.1) END,
                    e.last_accessed = $now_datetime
                WITH e
                WHERE e.memory_type = 'short_term' AND e.access_count >= 3
                SET e.memory_type = 'long_term',
                    e.consolidated_at = $now_datetime
                RETURN e.name AS name
                """,
                name=entity_name,
                now_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            record = result.single()
            if record:
                return f"已强化记忆: {record['name']}"
            return "未找到该记忆"
    
    def cleanup_memories(self) -> str:
        """清理长期未使用的短期记忆"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        cutoff_time = (datetime.now() - timedelta(hours=SHORT_TERM_MEMORY_DURATION)).strftime("%Y-%m-%d %H:%M:%S")
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.memory_type = 'short_term' AND e.last_accessed < $cutoff_time
                DETACH DELETE e
                RETURN COUNT(*) AS count
                """,
                cutoff_time=cutoff_time
            )
            record = result.single()
            count = record['count'] if record else 0
        
        return f"已清理 {count} 个记忆"
    
    def organize_memories(self) -> str:
        """整理记忆，合并相似实体"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WITH toLower(e.name) AS name_lower, COLLECT(e) AS entities
                WHERE SIZE(entities) > 1
                WITH entities[0] AS main, TAIL(entities) AS others
                UNWIND others AS other
                MATCH (other)-[r]->()
                MERGE (main)-[nr:RELATION {type: r.type}]->((r)->())
                ON CREATE SET nr.weight = r.weight, nr.created = r.created
                ON MATCH SET nr.weight = max(nr.weight, r.weight)
                DETACH DELETE other
                RETURN COUNT(DISTINCT others) AS count
                """
            )
            record = result.single()
            count = record['count'] if record else 0
        
        return f"已整理 {count} 个记忆"
    
    def analyze_memories(self) -> str:
        """生成记忆分析报告"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        with self.driver.session() as session:
            # 统计实体数
            entity_count = session.run("MATCH (e:Entity) RETURN COUNT(*) AS count").single()['count']
            
            # 统计关系数
            relation_count = session.run("MATCH ()-[r:RELATION]->() RETURN COUNT(*) AS count").single()['count']
            
            # 统计对话数
            conv_count = session.run("MATCH (c:Conversation) RETURN COUNT(*) AS count").single()['count']
            
            # 记忆类型分布
            memory_types = session.run(
                """
                MATCH (e:Entity)
                RETURN e.memory_type AS type, COUNT(*) AS count
                """
            ).data()
            
            # 实体类型分布
            entity_types = session.run(
                """
                MATCH (e:Entity)
                RETURN e.type AS type, COUNT(*) AS count
                """
            ).data()
            
            # 关系类型分布
            relation_types = session.run(
                """
                MATCH ()-[r:RELATION]->()
                RETURN r.type AS type, COUNT(*) AS count
                """
            ).data()
        
        report = "=== 记忆分析报告 ===\n"
        report += f"总实体数: {entity_count}\n"
        report += f"总关系数: {relation_count}\n"
        report += f"总对话数: {conv_count}\n"
        
        report += "\n记忆类型分布:\n"
        for item in memory_types:
            report += f"- {item['type']}: {item['count']}\n"
        
        report += "\n实体类型分布:\n"
        for item in entity_types:
            report += f"- {item['type']}: {item['count']}\n"
        
        report += "\n关系类型分布:\n"
        for item in relation_types:
            report += f"- {item['type']}: {item['count']}\n"
        
        analysis_path = os.path.join(MEMORY_DIR, 'analysis_report.txt')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return f"已生成记忆分析报告，保存至: {analysis_path}"
    
    def export_graph(self) -> str:
        """导出记忆图谱"""
        if not self.driver:
            return "Neo4j不可用，请检查连接"
        
        nodes = []
        edges = []
        
        with self.driver.session() as session:
            # 获取节点
            entity_results = session.run("MATCH (e:Entity) RETURN e").data()
            for record in entity_results:
                entity = record['e']._properties
                nodes.append({
                    'id': entity.get('name', ''),
                    'label': entity.get('name', ''),
                    'type': entity.get('type', 'unknown'),
                    'memory_type': entity.get('memory_type', 'short_term'),
                    'strength': entity.get('strength', 0.5),
                    'access_count': entity.get('access_count', 0)
                })
            
            # 获取边
            relation_results = session.run("MATCH (a)-[r:RELATION]->(b) RETURN a, r, b").data()
            for record in relation_results:
                edges.append({
                    'source': record['a']._properties.get('name', ''),
                    'target': record['b']._properties.get('name', ''),
                    'label': record['r']._properties.get('type', ''),
                    'weight': record['r']._properties.get('weight', 0.5)
                })
        
        graph_data = {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'exported_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        graph_path = os.path.join(MEMORY_DIR, 'graph_export.json')
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        return f"已导出记忆图谱，保存至: {graph_path}"

# 全局实例
_memory_graph = None

def get_memory_graph() -> Neo4jMemoryGraph:
    """获取记忆图谱实例"""
    global _memory_graph
    if _memory_graph is None:
        _memory_graph = Neo4jMemoryGraph()
    return _memory_graph

def retrieve_memory(query: str, max_results: int = 5) -> str:
    """检索记忆"""
    return get_memory_graph().retrieve_memory(query, max_results)

def save_memory(conversation_summary: str, extracted_entities: List[Dict], 
                extracted_relations: List[Dict], emotional_state: str = None, 
                context: str = None) -> str:
    """保存记忆"""
    return get_memory_graph().save_memory(conversation_summary, extracted_entities, 
                                          extracted_relations, emotional_state, context)

def delete_memory(entity_name: str = None, conversation_id: str = None) -> str:
    """删除记忆"""
    return get_memory_graph().delete_memory(entity_name, conversation_id)

def consolidate_memories() -> str:
    """记忆巩固"""
    return get_memory_graph().consolidate_memories()

def strengthen_memory(entity_name: str) -> str:
    """强化记忆"""
    return get_memory_graph().strengthen_memory(entity_name)

def cleanup_memories() -> str:
    """清理记忆"""
    return get_memory_graph().cleanup_memories()

def organize_memories() -> str:
    """整理记忆"""
    return get_memory_graph().organize_memories()

def analyze_memories() -> str:
    """分析记忆"""
    return get_memory_graph().analyze_memories()

def export_graph() -> str:
    """导出图谱"""
    return get_memory_graph().export_graph()

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