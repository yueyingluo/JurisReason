# v2 update
# 2025.4.27
# 1. 调用API独立成get_response函数
# 2. 修改了所有prompt，query变成法条
# 3. 修改了处理json的方式（使用json.loads()解析json）
# 4. 增加try..except..处理json解析错误
# TODO：要取消query条数限制吗（？）（但是这样就不能控制每次查出来的法条3K条了）
# TODO：最后的COT格式需要修改吗（？）
#     （反正都已经是用法条作query了，要不直接在最后的COT中去掉query？）
#     （或者把前面的prompt都改一下（不然要么变成前面的格式， 要么think/ search/ information和前面的推理过程基本没有关系）
# TODO：处理读入的json和输出整理后的COTjson（借鉴一下huatuo？）（求求有没有什么json解析教程推荐wwwww）

# 整体逻辑：
# 1. init_query：输入question，输出法条作为三个query
# 2. retrieve：输入三个query，输出result（检索出的法条）（json）
# 3. judge_and_answer：输入result和question，判断result法条是否相关，输出对question的回答response（json）
# 4. verify_answer：输入response和groundtruth，验证答案是否正确（返回True/False）
# 5. revise：如果答案错误，修正答案/法条 （设置最大迭代次数）
# 6. save_answer：保存答案

import os
# 通过 pip install volcengine-python-sdk[ark] 安装方舟SDK
from volcenginesdkarkruntime import Ark

api_key = "53e3f259-037d-412d-98ea-0b4c5b45d5a4"
modelv3 = "deepseek-v3-250324"
modelr1 = "deepseek-r1-250120"

# 初始化Ark客户端
client = Ark(api_key = api_key)

test_question="王某系某国家机关工作人员，被群众举报收受他人贿赂，市纪委对其立案查处，查出王某在建设本单位办公楼的过程中，收受工程施工方的贿赂计人民币3000元。在市纪委找其谈话过程中，\
        王某主动交代了另4起收受他人贿赂计人民币9万的事实。下列说法正确的有哪些?"+' "A": "王某构成受贿罪自首，应当从轻或者减轻处罚",\
        "B": "王某的行为不构成自首，属于坦白，可以酌情从轻处罚",\
        "C": "王某的行为属于坦白，应当从轻处罚",\
        "D": "王某的行为成立受贿罪自首，可以从轻或者减轻处罚" '

def get_response(model, system_prompt, user_prompt):
    # 创建一个对话请求
    completion = client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    response = completion.choices[0].message.content
    return response

def init_query(question=test_question):
    # 用他背的法条当做query
    ini_prompt='你是一名法学专家。你非常擅长阅读法律案例与回忆相关的法条。\
        请你阅读一道司法考试题目和它的选项，认真阅读每一个选项，有逻辑地思考。\
        你需要对每一个选项，详细地分析，联系题目，给出分析这个选项所有可能需要参考的法条。'

    format_request="""你的输出格式必须严格按照以下的样例json输出格式\
    ```json
    {{
        "思考过程": "...",
        "法条1": "《中华人民共和国民法典》第xxx条：xxx",
        "法条2": "《中华人民共和国刑法》第xxx条：xxx",
        "法条3": "《xx法》第xxx条：xxx",
    }}
    ```"""

    response = get_response(modelv3, ini_prompt + format_request, question)
    # 解析返回的 JSON 响应
    try:
        # Try to extract the JSON part from the response
        json_start = response.find('```json')
        json_end = response.find('```', json_start + 7)
        
        if json_start != -1 and json_end != -1:
            json_str = response[json_start + 7:json_end].strip()
            response_json = json.loads(json_str)
        else:
            # Try to parse the whole response
            response_json = json.loads(response)
        
        # Extract the law articles
        query1 = response_json.get("法条1", "")
        query2 = response_json.get("法条2", "")
        query3 = response_json.get("法条3", "")
        
    except Exception as e:
        print(f"Error parsing JSON response: {e}. Retrying...")
        # Retry with the same prompt
        response = get_response(modelv3, ini_prompt + format_request, question)
        try:
            json_start = response.find('```json')
            json_end = response.find('```', json_start + 7)
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start + 7:json_end].strip()
                response_json = json.loads(json_str)
            else:
                response_json = json.loads(response)
            
            query1 = response_json.get("法条1", "")
            query2 = response_json.get("法条2", "")
            query3 = response_json.get("法条3", "")
        except Exception as e:
            print(f"Failed to parse JSON response again: {e}. Using question as query.")
            query1 = query2 = query3 = question
    return query1, query2, query3

