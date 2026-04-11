import os
import json
import requests
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import restore
import paper_enrich
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_ENDPOINT = os.getenv("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")

HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}


DEEPSEEK_SYSTEM_TREE = """你是知识树生成助手。请根据用户主题输出一个 JSON 对象（只输出 JSON，不要其他文字）。

结构规则：
- 根节点 type="concept"，name 为主题名称。
- 树的深度建议 4~6 层，每个概念节点可以继续分解为子概念（children）。
- 每个节点尽量包含 description 字段（简短说明）。
- 叶子节点可以是 type="paper" 或 type="concept"。
- 同一父节点下 children 可以混合 concept 和 paper。
- paper 节点必须包含：name, type="paper", quote, url(不知道留空), authors, year, children=[]。

**关于 importance 字段：**
- 每个节点必须包含 importance 字段，值为正整数。
- **对于同一父节点下的所有子节点，importance 表示建议的学习顺序或重要性排序，数值越小越优先学习。**
- 兄弟节点之间的 importance 值必须互不相同，从 1 开始连续递增（如 1, 2, 3...）。
- 排序时请遵循：基础概念优先（作为前置知识的排在前面）→ 核心理论次之 → 应用与论文最后。
- 如果节点是 paper 类型，通常 importance 值较大（排在概念之后）。
- 示例：若某父节点有 3 个子节点，则它们的 importance 应分别为 1, 2, 3，不可重复，不可都为 1。

示例（主题“注意力机制”，注意 importance 的赋值）：
{
  "name": "注意力机制",
  "type": "concept",
  "description": "深度学习中的一种动态加权机制",
  "importance": 1,
  "children": [
    {
      "name": "注意力函数",
      "type": "concept",
      "description": "计算查询与键的相似度",
      "importance": 1,
      "children": [
        { "name": "加性注意力", "type": "concept", "description": "使用前馈网络计算", "importance": 1 },
        { "name": "点积注意力", "type": "concept", "description": "点积后缩放", "importance": 2 }
      ]
    },
    {
      "name": "多头注意力",
      "type": "concept",
      "description": "并行多个注意力头",
      "importance": 2,
      "children": [
        { "name": "自注意力", "type": "concept", "description": "序列内部关联", "importance": 1 }
      ]
    },
    {
      "name": "Transformer 论文",
      "type": "paper",
      "authors": "Vaswani et al.",
      "year": 2017,
      "quote": "Attention Is All You Need",
      "url": "https://arxiv.org/abs/1706.03762",
      "importance": 3,
      "children": []
    }
  ]
}
"""
def clean_identical_importance(node):
    children = node.get('children', [])
    if children:
        imps = [c.get('importance') for c in children if 'importance' in c]
        if len(imps) == len(children) and len(set(imps)) == 1:
            for c in children:
                c.pop('importance', None)
        for c in children:
            clean_identical_importance(c)

def generate_fallback_tree(keyword):

    return {
        "name": keyword,
        "type": "concept",
        "description": f"关于「{keyword}」的知识脉络",
        "children": [
            {
                "name": f"{keyword} 基础概念",
                "type": "concept",
                "description": "核心基础",
                "children": [
                    { "name": "定义与原理", "type": "concept", "description": "基本定义" },
                    { "name": "历史发展", "type": "concept", "description": "重要发展节点" }
                ]
            },
            {
                "name": f"{keyword} 核心理论",
                "type": "concept",
                "description": "深入理解",
                "children": [
                    {
                        "name": "关键方法",
                        "type": "concept",
                        "description": "主要方法论",
                        "children": [
                            { "name": "方法 A", "type": "concept", "description": "方法A详解" },
                            { "name": "方法 B", "type": "concept", "description": "方法B详解" }
                        ]
                    }
                ]
            },
            {
                "name": f"{keyword} 应用实践",
                "type": "concept",
                "description": "实际应用",
                "children": [
                    { "name": "案例1", "type": "concept", "description": "应用案例" },
                    { "name": "前沿论文", "type": "paper", "authors": "待补充", "year": "2024", "quote": "相关研究", "url": "" }
                ]
            }
        ]
    }

