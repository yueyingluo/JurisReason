import requests
import json

# API 服务的地址（确保 Flask 或 FastAPI 服务已在 localhost 上运行）
api_url = "http://localhost:5060/retrieve"

# 要查询的文本
query = "原告张兴凤向本院提出诉讼请求：1.判令二被告连带支付原告工程款80000.00元及利息（起诉之日起按中国人民银行同期贷款利率计算）；2.由被告承担本案全部诉讼费。事实与理由：2019年9月，被告刘明勇将松潘县古城2号厕所新建工程转包给被告尹明章。同年9月22日，被告尹明章作为发包人将该工程发包给原告的丈夫李永太实际施工，并签订了《土建施工承包合同》，合同总价款为350000.00元。2019年9月20日，李永太组织人员进场施工，两个月后施工完毕，工程经过竣工验收"

# 请求体，包含查询文本和返回结果的数量
data = {
    "queries": [query, '离婚怎么分财产'],
    "top_k": 3
}

# 发送 POST 请求到 API
response = requests.post(api_url, json=data)

# 解析返回的 JSON 响应
if response.status_code == 200:
    result = response.json()
    print("Retrieved articles:")
    print(json.dumps(result, indent=4, ensure_ascii=False))
else:
    print(f"Error: {response.status_code}")
    print(response.text)
