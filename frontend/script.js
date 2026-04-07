// 等待页面加载完成
document.addEventListener('DOMContentLoaded', () => {
    // 获取 DOM 元素
    const treeChart = echarts.init(document.getElementById('treeChart'));
    const pieChart = echarts.init(document.getElementById('pieChart'));
    const detailContent = document.getElementById('detailContent');
    const generateBtn = document.getElementById('generateBtn');
    const keywordInput = document.getElementById('keyword');

    // 当前知识树数据（用于饼图统计）
    let currentTreeData = null;

    // 渲染树图
    function renderTree(treeData) {
        // 确保数据格式符合 ECharts tree 要求
        const option = {
            series: [{
                type: 'tree',
                data: [treeData],          // 根节点
                layout: 'orthogonal',      // 水平树
                roam: true,                // 允许缩放/移动
                label: {
                    show: true,
                    position: 'left',
                    fontSize: 12,
                    rotate: 0,
                    offset: [0, 0]
                },
                leaves: {
                    label: {
                        position: 'right',
                        offset: [5, 0]
                    }
                },
                expandAndCollapse: true,
                initialTreeDepth: 2,       // 初始展开深度
                lineStyle: {
                    color: '#aaa',
                    width: 1.5,
                    curveness: 0.5
                },
                emphasis: {
                    focus: 'descendant'
                }
            }]
        };
        treeChart.setOption(option, true);
        // 绑定节点点击事件
        treeChart.off('click');  // 避免重复绑定
        treeChart.on('click', (params) => {
            if (params.dataType === 'node') {
                const node = params.data;
                showNodeDetail(node);
            }
        });
    }
    function findNodeByPath(path, treeNode, currentPath = "") {
    const nodePath = currentPath ? `${currentPath}/${treeNode.name}` : treeNode.name;
    if (nodePath === path) return treeNode;
    if (treeNode.children) {
        for (let child of treeNode.children) {
            const found = findNodeByPath(path, child, nodePath);
            if (found) return found;
        }
    }
    return null;
}

    // 显示节点详情
    function showNodeDetail(node) {
        if (!node) return;
        let html = `<h3 class="font-bold text-lg mb-2">${node.name}</h3>`;
        if (node.type === 'paper') {
            html += `
                <div class="text-sm text-gray-700 mb-2">
                    ${node.authors ? `<p><span class="font-semibold">作者：</span>${node.authors}</p>` : ''}
                    ${node.year ? `<p><span class="font-semibold">年份：</span>${node.year}</p>` : ''}
                </div>
                <div class="mt-2 p-3 bg-gray-50 rounded border-l-4 border-blue-400 italic">
                    “${node.quote || '暂无摘录'}”
                </div>
                ${node.url ? `<a href="${node.url}" target="_blank" class="inline-block mt-3 text-blue-600 hover:underline">📄 查看原文</a>` : ''}
            `;
        } else if (node.type === 'concept') {
            html += `<p class="text-gray-700">${node.description || '概念节点，暂无详细说明。'}</p>`;
        } else {
            html += `<p class="text-gray-700">${node.description || '点击节点查看详细信息'}</p>`;
        }
        detailContent.innerHTML = html;
    }

    // 更新饼图（统计各分类下的节点数量）
    function updatePieChart(treeData) {
        if (!treeData || !treeData.children) return;
        // 统计每个一级分类下的节点总数（包括子节点）
        const categoryStats = {};
        function countNodes(node) {
            let total = 1; // 自身计数
            if (node.children) {
                for (const child of node.children) {
                    total += countNodes(child);
                }
            }
            return total;
        }
        for (const category of treeData.children) {
            const name = category.name;
            const count = countNodes(category);
            categoryStats[name] = (categoryStats[name] || 0) + count;
        }
        // 转换为饼图数据格式
        const pieData = Object.entries(categoryStats).map(([name, value]) => ({ name, value }));
        const option = {
            title: {
                text: '知识比重',
                left: 'center',
                top: 10,
                textStyle: { fontSize: 14 }
            },
            tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
            series: [{
                type: 'pie',
                radius: '55%',
                center: ['50%', '55%'],
                data: pieData,
                emphasis: { scale: true },
                label: { show: true, formatter: '{b}: {d}%' }
            }]
        };
        pieChart.setOption(option, true);
    }

    // 调用后端生成知识树
    async function generateTree(keyword) {
        const response = await fetch('http://127.0.0.1:5000/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword: keyword })
        });
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errText}`);
        }
        return await response.json();
    }

    // 处理生成按钮点击
    generateBtn.addEventListener('click', async () => {
        const keyword = keywordInput.value.trim();
        if (!keyword) {
            alert('请输入关键词');
            return;
        }
        // 显示加载状态
        detailContent.innerHTML = '<p class="text-gray-500">AI 正在分析论文，请稍候...</p>';
        generateBtn.disabled = true;
        generateBtn.classList.add('btn-loading');
        try {
            const treeData = await generateTree(keyword);
            if (!treeData || !treeData.name) {
                throw new Error('返回的知识树格式不正确');
            }
            currentTreeData = treeData;
            renderTree(treeData);
            updatePieChart(treeData);
            detailContent.innerHTML = '<p>知识树已生成，点击节点查看详情。</p>';
        } catch (err) {
            console.error(err);
            detailContent.innerHTML = `<p class="text-red-500">生成失败：${err.message}</p>`;
            // 可选：显示备用静态数据
            // loadStaticData();
        } finally {
            generateBtn.disabled = false;
            generateBtn.classList.remove('btn-loading');
        }
    });

    // 可选：加载静态数据作为降级方案（如果后端不可用）
    function loadStaticData() {
        fetch('data/demo.json')
            .then(res => res.json())
            .then(data => {
                currentTreeData = data;
                renderTree(data);
                updatePieChart(data);
                detailContent.innerHTML = '<p class="text-yellow-600">已加载静态演示数据，后端服务可能未启动。</p>';
            })
            .catch(err => console.error('加载静态数据失败', err));
    }

    // 启动时默认加载静态数据，便于演示（可选）
    loadStaticData();
});