def call_deepseek(prompt):
    if not DEEPSEEK_API_KEY or not str(DEEPSEEK_API_KEY).strip():
        print("DEEPSEEK_API_KEY 未配置")
        return None, "未配置 DEEPSEEK_API_KEY"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": DEEPSEEK_SYSTEM_TREE},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
        "max_tokens": 4096,  # 降低 token 防止截断
        "response_format": {"type": "json_object"},
    }
    try:
        print(f"正在请求 DeepSeek API，主题: {prompt[:50]}...")
        response = requests.post(DEEPSEEK_ENDPOINT, headers=HEADERS, json=payload, timeout=90)
        if not response.ok:
            print(f"HTTP {response.status_code}: {response.text[:200]}")
            return None, f"API 返回 {response.status_code}"
        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            return None, "响应无 choices"
        content = choices[0].get("message", {}).get("content")
        if not content:
            return None, "模型返回空内容"
        # 解析 JSON
        content = content.strip()
        # 移除可能的 markdown 代码块标记
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        tree_data = json.loads(content)
        # 基本校验
        if not isinstance(tree_data, dict) or "name" not in tree_data:
            raise ValueError("根节点缺少 name 字段")
        print(f"成功生成知识树: {tree_data.get('name')}")
        return tree_data, None
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}\n原始内容前300字符: {content[:300]}")
        return None, f"JSON 格式错误: {e}"
    except Exception as e:
        print(f"API 调用异常: {traceback.format_exc()}")
        return None, f"请求异常: {e}"

@app.route('/generate', methods=['POST'])
def generate_knowledge_tree():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    prompt = f"""请为主题「{keyword}」生成一棵多层级知识树（深度4-6层），展现完整学习脉络。每个概念节点尽量提供 description。输出严格的 JSON 对象。"""
    
    tree_data, err = call_deepseek(prompt)
    if tree_data is None:
        print(f" API 生成失败，使用回退树。错误: {err}")
        tree_data = generate_fallback_tree(keyword)
    else:
        # 确保有 children 字段
        if 'children' not in tree_data:
            tree_data['children'] = []
        # 补全描述（如果缺失）
        def fill_desc(node):
            if 'description' not in node and node.get('type') != 'paper':
                node['description'] = f"{node.get('name', '')} 相关知识"
            for child in node.get('children', []):
                fill_desc(child)
        fill_desc(tree_data)
        clean_identical_importance(tree_data)   

    # 论文链接补全（即使回退树也尝试）
    try:
        paper_enrich.enrich_tree_with_literature(tree_data)
    except Exception as e:
        print(f"论文链接补全失败: {e}")
    assign_default_importance(tree_data) 
    tree_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tree_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(tree_data)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# 保存 API：与 app.py 同目录，不依赖启动时的 cwd
_STORAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage.json')
st = restore.JSONStorage(_STORAGE_FILE)



@app.route('/api/trees', methods=['GET'])
def get_all_trees():

    try:
        all_data = st.read_all()
        
        trees_list = []
        for name, data in all_data.items():
            trees_list.append({
                'name': name,
                'title': data.get('name', name),
                'type': data.get('type', 'root'),
                'created_at': data.get('created_at'),
                'updated_at': data.get('updated_at'),
                'node_count': count_nodes(data),
                'preview': get_preview_text(data)
            })
        
        trees_list.sort(key=lambda x: x['updated_at'], reverse=True)
        
        return jsonify({
            'code': 200,
            'data': trees_list,
            'total': len(trees_list)
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取列表失败: {str(e)}'
        }), 500

@app.route('/api/tree/<tree_name>', methods=['GET'])
def get_tree_detail(tree_name):
    try:
        data = st.read(tree_name)
        
        if data:
            return jsonify({
                'code': 200,
                'data': data
            })
        else:
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
            
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取数据失败: {str(e)}'
        }), 500



@app.route('/api/tree/<tree_name>/node', methods=['POST'])
def add_node(tree_name):
    try:
        node_data = request.get_json()
        
        if not st.exists(tree_name):
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
        
        # 验证节点数据
        if not node_data or 'name' not in node_data:
            return jsonify({
                'code': 400,
                'message': '节点必须包含 name 字段'
            }), 400
        
        # 设置默认类型
        if 'type' not in node_data:
            node_data['type'] = 'concept'
        
        # 获取知识树
        tree = st.read(tree_name)
        
        # 获取父节点路径
        parent_path = node_data.get('parent_path', '')
        
        if parent_path:
            # 添加节点
            parent = find_node_by_path(tree, parent_path)
            if parent:
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(node_data)
            else:
                return jsonify({
                    'code': 404,
                    'message': f'找不到父节点路径: {parent_path}'
                }), 404
        else:
            # 添加到根节点
            if 'children' not in tree:
                tree['children'] = []
            tree['children'].append(node_data)
        

        tree['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存
        st.create(tree_name, tree)
        
        return jsonify({
            'code': 200,
            'message': f'节点 "{node_data["name"]}" 添加成功',
            'data': node_data
        })
        
    except Exception as e:
        print(f"添加节点失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'添加节点失败: {str(e)}'
        }), 500

