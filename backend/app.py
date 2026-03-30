import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()
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
        "response_format": {"type": "json_object"}  # DeepSeek 支持 JSON 模式
    }
    try:
        response = requests.post(DEEPSEEK_ENDPOINT, headers=HEADERS, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        # 提取模型返回的内容
        content = result['choices'][0]['message']['content']
        # 解析 JSON（如果模型返回了代码块，需要清理）
        # 尝试直接解析
        try:
            tree_data = json.loads(content)
        except json.JSONDecodeError:
            # 如果内容包含 ```json ... ```，提取中间部分
            import re
            match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                tree_data = json.loads(match.group(1))
            else:
                # 最后尝试直接解析
                tree_data = json.loads(content)
        return tree_data
    except requests.exceptions.RequestException as e:
        print(f"API 请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        return None

@app.route('/generate', methods=['POST'])
def generate_knowledge_tree():
    """接收关键词，返回知识树 JSON"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    # 构造提示词，引导模型生成符合我们格式的知识树
    prompt = f"""
    请为关键词“{keyword}”生成一个知识树。结构要求：
    - 根节点名称是关键词。
    - 第一层子节点为三个分类：“前置理论基础”、“核心概念与验证”、“应用与前沿”。
    - 每个分类下至少包含2-3个具体的知识点，每个知识点可以是论文节点或概念节点。
    - 论文节点需要包含字段：name (论文标题或知识点名称), type: "paper", quote (一段原文摘录), url (原文链接，可以是虚构的示例链接), authors (作者), year (年份)。
    - 概念节点只需要 name 和 type: "concept"。
    - 所有节点都必须有 name 和 type 字段，且 children 字段存在（即使为空数组）。
    输出必须是严格的 JSON 格式，不要有任何注释。
    """
    tree_data = call_deepseek(prompt)
    if tree_data is None:
        return jsonify({'error': '生成知识树失败，请稍后重试'}), 500

    # 可选：对返回的数据进行校验或补充（如确保有根节点、children等）
    if 'name' not in tree_data:
        tree_data['name'] = keyword
    if 'children' not in tree_data:
        tree_data['children'] = []
    return jsonify(tree_data)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)