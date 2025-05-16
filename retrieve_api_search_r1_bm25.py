from flask import Flask, request, jsonify
import json
import os
from rank_bm25 import BM25Okapi
from FlagEmbedding import FlagModel
import jieba

# Flask 应用实例
app = Flask(__name__)

# 加载模型和数据
class RetrievalAPI:
    def __init__(self, fatiao_path):
        # 加载 fatiao 数据
        self.f2id, self.id2f, self.fatiaos_list, self.docs = self.load_fatiaos(fatiao_path)
        
        # 准备BM25索引
        self.tokenized_docs = [list(jieba.cut(doc['contents'])) for doc in self.docs]
        self.bm25 = BM25Okapi(self.tokenized_docs)

    def load_fatiaos(self, path):
        fatiaos = json.load(open(path, 'r'))
        f2id = {}
        id2f = {}
        fatiaos_list = []
        for k in fatiaos:
            f2id[fatiaos[k]] = k
            id2f[k] = fatiaos[k]
            fatiaos_list.append(fatiaos[k])
        docs = []
        for k,v in fatiaos.items():
            docs.append({'id': k, 'contents': f'{k}: {v}'})
        return f2id, id2f, fatiaos_list, docs
    
    def retrieve(self, query, top_k=3):
        tokenized_query = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
        topK_result = [self.fatiaos_list[i] for i in top_indices]
        topK_result = [{self.f2id[r]: self.id2f[self.f2id[r]]} for r in topK_result]
        return topK_result
    
    def batch_retrieve(self, queries, top_k=3):
        results = []
        for query in queries:
            tokenized_query = list(jieba.cut(query))
            scores = self.bm25.get_scores(tokenized_query)
            top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
            results.append([{'document': self.docs[i]} for i in top_indices])
        return results

# 初始化检索系统实例
retrieval_api = RetrievalAPI(
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
            print(data)
            return jsonify({"result": []}), 400

        # 使用检索系统进行查询
        results = retrieval_api.batch_retrieve(queries, top_k=top_k)
        
        # 返回查询结果
        return jsonify({"result": results})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 启动 Flask 应用
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5060)
