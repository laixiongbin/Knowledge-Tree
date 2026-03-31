import os
import json
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import restore
from datetime import datetime
import io

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app)  # 允许前端跨域访问

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_ENDPOINT = os.getenv("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")

# 请求头
HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}

def call_deepseek(prompt):
    """调用 DeepSeek API，返回知识树 JSON"""
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个知识树生成助手。请根据用户输入的关键词，生成一个结构化的知识树，输出格式必须是严格的 JSON，包含 name, type, children 等字段。只返回 JSON，不要有任何额外说明。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"}
    }
    try:
        response = requests.post(DEEPSEEK_ENDPOINT, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        try:
            tree_data = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                tree_data = json.loads(match.group(1))
            else:
                tree_data = json.loads(content)
        return tree_data
    except Exception as e:
        print(f"API 请求失败: {e}")
        return None

@app.route('/generate', methods=['POST'])
def generate_knowledge_tree():
    """接收关键词，返回知识树 JSON"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    prompt = f"""
    请为关键词“{keyword}”生成一个知识树。结构要求：
    - 根节点名称是关键词。
    - 第一层子节点为三个分类：“前置理论基础”、“核心概念与验证”、“应用与前沿”。
    - 每个分类下至少包含2-3个具体的知识点，每个知识点可以是论文节点或概念节点。
    - 论文节点需要包含字段：name, type: "paper", quote, url, authors, year。
    - 概念节点只需要 name 和 type: "concept"。
    - 所有节点都必须有 name 和 type 字段，且 children 字段存在（即使为空数组）。
    输出必须是严格的 JSON 格式，不要有任何注释。
    """
    tree_data = call_deepseek(prompt)
    if tree_data is None:
        return jsonify({'error': '生成知识树失败，请稍后重试'}), 500

    if 'name' not in tree_data:
        tree_data['name'] = keyword
    if 'children' not in tree_data:
        tree_data['children'] = []
    
    tree_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tree_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(tree_data)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# 保存API
st = restore.JSONStorage('storage.json')



@app.route('/api/trees', methods=['GET'])
def get_all_trees():
    """获取所有知识树列表"""
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
    """获取单个知识树的完整数据"""
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
    """向知识树添加节点"""
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
            # 在指定路径下添加节点
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
        
        # 更新时间戳
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
    """更新知识树中的节点"""
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
        
        # 更新节点数据（保留原有字段，只更新提供的字段）
        node.update(update_data)
        
        # 更新时间戳
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
    """删除知识树中的节点"""
    try:
        if not st.exists(tree_name):
            return jsonify({
                'code': 404,
                'message': f'找不到知识树 "{tree_name}"'
            }), 404
        
        tree = st.read(tree_name)
        
        # 解析节点路径
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
            # 删除根节点下的子节点
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
        
        # 更新时间戳
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
    """批量添加节点"""
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
    """接收前端的数据并保存"""
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
    """更新知识树"""
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
    """删除知识树"""
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)