import requests
import json
import re

def retrieve(query1, query2, query3):
    # API 服务的地址（确保 Flask 或 FastAPI 服务已在 localhost 上运行）
    api_url = "http://localhost:5060/retrieve"

    # 请求体，包含查询文本和返回结果的数量
    data = {
        "queries": [query1, query2, query3],
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
    return result

def judge_and_answer(result):
    # 将检索到的法条转换为字符串格式
    result_str = json.dumps(result, ensure_ascii=False)

    judge_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
        你会看到一些相关的法条，排除对你没有帮助的法条，只参考你认为对你分析这道题有帮助的法条。你也可以自己回忆相关的法条进行分析来帮助你回答。\
        你需要对每一个选项，详细地解释，联系题目，进行相应的分析。然后在“参考法条”中准确地给出你参考的法条内容你需要在回答的最后根据你对题目和每一个选项的分析，给出你的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。'

    answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式,\
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

    response = get_response(modelv3, judge_answer_prompt + answer_format_prompt, result_str)
    
    # print(response)
    return response

def verify_answer(response, ground_truth='D'):
    # 解析返回的 JSON 响应，只选取最终答案，确保格式是大写字母组合
    # LKC: json.load()
    try:
        # Try to extract the JSON part from the response
        json_start = response.find('```json')
        json_end = response.find('```', json_start + 7)
        
        if json_start != -1 and json_end != -1:
            json_str = response[json_start + 7:json_end].strip()
            response_json = json.loads(json_str)
        else:
            # Try to parse the whole response
            response_json = json.loads(response)
        
        # Extract the final answer
        answer = response_json.get("最终答案", "")
        print("最终答案:", answer)
        
    except Exception as e:
        print(f"Error parsing JSON response: {e}")
    
    answer_pattern = re.compile(r'[A-D]+')  # Match one or more capital letters A-D
    match = answer_pattern.search(answer)
    if match:
        answer = match.group(0)  # Get the matched letter(s)
    if answer == ground_truth:
        print("答案正确")
        # 可以存下来了（存到json文件中）（具体以后再写吧）
        return True
    else:
        print("答案错误")
        return False

        
def revise(result, response, question=test_question):
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
        "参考法条": {{
            "法条1": "《xx法》第xxx条：xxx",
            "法条2": "《xx法》第xxx条：xxx",
            ...
        }},
        "最终答案": "...",
    }}
    ```
    如果你认为需要检索新的法条：```json
    {{
        "思考过程": "...",
        "法条1": "《中华人民共和国民法典》第xxx条：xxx",
        "法条2": "《中华人民共和国刑法》第xxx条：xxx",
        "法条3": "《xx法》第xxx条：xxx",
        }}
    ```
    """  
    response = get_response(modelr1, revise_prompt + revise_format_prompt, question + json.dumps(response, ensure_ascii=False) )
    print("修正后的回答:", response)
    # 解析返回的 JSON 响应
    if '"最终答案":' in response:
        return result, response
    else: 
        # 重新检索法条
        try:
            # Try to extract the JSON part from the response
            json_start = response.find('```json')
            json_end = response.find('```', json_start + 7)
        
            if json_start != -1 and json_end != -1:
                json_str = response[json_start + 7:json_end].strip()
                response_json = json.loads(json_str)
            else:
                # Try to parse the whole response
                response_json = json.loads(response)
        
            # Extract the law articles
            query1 = response_json.get("法条1", "")
            query2 = response_json.get("法条2", "")
            query3 = response_json.get("法条3", "")
        
        except Exception as e:
            print(f"Error parsing JSON response: {e}. Retrying...")
            # Retry with the same prompt
            response = get_response(modelr1, revise_prompt + revise_format_prompt, question + json.dumps(response, ensure_ascii=False) )
            try:
                json_start = response.find('```json')
                json_end = response.find('```', json_start + 7)
            
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start + 7:json_end].strip()
                    response_json = json.loads(json_str)
                else:
                    response_json = json.loads(response)
            
                query1 = response_json.get("法条1", "")
                query2 = response_json.get("法条2", "")
                query3 = response_json.get("法条3", "")
            except Exception as e:
                print(f"Failed to parse JSON response again: {e}. Using question as query.")
                query1 = query2 = query3 = question

        result = retrieve(query1, query2, query3)
        response = judge_and_answer(result)
        return result, response

