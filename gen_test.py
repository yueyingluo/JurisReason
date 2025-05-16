import os
# 通过 pip install volcengine-python-sdk[ark] 安装方舟SDK
from volcenginesdkarkruntime import Ark
# export VOLCENGINE_API_KEY="53e3f259-037d-412d-98ea-0b4c5b45d5a4"
# python gen_test.py
# Get API key from environment variable
api_key = os.environ.get("VOLCENGINE_API_KEY")
if not api_key:
    raise ValueError("API key not found. Set the VOLCENGINE_API_KEY environment variable.")

model = "deepseek-v3-250324"

# 初始化Ark客户端
client = Ark(api_key=api_key)

test_question="王某系某国家机关工作人员，被群众举报收受他人贿赂，市纪委对其立案查处，查出王某在建设本单位办公楼的过程中，收受工程施工方的贿赂计人民币3000元。在市纪委找其谈话过程中，\
    王某主动交代了另4起收受他人贿赂计人民币9万的事实。下列说法正确的有哪些?"+' "A": "王某构成受贿罪自首，应当从轻或者减轻处罚",\
      "B": "王某的行为不构成自首，属于坦白，可以酌情从轻处罚",\
      "C": "王某的行为属于坦白，应当从轻处罚",\
      "D": "王某的行为成立受贿罪自首，可以从轻或者减轻处罚" '

completion = client.chat.completions.create(
    model = model,
    messages = [
        {"role": "system", "content": '你是法学专家。阅读题目，参考法条，给出答案。'},
        {"role": "user", "content": test_question},
    ],
)

response = completion.choices[0].message.content
print(response)