@app.route('/api/tree/<tree_name>/node/<path:node_path>', methods=['PUT'])
def update_node(tree_name, node_path):

    try:
        update_data = request.get_json()
        
        if not st.exists(tree_name):
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
        
        tree = st.read(tree_name)
        
        # 查找节点
        node = find_node_by_path(tree, node_path)
        if not node:
            return jsonify({
                'code': 404,
                'message': f'找不到节点路径: {node_path}'
            }), 404
        
        # 更新节点数据
        node.update(update_data)
        

        tree['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存
        st.create(tree_name, tree)
        
        return jsonify({
            'code': 200,
            'message': f'节点 "{node.get("name")}" 更新成功',
            'data': node
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'更新节点失败: {str(e)}'
        }), 500

@app.route('/api/tree/<tree_name>/node/<path:node_path>', methods=['DELETE'])
def delete_node(tree_name, node_path):

    try:
        if not st.exists(tree_name):
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
        
        tree = st.read(tree_name)
        

        path_parts = node_path.split('/')
        node_name = path_parts[-1]
        parent_path = '/'.join(path_parts[:-1]) if len(path_parts) > 1 else ''
        
        deleted = False
        
        if parent_path:
            parent = find_node_by_path(tree, parent_path)
            if parent and 'children' in parent:
                for i, child in enumerate(parent['children']):
                    if child.get('name') == node_name:
                        del parent['children'][i]
                        deleted = True
                        break
        else:
            # 删除子节点
            if 'children' in tree:
                for i, child in enumerate(tree['children']):
                    if child.get('name') == node_name:
                        del tree['children'][i]
                        deleted = True
                        break
        
        if not deleted:
            return jsonify({
                'code': 404,
                'message': f'找不到节点 "{node_name}"'
            }), 404
        

        tree['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存
        st.create(tree_name, tree)
        
        return jsonify({
            'code': 200,
            'message': f'节点 "{node_name}" 删除成功'
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'删除节点失败: {str(e)}'
        }), 500

@app.route('/api/tree/<tree_name>/batch_nodes', methods=['POST'])
def batch_add_nodes(tree_name):
    try:
        nodes_data = request.get_json()
        
        if not st.exists(tree_name):
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
        
        if not nodes_data or not isinstance(nodes_data, list):
            return jsonify({
                'code': 400,
                'message': '需要提供节点列表'
            }), 400
        
        tree = st.read(tree_name)
        added_count = 0
        
        for node_data in nodes_data:
            if 'name' not in node_data:
                continue
            
            if 'type' not in node_data:
                node_data['type'] = 'concept'
            
            parent_path = node_data.get('parent_path', '')
            
            if parent_path:
                parent = find_node_by_path(tree, parent_path)
                if parent:
                    if 'children' not in parent:
                        parent['children'] = []
                    parent['children'].append(node_data)
                    added_count += 1
            else:
                if 'children' not in tree:
                    tree['children'] = []
                tree['children'].append(node_data)
                added_count += 1
        

        tree['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存
        st.create(tree_name, tree)
        
        return jsonify({
            'code': 200,
            'message': f'成功添加 {added_count} 个节点',
            'count': added_count
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'批量添加失败: {str(e)}'
        }), 500



@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({
                'code': 400,
                'message': '缺少必要参数：name'
            }), 400
        
        tree_name = data['name']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if st.exists(tree_name):
            existing_data = st.read(tree_name)
            data['created_at'] = existing_data.get('created_at', current_time)
            data['updated_at'] = current_time
            message = f'知识树 "{tree_name}" 更新成功！'
        else:
            data['created_at'] = current_time
            data['updated_at'] = current_time
            message = f'知识树 "{tree_name}" 保存成功！'
        
        if 'children' not in data:
            data['children'] = []
        
        st.create(tree_name, data)
        
        return jsonify({
            'code': 200,
            'message': message,
            'data': data
        })
        
    except Exception as e:
        print("错误:", str(e))
        return jsonify({
            'code': 500,
            'message': f'保存失败: {str(e)}'
        }), 500

@app.route('/api/tree/<tree_name>', methods=['PUT'])
def update_tree(tree_name):
    try:
        update_data = request.get_json()
        
        if not st.exists(tree_name):
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
        
        existing_data = st.read(tree_name)
        existing_data.update(update_data)
        existing_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        st.create(tree_name, existing_data)
        
        return jsonify({
            'code': 200,
            'message': f'知识树 "{tree_name}" 更新成功',
            'data': existing_data
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'更新失败: {str(e)}'
        }), 500

@app.route('/api/tree/<tree_name>', methods=['DELETE'])
def delete_tree(tree_name):
    try:
        if st.delete(tree_name):
            return jsonify({
                'code': 200,
                'message': f'知识树 "{tree_name}" 删除成功'
            })
        else:
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
            
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'删除失败: {str(e)}'
        }), 500

@app.route('/api/search', methods=['GET'])
def search_trees():
    """搜索知识树"""
    try:
        keyword = request.args.get('q', '').strip()
        
        if not keyword:
            return get_all_trees()
        
        all_data = st.read_all()
        results = []
        
        for tree_name, tree_data in all_data.items():
            if keyword.lower() in tree_name.lower() or \
               keyword.lower() in tree_data.get('name', '').lower():
                results.append({
                    'name': tree_name,
                    'title': tree_data.get('name', tree_name),
                    'type': tree_data.get('type', 'root'),
                    'created_at': tree_data.get('created_at'),
                    'updated_at': tree_data.get('updated_at'),
                    'node_count': count_nodes(tree_data),
                    'preview': get_preview_text(tree_data)
                })
        
        return jsonify({
            'code': 200,
            'data': results,
            'total': len(results)
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'搜索失败: {str(e)}'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_statistics():

    try:
        all_data = st.read_all()
        
        stats = {
            'total_trees': len(all_data),
            'total_nodes': 0,
            'total_papers': 0,
            'total_concepts': 0
        }
        
        for tree_data in all_data.values():
            node_counts = count_nodes_by_type(tree_data)
            stats['total_nodes'] += node_counts['total']
            stats['total_papers'] += node_counts['papers']
            stats['total_concepts'] += node_counts['concepts']
        
        return jsonify({
            'code': 200,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'获取统计失败: {str(e)}'
        }), 500

@app.route('/expand', methods=['POST'])
def expand_node():
    """接收父节点信息，生成其子节点并返回"""
    data = request.get_json()
    parent_name = data.get('parent_name', '').strip()
    parent_path = data.get('parent_path', '')   # 用于上下文
    tree_name = data.get('tree_name', '')       # 当前树名（可选）
    keyword = data.get('keyword', parent_name)  # 默认使用父节点名
    
    if not parent_name:
        return jsonify({'error': '缺少父节点名称'}), 400
    
    prompt = f"""请为主题「{keyword}」生成**仅其直接子节点**（深度为1，不要超过2层）。输出格式为一个 children 数组，每个子节点可以是 concept 或 paper。
要求：
- 每个子节点包含 name, type, description (可选)
- paper 节点需包含 authors, year, quote, url(可留空)
- 最多生成 5 个子节点
- 输出必须是合法的 JSON 数组，例如：
[
  {{"name":"子概念1","type":"concept","description":"说明"}},
  {{"name":"相关论文","type":"paper","authors":"..."}}
]
"""
 
    system_prompt = "你是知识树生成助手。用户会要求生成某个主题的直接子节点，请只输出一个 JSON 数组，不要输出其他文字。"
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(DEEPSEEK_ENDPOINT, headers=HEADERS, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            # 尝试解析 JSON
            import json
            obj = json.loads(content)
            if isinstance(obj, list):
                children = obj
            elif isinstance(obj, dict) and 'children' in obj:
                children = obj['children']
            else:
                children = []
            # 为每个子节点补充必要字段
            for child in children:
                if 'type' not in child:
                    child['type'] = 'concept'
                if 'children' not in child:
                    child['children'] = []
            return jsonify({'code': 200, 'children': children})
        else:
            return jsonify({'code': 500, 'message': 'API调用失败'}), 500
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


def count_nodes(node):
    """递归计算节点数量"""
    count = 1
    for child in node.get('children', []):
        count += count_nodes(child)
    return count

def count_nodes_by_type(node):
    """统计节点类型"""
    counts = {'total': 1, 'papers': 0, 'concepts': 0}
    
    if node.get('type') == 'paper':
        counts['papers'] = 1
    elif node.get('type') == 'concept':
        counts['concepts'] = 1
    
    for child in node.get('children', []):
        child_counts = count_nodes_by_type(child)
        counts['total'] += child_counts['total']
        counts['papers'] += child_counts['papers']
        counts['concepts'] += child_counts['concepts']
    
    return counts

def get_preview_text(node, max_length=80):
    """获取节点预览文本"""
    preview = node.get('name', '')
    
    if node.get('type') == 'paper':
        authors = node.get('authors', '')
        year = node.get('year', '')
        if authors or year:
            preview += f" ({authors}, {year})"
    
    return preview[:max_length]

def find_node_by_path(node, path):
    """根据路径查找节点"""
    if not path:
        return node
    
    parts = path.split('/')
    current = node
    
    for part in parts:
        found = False
        for child in current.get('children', []):
            if child.get('name') == part:
                current = child
                found = True
                break
        if not found:
            return None
    return current

@app.route('/api/tree/<tree_name>/reorder', methods=['POST'])
def reorder_children(tree_name):
    """批量调整同级节点的优先级顺序"""
    try:
        data = request.get_json()
        parent_path = data.get('parent_path', '')
        ordered_names = data.get('ordered_names', [])
        
        if not ordered_names:
            return jsonify({'code': 400, 'message': 'ordered_names 不能为空'}), 400
        
        if not st.exists(tree_name):
            return jsonify({'code': 404, 'message': '知识树不存在'}), 404
        
        tree = st.read(tree_name)
        
        # 找到父节点
        if parent_path:
            parent = find_node_by_path(tree, parent_path)
            if not parent:
                return jsonify({'code': 404, 'message': '父节点不存在'}), 404
            children = parent.get('children', [])
        else:
            children = tree.get('children', [])
        
        # 建立名称到节点的映射
        name_to_node = {node['name']: node for node in children}
        
        # 按新顺序重新设置 importance
        new_children = []
        for idx, name in enumerate(ordered_names, start=1):
            if name not in name_to_node:
                return jsonify({'code': 400, 'message': f'节点 "{name}" 不在子节点中'}), 400
            node = name_to_node[name]
            node['importance'] = idx
            new_children.append(node)
        
        
        existing_names = set(name_to_node.keys())
        ordered_set = set(ordered_names)
        leftover = [node for name, node in name_to_node.items() if name not in ordered_set]
        for node in leftover:
            if 'importance' not in node:
                node['importance'] = len(new_children) + 1
            new_children.append(node)
        
        # 更新父节点的 children
        if parent_path:
            parent['children'] = new_children
        else:
            tree['children'] = new_children
        
        tree['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        st.create(tree_name, tree)

        def sort_children_by_importance(node):
            if 'children' in node and node['children']:
                node['children'].sort(key=lambda x: x.get('importance', 999))
                for child in node['children']:
                    sort_children_by_importance(child)
            return node

# 在 get_tree_detail 返回前调用
        data = sort_children_by_importance(data)
        
        return jsonify({
            'code': 200,
            'message': '优先级更新成功',
            'children': new_children
        })
    
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500

@app.route('/api/tree/<tree_name>/auto_importance',methods = ['POST'])
def auto_importance(tree_name):
    try:
        data = request.get_json()
        parent_path = data.get('parent_path','')

        if not st.exists(tree_name):
            return jsonify({'code':404,'message':'知识树不存在'}),404
        
        tree = st.read(tree_name)
        if parent_path :
            parent=find_node_by_path(tree,parent_path)
            if not parent_path:
                return jsonify({'code':404,'message':'知识树不存在'})
            children = parent.get('children',[])
        else :
            children  =tree.get('children',[])

        if not children:
            return jsonify({'code':404,'message':'没有子节点可以排序'}),400
        
        nodes_info = "\n".join([f" - {node['name']}: {node.get('description','无描述')}" for node in children])
        prompt = f"""请根据以下原则，对下列同一主题下的子节点进行**学习顺序排序**（从最应该先学、最重要到最不重要）：

排序原则：
1. 基础概念优先（作为其他知识前提的排在前面）
2. 核心思想优先（最通用、引用最多的排前）
3. 理论先于应用（concept 排在 paper 之前）
4. 经典先于前沿（开创性工作排在改进工作前）
5. 宽泛先于专深（适用范围广的排前）

子节点列表：
{nodes_info}

只输出节点名称的 JSON 数组，例如：["概念A", "概念B", "论文C"]
"""
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是知识重要性排序专家。只输出JSON数组。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(DEEPSEEK_ENDPOINT, headers=HEADERS, json=payload, timeout=60)
        if response.status_code != 200:
            return jsonify({'code': 500, 'message': 'AI排序失败'}), 500
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        ordered_names = json.loads(content)
        if not isinstance(ordered_names, list):
            ordered_names = []
        

        reorder_data = {
            "parent_path": parent_path,
            "ordered_names": ordered_names
        }
        # 直接复用 reorder 函数（可提取为内部函数）
        with app.test_request_context(json=reorder_data):
            res = reorder_children(tree_name)
            return res
    
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500

def assign_default_importance(node, sibling_index=0):
    if 'importance' not in node:
        node['importance'] = sibling_index + 1
    for idx, child in enumerate(node.get('children', [])):
        assign_default_importance(child, idx)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)