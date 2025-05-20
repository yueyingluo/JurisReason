import os
# 通过 pip install volcengine-python-sdk[ark] 安装方舟SDK
from volcenginesdkarkruntime import Ark

api_key = "53e3f259-037d-412d-98ea-0b4c5b45d5a4"
model = "deepseek-v3-250324"

# 初始化Ark客户端
client = Ark(api_key = api_key)

test_question="王某系某国家机关工作人员，被群众举报收受他人贿赂，市纪委对其立案查处，查出王某在建设本单位办公楼的过程中，收受工程施工方的贿赂计人民币3000元。在市纪委找其谈话过程中，\
        王某主动交代了另4起收受他人贿赂计人民币9万的事实。下列说法正确的有哪些?"+' "A": "王某构成受贿罪自首，应当从轻或者减轻处罚",\
        "B": "王某的行为不构成自首，属于坦白，可以酌情从轻处罚",\
        "C": "王某的行为属于坦白，应当从轻处罚",\
        "D": "王某的行为成立受贿罪自首，可以从轻或者减轻处罚" '

# TODO：json格式生成不理想的时候怎么处理（但是好像DeepSeek格式都挺好的）
# LKC: 如果生成的json格式有问题就重新生成，用try..except..处理一下

def init_query(question=test_question):
    # ini_prompt='你是一名法学专家。你非常擅长阅读法律案例，引用相关的法条。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
    #     你需要对每一个选项，详细地解释，联系题目，进行相应的分析，给出分析这个选项需要参考的法条。你需要在回答的最后根据你对题目和每一个选项的分析，总结出解决这道题需要参考的所有法条。'
    ini_prompt='你是一名法学专家。你非常擅长阅读法律案例，提取关键词，回忆相关的法条。\
        请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
        你需要对每一个选项，详细地分析，联系题目，给出分析这个选项所有可能需要参考的法条。\
        接下来，你会使用一个检索器检索你认为能够帮助你解决这个问题的相关法条。检索器会返回与你的检索问题最相关的若干条法条。\
        你有三次检索机会。请认真思考，发挥你的法律专业能力，保证问题的精确和准确性。分别给出你的三个检索问题。'
    
    # LKC: 不一定是三次检索；昨天组会讨论后，我觉得我们可以先试试让它背法条，然后用他背的法条当做query
    # ini_prompt='你是一名法学专家。你非常擅长阅读法律案例与回忆相关的法条。\
    #     请你阅读一道司法考试题目和它的选项，认真阅读每一个选项，有逻辑地思考。\
    #     你需要对每一个选项，详细地分析，联系题目，给出分析这个选项所有可能需要参考的法条。'

    format_request="""你的输出格式必须严格按照以下的json输出格式\
    ```json
    {{
        "思考过程": "...",
        "检索问题1": "...",
        "检索问题2": "...",
        "检索问题3": "...",
        }}
    ```"""
    # LKC: 
    # format_request="""你的输出格式必须严格按照以下的样例json输出格式\
    # ```json
    # {{
    #     "思考过程": "...",
    #     "法条1": "《中华人民共和国民法典》第xxx条：xxx",
    #     "法条2": "《中华人民共和国刑法》第xxx条：xxx",
    #     "法条3": "《xx法》第xxx条：xxx",
    # }}
    # ```"""

    #TODO：query怎么写（关键词or原始问题or有什么要求）

    # 创建一个对话请求
    completion = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": ini_prompt + format_request},
            {"role": "user", "content": question},
        ],
    )

    response = completion.choices[0].message.content
    # 解析返回的 JSON 响应
    # LKC: 这里的response是json格式的，可以直接用json.load()?
    query1 = response.split('"检索问题1":')[1].split('"检索问题2":')[0].replace('"检索问题1":', '').replace('"检索问题2":', '').replace('"检索问题3":', '').replace('}', '').replace('"', '').strip()
    query2 = response.split('"检索问题2":')[1].split('"检索问题3":')[0].replace('"检索问题2":', '').replace('"检索问题3":', '').replace('}', '').replace('"', '').strip()
    query3 = response.split('"检索问题3":')[1].split('}')[0].replace('"检索问题3":', '').replace('}', '').replace('"', '').strip()
    print("检索问题1:", query1)
    print("检索问题2:", query2)
    print("检索问题3:", query3)
    return query1, query2, query3