def save_answer(result, response):
    # 用deepseek r1模型整合COT，保存答案
    save_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。\
        下面是你之前的回答，你的最终答案是正确的。\
        你需要根据你之前的回答，进行分析，整理你的思维过程，合并为如下格式的连贯回答。\
        '
    # save_answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式\
    # <think>reasoning</think>
    # <search>this is a query</search>
    # <information>法条1,2,3。。。</information>
    # <think>reasoning</think>
    # <search>this is a query</search>
    # <information>法条1,2,3。。。</information>
    # ...
    # <answer>BC<answer>"""
    save_answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式\
    ```json
    {{
        "思考过程": "...",
        “参考法条": {{
            "法条1": "《xx法》第xxx条：xxx",
            "法条2": "《xx法》第xxx条：xxx",
            ...
        }},
        "最终答案": "...",
    }}
    ```"""

    response = get_response(modelr1, save_answer_prompt + save_answer_format_prompt, json.dumps(result, ensure_ascii=False) + json.dumps(response, ensure_ascii=False))
    print("保存的答案:", response)
    return response
 

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
    # verify_answer(response, ground_truth)
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

# 示例保存的答案
# ```json
# {
#     "思考过程": "王某因收受3000元被市纪委立案调查，期间主动交代另4起受贿9万元的事实。根据《刑法》第六十七条，被采取强制措施的犯罪嫌疑人如实供述司法机关未掌握的其他罪行的，以自首论。王某在纪委谈话中交代的9万元属于未被掌握的罪行，构成特别自首（余罪自首）。对于自首，法律规定可以从轻或减轻处罚。选项D正确，A错误（因是‘可以’而非‘应当’）。B、C错误，因王某行为属于自首而非坦白。",
#     "参考法条": {
#         "法条1": "《中华人民共和国刑法》第六十七条：被采取强制措施的犯罪嫌疑人、被告人和正在服刑的罪犯，如实供述司法机关还未掌握的本人其他罪行的，以自首论。对于自首的犯罪分子，可以从轻或者减轻处罚。"
#     },
#     "最终答案": "D"
# }
# ```
# 人类解析：
# 根据最高人民法院发布的《关于处理自首和立功具体应用法律若干问题的解释》
# (以下简称《解释》)对“以自首论”做了严格的规定：被采取强制措施的犯罪嫌疑人、被告人和已宣判的罪犯，
# 如实供述司法机关尚未掌握的罪行，与司法机关已掌握的或者判决确定的罪行属不同种罪行的，以自首论。
# 即规定“以自首论”必须是司法机关还未掌握的“其他罪行”。考生很容易产生错误的认识：本案中王某供述的是受贿罪，
# 和纪委调查的行为属于同类，所以王某的行为不构成自首。其实不然，本案中王某的行为与解释规定的情形不同。
# 王某因一般违纪行为被纪委查处，通常情况下不会被采取强制措施。因为根据最高人民检察院的立案标准规定，
# 个人受贿数额在5千元以上的应予立案。在王某主动交代前，纪委掌握的王某的受贿金额仅有3000元，
# 该行为并不构成犯罪，仅属于一般违纪行为。因此，上述司法解释中对“以自首论”所作的限定，
# 不适用某实施一般违纪行为被查处后主动交代司法机关尚未掌握的同种犯罪行为的情况。
# 王某的行为属于如实供述全部罪行，应以自首论。另根据法律的规定，对于自首行为可以从轻或减轻处罚。
# 所以D选项正确，ABC选项错误。