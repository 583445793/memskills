---
name: "memory-graph"
description: "基于图谱的记忆系统。对话开始前检索相关记忆，对话结束后提取并保存关键信息。当用户开启新对话或需要延续上下文时调用。"
---

# 记忆图谱系统 (Memory Graph)

## 功能概述

这是一个基于图谱的记忆系统，在每次对话开始前检索相关记忆，对话结束后保存关键信息。

## 记忆存储结构

记忆存储在 `.trae/skills/memory-graph/.memory/` 目录下：

```
.memory/
├── entities.json      # 实体库（用户、项目、技术、偏好等）
├── relations.json    # 关系图谱（实体间的关联）
└── conversations.json # 对话历史摘要
```

## 触发时机

### 1. 对话前检索 (Before Conversation)

当开始新对话或模型被唤醒时，**必须首先执行记忆检索**：

```
用户: "帮我看看之前那个项目的问题"

→ 检索步骤:
1. 解析当前query关键词：项目、问题
2. 遍历entities.json查找相关实体
3. 遍历conversations.json查找相关对话
4. 构建上下文prompt片段
```

### 2. 对话后保存 (After Conversation)

对话结束后（或用户表示满意时），**必须执行记忆提取**：

```
对话结束 → 提取:
1. 关键实体（用户提到的项目、工具、概念）
2. 关系（user_a 使用了 tool_b 完成 task_c）
3. 对话摘要（这次讨论了什么、达成了什么结论）
```

## 核心操作

### 检索记忆 (retrieve)

```python
def retrieve_memory(query, max_results=5):
    """
    基于query检索相关记忆

    步骤:
    1. 分词提取关键词
    2. 在entities中查找匹配的实体
    3. 通过实体关系扩展（查找关联实体）
    4. 在conversations中查找相关对话
    5. 合并排序返回top结果
    """
```

**返回格式**:
```
=== 相关记忆 ===
[实体] user:张三 - 身份:开发者 - 最近活动:2026-04-15
[实体] project:电商重构 - 状态:进行中 - 技术栈:React,Node.js
[对话] 2026-04-16 - 讨论了支付模块优化问题，结论:采用消息队列方案
[关系] 张三 负责 电商重构项目
```

### 保存记忆 (save)

```python
def save_memory(conversation_summary, extracted_entities, extracted_relations):
    """
    保存对话产生的记忆

    extracted_entities格式:
    [{"type": "user", "name": "张三", "properties": {...}}, ...]

    extracted_relations格式:
    [{"from": "张三", "relation": "负责", "to": "电商重构", "weight": 0.9}, ...]
    """
```

### 删除记忆 (delete)

```python
def delete_memory(entity_name=None, conversation_id=None):
    """
    删除记忆（实体或对话）

    参数:
    - entity_name: 要删除的实体名称
    - conversation_id: 要删除的对话ID
    """
```

### 提取关键信息 (extract)

从当前对话中提取：

1. **实体识别**: 用户、项目、技术栈、工具、概念
2. **关系抽取**: A 使用 B、 A 属于 B、 A 导致 B
3. **摘要生成**: 一句话总结这次对话
4. **情绪识别**: 对话中的情绪状态
5. **情境提取**: 对话发生的上下文情境

### 记忆巩固 (consolidate)

```python
def consolidate_memories():
    """
    记忆巩固：将重要的短期记忆转换为长期记忆
    模拟大脑的记忆巩固过程
    """
```

### 记忆强化 (strengthen)

```python
def strengthen_memory(entity_name):
    """
    强化记忆：增加记忆的权重和访问计数
    模拟大脑的记忆强化过程
    """
```

### 记忆清理 (cleanup)

```python
def cleanup_memories():
    """
    记忆清理：清理长期未使用的短期记忆
    模拟大脑的记忆清理过程
    """
```

### 记忆整理 (organize)

```python
def organize_memories():
    """
    记忆整理：合并相似记忆，优化记忆结构
    模拟大脑的记忆整理过程
    """
```

### 记忆分析 (analyze)

```python
def analyze_memories():
    """
    记忆分析：生成记忆统计和分析报告
    包含：
    - 记忆数量统计
    - 记忆类型分布
    - 实体类型分布
    - 情绪分布
    - 关系类型分布
    """
```

### 记忆导出 (export)

```python
def export_graph():
    """
    导出记忆图谱为可视化格式
    生成JSON格式的图谱数据，可用于D3.js等可视化工具
    """
```

## 图谱结构示例

```json
// entities.json
{
  "entities": [
    {
      "id": "e1",
      "type": "user",
      "name": "张三",
      "properties": {
        "role": "前端开发者",
        "preferences": ["React", "TypeScript"],
        "first_seen": "2026-04-01"
      }
    },
    {
      "id": "e2",
      "type": "project",
      "name": "电商重构",
      "properties": {
        "status": "进行中",
        "tech_stack": ["React", "Node.js", "PostgreSQL"],
        "start_date": "2026-03-15"
      }
    }
  ]
}

// relations.json
{
  "relations": [
    {
      "from": "e1",
      "to": "e2",
      "relation": "负责",
      "weight": 0.9,
      "created": "2026-04-10"
    },
    {
      "from": "e2",
      "to": "React",
      "relation": "使用技术",
      "weight": 0.95,
      "created": "2026-03-15"
    }
  ]
}

// conversations.json
{
  "conversations": [
    {
      "id": "c1",
      "date": "2026-04-16",
      "summary": "讨论支付模块优化，采用消息队列方案",
      "entities": ["e2"],
      "entities_text": ["电商重构", "支付模块"],
      "conclusion": "使用RabbitMQ解耦支付流程"
    }
  ]
}
```

## 使用流程

### 对话前
1. 解析用户输入，提取关键词
2. 调用 `retrieve_memory(query)` 获取相关记忆
3. 将返回的记忆插入上下文开头

### 对话后
1. 等待用户表示对话结束（"谢谢"、"好的"等）
2. 调用 `extract_memory(dialog_content)` 提取关键信息
3. 调用 `save_memory()` 保存到图谱

## 优先级规则

- 最近对话优先（时间衰减）
- 高频关联优先（关系权重）
- 明确实体优先（完全匹配 > 部分匹配）

## 注意事项

- 每次对话结束必须保存记忆
- 实体ID全局唯一，重复实体更新而非创建
- 关系权重影响检索排序
- 对话摘要不超过100字
