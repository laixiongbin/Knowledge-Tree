import os
import json
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import restore
import paper_enrich
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

# DeepSeek json_object 模式要求：提示里必须出现英文 "json"，并给出示例，否则会长时间输出空白直至触顶 token。
DEEPSEEK_SYSTEM_TREE = """你是知识树生成助手。请根据用户主题输出一个 json 对象（仅此一个 json，不要 Markdown）。
结构规则：根与中间节点 type 均为 "concept"；仅最深层允许 "paper"，且 paper 的 children 必须为 []。
同一父节点的 children 要么全是 concept（继续展开），要么全是 paper（结束分支），禁止混排。
从根到任一 paper 的路径长度为 4 或 5 层（第1层根，第2层为三个固定分类名）。
关于 paper 的 url：你没有联网检索能力。禁止编造或占位链接（禁止使用 example.com、test.com、placeholder、假 DOI 等）。不确定时 url 必须为空字符串 ""；服务端会按标题依次通过 arXiv、Semantic Scholar、OpenAlex 尝试补全可点击链接。
EXAMPLE JSON OUTPUT（字段名必须一致，内容替换为用户主题）:
{"name":"示例主题","type":"concept","children":[{"name":"前置理论基础","type":"concept","children":[{"name":"子主题","type":"concept","children":[{"name":"某论文","type":"paper","quote":"","url":"","authors":"","year":"2020","children":[]}]}]},{"name":"核心概念与验证","type":"concept","children":[]},{"name":"应用与前沿","type":"concept","children":[]}]}"""


def call_deepseek(prompt):
    """调用 DeepSeek API，返回 (知识树 dict 或 None, 错误说明或 None)。"""
    if not DEEPSEEK_API_KEY or not str(DEEPSEEK_API_KEY).strip():
        return None, "未配置 DEEPSEEK_API_KEY"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": DEEPSEEK_SYSTEM_TREE},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    try:
        response = requests.post(
            DEEPSEEK_ENDPOINT, headers=HEADERS, json=payload, timeout=120
        )
        if not response.ok:
            snippet = (response.text or "")[:800]
            print(f"DeepSeek HTTP {response.status_code}: {snippet}")
            return None, f"上游接口 HTTP {response.status_code}"

        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            return None, "上游返回无 choices 字段"

        choice0 = choices[0]
        finish_reason = choice0.get("finish_reason")
        msg = choice0.get("message") or {}
        content = msg.get("content")
        if content is None or not str(content).strip():
            print(f"DeepSeek 空内容 finish_reason={finish_reason} raw={repr(result)[:500]}")
            return None, f"模型返回空内容（finish_reason={finish_reason}）"

        content = str(content).strip()

        try:
            tree_data = json.loads(content)
        except json.JSONDecodeError:
            import re

            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
            if match:
                try:
                    tree_data = json.loads(match.group(1).strip())
                except json.JSONDecodeError as e:
                    print(f"JSON 解析失败(代码块): {e}\n前300字: {content[:300]}")
                    return None, "模型返回的 json 无法解析"
            else:
                print(f"JSON 解析失败: {content[:400]}")
                return None, "模型返回的 json 无法解析"

        if finish_reason == "length":
            print("警告: finish_reason=length，输出可能被截断，若前端异常可适当缩小树规模")

        return tree_data, None
    except requests.RequestException as e:
        print(f"API 请求失败: {e}")
        return None, f"网络请求失败: {e}"
    except (KeyError, TypeError, ValueError) as e:
        print(f"API 响应异常: {e}")
        return None, f"响应格式异常: {e}"

@app.route('/generate', methods=['POST'])
def generate_knowledge_tree():
    """接收关键词，返回知识树 JSON"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    prompt = f"""请为主题「{keyword}」生成一棵完整知识树，输出为单个 json 对象（与 system 中的 EXAMPLE JSON OUTPUT 同一结构风格）。
层数从根计：第1层根、第2层恰为「前置理论基础」「核心概念与验证」「应用与前沿」三个 concept。
第3层每分类下 2～3 个 concept；不得在第3层出现 paper。
从根到任一 paper 的路径总长须为 4 或 5：要么第3层 concept 下直接挂 2～3 个 paper（4 层）；要么第3层下再接一层 concept，其下再挂 1～3 个 paper（5 层）。同一父节点下 children 要么全 concept 要么全 paper。
每篇 paper 含 name,type,quote,url,authors,year,children([])。为控制长度，每处 paper 列表最多 3 条。
url 规则：勿填示例站；无把握则 url 留空 ""，服务端会按 arXiv → Semantic Scholar → OpenAlex 顺序补全链接。
"""
    tree_data, api_err = call_deepseek(prompt)
    if tree_data is None:
        return jsonify(
            {"error": "生成知识树失败，请稍后重试", "detail": api_err or "未知错误"}
        ), 500

    if 'name' not in tree_data:
        tree_data['name'] = keyword
    if 'children' not in tree_data:
        tree_data['children'] = []

    try:
        paper_enrich.enrich_tree_with_literature(tree_data)
    except Exception as e:
        print(f"文献链接补全失败（已返回未补全的树）: {e}")
    
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