from flask import Flask, request, jsonify
import json
import numpy as np
import faiss
import torch
from FlagEmbedding import FlagModel
import os

# 设置 CUDA 环境
os.environ["CUDA_VISIBLE_DEVICES"] = "2"

# Flask 应用实例
app = Flask(__name__)

# 加载模型和数据
class RetrievalAPI:
    def __init__(self, model_path, fatiao_path):
        # 加载 fatiao 数据
        self.f2id, self.id2f, self.fatiaos_list = self.load_fatiaos(fatiao_path)
        
        # 初始化模型
        self.model = FlagModel(model_path, query_instruction_for_retrieval="为这个句子生成表示以用于检索相关文章：")
        
        # 生成 fatiao embeddings
        self.fatiao_embeddings = self.generate_fatiao_emb(self.model, self.fatiaos_list)
        
        # 创建索引
        self.index = faiss.IndexFlatIP(self.fatiao_embeddings.shape[-1])
        self.index.add(self.fatiao_embeddings)

    def load_fatiaos(self, path):
        fatiaos = json.load(open(path, 'r'))
        f2id = {}
        id2f = {}
        fatiaos_list = []
        for k in fatiaos:
            f2id[fatiaos[k]] = k
            id2f[k] = fatiaos[k]
            fatiaos_list.append(fatiaos[k])
        return f2id, id2f, fatiaos_list

    def generate_fatiao_emb(self, model, fatiaos):
        fatiao_embeddings = model.encode(fatiaos)
        return fatiao_embeddings.astype(np.float32)
    
    def retrieve(self, query, top_k=3):
        q_embeddings = self.model.encode_queries([query]).astype(np.float32)
        D, I = self.index.search(q_embeddings, top_k)
        topK_result = [self.fatiaos_list[i] for i in I[0]]
        topK_result = [{self.f2id[r]: self.id2f[self.f2id[r]]} for r in topK_result]
        return topK_result
    def batch_retrieve(self, queries, top_k=3):
        q_embeddings = self.model.encode_queries(queries).astype(np.float32)
        D, I = self.index.search(q_embeddings, top_k)
        topK_results = [[self.fatiaos_list[i] for i in I[j]] for j in range(len(queries))]
        topK_results = [[{self.f2id[r]: self.id2f[self.f2id[r]]} for r in topK_results[j]] for j in range(len(queries))]
        return topK_results

# 初始化检索系统实例
retrieval_api = RetrievalAPI(
    model_path="retrieve_model/v2_ep-20_lr-1e-4_bs-64",
    fatiao_path='data/fatiaos_v2.json'
)

# API 路由，接收查询请求并返回结果
@app.route('/retrieve', methods=['POST'])
def retrieve():
    try:
        # 从请求中获取参数
        data = request.get_json()
        queries = data.get('queries', '')
        top_k = data.get('top_k', 3)

        if not queries:
            return jsonify({"error": "Query is required"}), 400

        # 使用检索系统进行查询
        results = retrieval_api.batch_retrieve(queries, top_k=top_k)
        
        # 返回查询结果
        return jsonify({"articles": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 启动 Flask 应用
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5060)
