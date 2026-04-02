import json
import os

class JSONStorage:
    """JSON文件存储类 - 以TreeName为key存储数据"""
    
    def __init__(self, filename='data.json'):
        self.filename = filename
        # 如果文件不存在，自动创建空文件
        if not os.path.exists(filename):
            self.save_data({})
    
    def load_data(self):
        """加载数据"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def save_data(self, data):
        """保存数据"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create(self, TreeName, TreeData):
        """创建或更新数据（以TreeName为key）"""
        data = self.load_data()
        data[TreeName] = TreeData
        self.save_data(data)
        return True
    
    def read(self, TreeName):
        """读取指定TreeName的数据"""
        data = self.load_data()
        return data.get(TreeName)
    
    def read_all(self):
        """读取所有数据"""
        return self.load_data()
    
    def delete(self, TreeName):
        """删除指定TreeName的数据"""
        data = self.load_data()
        if TreeName in data:
            del data[TreeName]
            self.save_data(data)
            return True
        return False
    
    def update(self, TreeName, TreeData):
        """更新指定TreeName的数据（如果存在）"""
        data = self.load_data()
        if TreeName in data:
            data[TreeName] = TreeData
            self.save_data(data)
            return True
        return False
    
    def exists(self, TreeName):
        """检查TreeName是否存在"""
        data = self.load_data()
        return TreeName in data
    
    def get_all_keys(self):
        """获取所有TreeName"""
        data = self.load_data()
        return list(data.keys())
    
    def clear(self):
        """清空所有数据"""
        self.save_data({})
        return True
    
    def get_size(self):
        """获取数据条数"""
        data = self.load_data()
        return len(data)