import requests
import json

def retrieve(query1, query2, query3):
    # API 服务的地址（确保 Flask 或 FastAPI 服务已在 localhost 上运行）
    api_url = "http://localhost:5060/retrieve"

    # 请求体，包含查询文本和返回结果的数量
    data = {
        "queries": [query1, query2, query3],
        "top_k": 3
    }
    # TODO: top_k设置成多少
    # LKC：先设置3试试

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
    return result

def judge_and_answer(result):
    # 这里的 result 是检索到的法条
    # 你可以根据需要对 result 进行处理
    # 例如，提取法条的标题和内容等
    # 这里假设 result 是一个包含法条的列表，每个法条是一个字典
    # 你可以根据实际情况进行调整

    # 将检索到的法条转换为字符串格式
    result_str = json.dumps(result, ensure_ascii=False)
   
    judge_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
        你会看到一些相关的法条，排除对你没有帮助的法条，只参考你认为对你分析这道题有帮助的法条。你也可以自己回忆相关的法条进行分析来帮助你回答。\
        你需要对每一个选项，详细地解释，联系题目，进行相应的分析。你需要在回答的最后根据你对题目和每一个选项的分析，给出你的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。'
    # LKC：
    # judge_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
    #     你会看到一些相关的法条，排除对你没有帮助的法条，只参考你认为对你分析这道题有帮助的法条。你也可以自己回忆相关的法条进行分析来帮助你回答。\
    #     你需要对每一个选项，详细地解释，联系题目，进行相应的分析。然后在“参考法条”中准确地给出你参考的法条内容你需要在回答的最后根据你对题目和每一个选项的分析，给出你的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。'

    answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式\
    ```json
    {{
        "思考过程": "...",
        "参考法条": "...",
        "最终答案": "...",
    }}
    ```
    """
    # LKC: 
    answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式\
    ```json
    {{
        "思考过程": "...",
        "参考法条": {{
            "法条1": "《xx法》第xxx条：xxx",
            "法条2": "《xx法》第xxx条：xxx",
            ...
        }},
        "最终答案": "...",
    }}
    ```
    """

    completion = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content":  judge_answer_prompt + answer_format_prompt},
            {"role": "user", "content": test_question + result_str},
        ],
    )

    response = completion.choices[0].message.content
    print(response)
    return response

def verify_answer(response, question=test_question, ground_truth='D'):
    # 解析返回的 JSON 响应，只选取最终答案，确保格式是大写字母组合
    # LKC: json.load()
    answer = response.split('"最终答案":')[1].split('}')[0].replace('"最终答案":', '').replace('}', '').replace('"', '').strip()
    print("最终答案:", answer)
    # 怎么判断还没有想好怎么写（应该可以直接正则表达式匹配？）
    # LKC: 可以在prompt中要求把答案放在{}中，如{AD}，然后直接正则表达式匹配
    if answer == ground_truth:
        print("答案正确")
        # 可以存下来了（存到json文件中）（具体以后再写吧）
        return True
    else:
        print("答案错误")
        return False

        
