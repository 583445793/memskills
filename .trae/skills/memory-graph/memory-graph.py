import sys
import os
import json

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

sys.path.append(os.path.join(current_dir, '.memory'))

from memory_ops import (
    retrieve_memory,
    save_memory,
    delete_memory,
    strengthen_memory,
    consolidate_memories,
    cleanup_memories,
    organize_memories,
    analyze_memories,
    export_graph
)

def execute(command, args=None):
    args = args or {}
    
    if command == 'retrieve':
        query = args.get('query', '')
        if not query:
            return {"status": "error", "message": "请提供查询关键词"}
        result = retrieve_memory(query)
        return {"status": "success", "data": result}
    
    elif command == 'save':
        summary = args.get('summary', '')
        entities = args.get('entities', '[]')
        relations = args.get('relations', '[]')
        emotion = args.get('emotion', None)
        context = args.get('context', None)
        
        if not summary:
            return {"status": "error", "message": "请提供对话摘要"}
        
        try:
            if isinstance(entities, str):
                entities = json.loads(entities)
            if isinstance(relations, str):
                relations = json.loads(relations)
        except json.JSONDecodeError:
            return {"status": "error", "message": "实体或关系格式错误"}
        
        result = save_memory(summary, entities, relations, emotional_state=emotion, context=context)
        return {"status": "success", "data": result}
    
    elif command == 'delete':
        entity_name = args.get('entity_name')
        conversation_id = args.get('conversation_id')
        
        if not entity_name and not conversation_id:
            return {"status": "error", "message": "请指定要删除的实体名称或对话ID"}
        
        result = delete_memory(entity_name=entity_name, conversation_id=conversation_id)
        return {"status": "success", "data": result}
    
    elif command == 'strengthen':
        entity_name = args.get('entity_name', '')
        if not entity_name:
            return {"status": "error", "message": "请提供实体名称"}
        result = strengthen_memory(entity_name)
        return {"status": "success", "data": result}
    
    elif command == 'consolidate':
        result = consolidate_memories()
        return {"status": "success", "data": result}
    
    elif command == 'cleanup':
        result = cleanup_memories()
        return {"status": "success", "data": result}
    
    elif command == 'organize':
        result = organize_memories()
        return {"status": "success", "data": result}
    
    elif command == 'analyze':
        result = analyze_memories()
        return {"status": "success", "data": result}
    
    elif command == 'export':
        result = export_graph()
        return {"status": "success", "data": result}
    
    else:
        return {"status": "error", "message": f"未知命令: {command}"}

def run(params=None):
    params = params or {}
    command = params.get('command', '')
    
    if not command:
        query = params.get('query', params.get('input', params.get('content', '')))
        if query:
            return execute('retrieve', {'query': query})
        else:
            return {"status": "error", "message": "请提供命令或查询内容"}
    
    return execute(command, params)

def main():
    if len(sys.argv) < 2:
        print("Usage: python memory-graph.py <command> [args...]")
        print("Commands:")
        print("  retrieve <query>           - 检索记忆")
        print("  save <summary> <entities> <relations> [--emotion <emotion>] [--context <context>]")
        print("  delete --entity <name>     - 删除实体")
        print("  delete --conversation <id> - 删除对话")
        print("  strengthen <entity_name>   - 强化记忆")
        print("  consolidate                - 记忆巩固")
        print("  cleanup                    - 记忆清理")
        print("  organize                   - 记忆整理")
        print("  analyze                    - 记忆分析")
        print("  export                     - 图谱导出")
        return
    
    command = sys.argv[1]
    
    if command == 'retrieve':
        if len(sys.argv) < 3:
            print("请提供查询关键词")
            return
        query = sys.argv[2]
        result = retrieve_memory(query)
        print(result)
    
    elif command == 'save':
        if len(sys.argv) < 5:
            print("请提供摘要、实体、关系参数")
            return
        summary = sys.argv[2]
        entities = sys.argv[3]
        relations = sys.argv[4]
        emotion = None
        context = None
        i = 5
        while i < len(sys.argv):
            if sys.argv[i] == '--emotion':
                emotion = sys.argv[i+1]
                i += 2
            elif sys.argv[i] == '--context':
                context = sys.argv[i+1]
                i += 2
            else:
                i += 1
        result = save_memory(summary, entities, relations, emotional_state=emotion, context=context)
        print(result)
    
    elif command == 'delete':
        if len(sys.argv) < 4:
            print("请指定 --entity 或 --conversation")
            return
        if sys.argv[2] == '--entity':
            result = delete_memory(entity_name=sys.argv[3])
            print(result)
        elif sys.argv[2] == '--conversation':
            result = delete_memory(conversation_id=sys.argv[3])
            print(result)
    
    elif command == 'strengthen':
        if len(sys.argv) < 3:
            print("请提供实体名称")
            return
        result = strengthen_memory(sys.argv[2])
        print(result)
    
    elif command == 'consolidate':
        result = consolidate_memories()
        print(result)
    
    elif command == 'cleanup':
        result = cleanup_memories()
        print(result)
    
    elif command == 'organize':
        result = organize_memories()
        print(result)
    
    elif command == 'analyze':
        result = analyze_memories()
        print(result)
    
    elif command == 'export':
        result = export_graph()
        print(result)
    
    else:
        print(f"未知命令: {command}")

if __name__ == '__main__':
    main()