def revise(result, response, question=test_question):
    # 这里可以添加一些逻辑来修正答案
    # 例如，重新生成答案或修改答案
    revise_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
        下面是你之前的回答，你的最终答案是不正确的。\
        你需要根据你之前的回答，重新分析，判断你之前使用的法条是否正确且足够支撑你的分析。\
        如果你认为不需要检索新的法条，在你之前的推理基础上继续思考，给出新的答案。你需要在回答的最后根据你对题目和每一个选项的分析，给出你的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。\
        如果你认为需要检索新的法条，给出新的检索问题。\
        '
    
    # LKC：和前面一样做些小修改：1."参考法条"是一个dict 2.检索问题i-->法条i
    revise_format_prompt="""你的输出格式必须严格按照以下的两种json输出格式之一\
    如果你认为不需要检索新的法条：```json
    {{
        "思考过程": "...",
        "参考法条": "...",
        "最终答案": "...",
    }}
    ```
    如果你认为需要检索新的法条：```json
    {{
        "思考过程": "...",
        "检索问题1": "...",
        "检索问题2": "...",
        "检索问题3": "...",
        }}
    ```
    """  
    completion = client.chat.completions.create(
        model = "deepseek-r1-250120",#行吧用r1试试
        messages = [
            {"role": "system", "content":  revise_prompt + revise_format_prompt},
            {"role": "user", "content": question + response},
        ],
    )
    response = completion.choices[0].message.content
    print("修正后的回答:", response)
    # 解析返回的 JSON 响应
    if '"最终答案":' in response:
        return result, response
    else: 
        # 重新检索法条
        query1 = response.split('"检索问题1":')[1].split('"检索问题2":')[0].replace('"检索问题1":', '').replace('"检索问题2":', '').replace('"检索问题3":', '').replace('}', '').replace('"', '').strip()
        query2 = response.split('"检索问题2":')[1].split('"检索问题3":')[0].replace('"检索问题2":', '').replace('"检索问题3":', '').replace('}', '').replace('"', '').strip()
        query3 = response.split('"检索问题3":')[1].split('}')[0].replace('"检索问题3":', '').replace('}', '').replace('"', '').strip()
        print("修正后的检索问题1:", query1)
        print("修正后的检索问题2:", query2)
        print("修正后的检索问题3:", query3)
        result = retrieve(query1, query2, query3)
        response = judge_and_answer(result)
        return result, response

def save_answer(result, response):
    # 用deepseek r1模型整合COT，保存答案
    save_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。\
        下面是你之前的回答，你的最终答案是正确的。\
        你需要根据你之前的回答，进行分析，整理你的思维过程，合并为如下格式的连贯回答。\
        '
    save_answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式\
    <think>reasoning</think>
    <search>this is a query</search>
    <information>法条1,2,3。。。</information>
    <think>reasoning</think>
    <search>this is a query</search>
    <information>法条1,2,3。。。</information>
    ...
    <answer>BC<answer>"""
    result = json.dumps(result, ensure_ascii=False)
    completion = client.chat.completions.create(
        model = "deepseek-r1-250120",
        messages = [
            {"role": "system", "content":  save_answer_prompt + save_answer_format_prompt},
            {"role": "user", "content": result + response},
        ],
    )
    response = completion.choices[0].message.content
    print("保存的答案:", response)
    return response
 

# TODO:好像被之前的格式带歪了，看看要不要把之前的prompt改一下
# ```json
# {
#     "思考过程": "根据案例描述，王某在被市纪委立案查处期间，主动交代了未被掌握的4起受贿事实。根据《中华人民共和国刑法》第六十七条第三款，被采取强制措施的犯罪嫌疑人如实供述司法机关尚未掌握的本人其他罪行的，应当认定为自首。因此，王某的行为构成自首。对于自首的犯罪分子，法条规定'可以'从轻或减轻处罚，而非'应当'。选项D正确，因为它准确引用了'可以'这一量刑裁量权。选项A错误在于使用了'应当'，而B和C错误地将该行为定性为坦白，不符合自首的构成要件。",
#     "参考法条": "《中华人民共和国刑法》第六十七条",
#     "最终答案": "D"
# }

if __name__ == "__main__":
    # TODO: 需要从json文件中读取问题和答案
    # question = 
    # ground_truth = 
    # query1, query2, query3 = init_query(question)
    
    query1, query2, query3 = init_query()

    # 检索法条
    result = retrieve(query1, query2, query3)

    # 判断和回答
    response = judge_and_answer(result)

    # 验证答案
    max_iterations = 3
    flag = verify_answer(response)
    # verify_answer(response, question, ground_truth)
    for i in range(max_iterations):
        print(flag)
        if flag == True:
            # TODO
            # 答案正确，保存答案（result和response）
            response = save_answer(result, response)
            # 保存response到json文件中
            break
        else:
            # 修正答案
            result, response = revise(result, response)
            # revise(result, response, question)
            flag = verify_answer(response)