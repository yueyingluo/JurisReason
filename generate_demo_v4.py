# v4.2 update:
# 2025.5.20
# 0. 给save_answer也拆成sys_prompt和user_prompt了
# 1. debug了4.1中revise函数改了json格式但是reasoning_process的json.get里面的内容没改的问题

# 流程图参考pipeline.jpg（

# demo见output/all_results.json

import os
# 通过 pip install volcengine-python-sdk[ark] 安装方舟SDK
from volcenginesdkarkruntime import Ark
import json
import re
import requests

api_key = # please load from your config 
modelv3 = "deepseek-v3-250324"
modelr1 = "deepseek-r1-250120"

# 初始化Ark客户端
client = Ark(api_key=api_key)

test_question = "王某系某国家机关工作人员，被群众举报收受他人贿赂，市纪委对其立案查处，查出王某在建设本单位办公楼的过程中，收受工程施工方的贿赂计人民币3000元。在市纪委找其谈话过程中，\
        王某主动交代了另4起收受他人贿赂计人民币9万的事实。下列说法正确的有哪些?"+' "A": "王某构成受贿罪自首，应当从轻或者减轻处罚",\
        "B": "王某的行为不构成自首，属于坦白，可以酌情从轻处罚",\
        "C": "王某的行为属于坦白，应当从轻处罚",\
        "D": "王某的行为成立受贿罪自首，可以从轻或者减轻处罚" '


def get_response(model, system_prompt, user_prompt):
    # 创建一个对话请求
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    response = completion.choices[0].message.content
    return response

# initial round:
# input question, output reasoning process and law query


def init_query(question=test_question):
    # 用他背的法条当做query
    sys_prompt = "你是一名法学专家。"
    # ini_prompt = '你是一名法学专家。你非常擅长阅读法律案例与回忆相关的法条。\
    #     请你阅读一道司法考试题目和它的选项，认真阅读每一个选项，有逻辑地思考。\
    #     你需要给出分析题目所有可能需要参考的法条。'
    ini_prompt = '请你阅读一道司法考试题目，先进行分析，然后给出解题必须参考的法条（不包括司法解释）。'

    format_request = """你的输出格式必须严格按照以下的样例json输出格式\
    ```json
    {{
        "思考过程": "...",
        "法条1": "《中华人民共和国民法典》第xxx条：xxx",
        "法条2": "《中华人民共和国刑法》第xxx条：xxx",
        "法条3": "《xx法》第xxx条：xxx",
        ...
    }}
    ```"""
    response = get_response(modelv3, sys_prompt, ini_prompt +
                            format_request + "<需要解决的问题>"+question+"</需要解决的问题>")

    json_start = response.find('```json')
    json_end = response.find('```', json_start + 7)

    if json_start != -1 and json_end != -1:
        json_str = response[json_start + 7:json_end].strip()
        response_json = json.loads(json_str)
    else:
        # Try to parse the whole response
        response_json = json.loads(response)

    # Extract the reasoning process
    reasoning_process = response_json.get("思考过程", "")
    # Extract all law articles (not just 3)
    queries = []
    for key, value in response_json.items():
        if key.startswith("法条") and value:
            queries.append(value)
    if not queries:
        queries = [question]
    # print("思考过程:", reasoning_process)
    # print("检索法条:", queries)
    reasoning_process = {'找出相关法条': reasoning_process}
    return reasoning_process, queries

# retrieve: use queries to retrieve law articles
# input: queries
# output: law articles


def retrieve(queries):
    # API 服务的地址（确保 Flask 或 FastAPI 服务已在 localhost 上运行）
    api_url = "http://localhost:5000/retrieve"

    # 请求体，包含查询文本和返回结果的数量
    data = {
        "queries": queries,
        "top_k": 1
    }

    # 发送 POST 请求到 API
    response = requests.post(api_url, json=data)

    # 解析返回的 JSON 响应
    if response.status_code == 200:
        result = response.json()
        # print("Retrieved articles:")
        # print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print(f"Error: {response.status_code}")
        # print(response.text)

    formatted_result = [
        # Access first item in sublist -> "document" -> "contents"
        entry[0]["document"]["contents"]
        # Iterate through each entry in "result" list
        for entry in result["result"]
    ]
    # Return the formatted list of law article contents
    # print("Formatted result:")
    # print(json.dumps(formatted_result, indent=4, ensure_ascii=False))
    # 去重
    formatted_result = list(set(formatted_result))
    return formatted_result

# judge whether the law articles are applicable, and give the reason, and give answer
# input: law articles, question
# output: reasoning process, filtered law articles, answer


def judge_and_answer(result, question=test_question):
    # 将检索到的法条转换为字符串格式
    result_str = json.dumps(result, ensure_ascii=False)

    # judge_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
    # 你会看到一些相关的法条，排除对你没有帮助的法条，只参考你认为对你分析这道题有帮助的法条。你需要在“思考过程”中说明为什么参考或者不参考某条法条。 \
    # 你需要对每一个选项，详细地解释，联系题目，进行相应的分析。然后在“参考法条”中准确地给出你参考的法条内容你需要在回答的最后根据你对题目和每一个选项的分析，给出你的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。'
    sys_prompt = '你是一名法学专家。'
    judge_answer_prompt = '我会给你一道司法考试的不定项选择题（由<问题></问题>标签包裹）和一些由<法条></法条>标签包裹的参考法条，这些法条中有的有用有的无用。你需要在输出中的"分析法条过程"中一个个地分析<法条></法条>中的每条法条，说明为什么每条法条对于解决这道题有用或无用。请你排除对你没有帮助的法条，只给出你认为对你解答这道题有帮助的法条。在“有用的法条”中准确地给出且只给出你认为有用的法条内容。然后再在"解题思考过程"中联系“有用的法条”分析题目，在"最终答案"中给出最终答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。'

    answer_format_prompt = """你的输出格式必须严格按照以下的json输出格式,\
    ```json
    {{
        "分析法条过程": "...",
        "有用的法条": {{
            "法条1": "《xx法》第xxx条：xxx",
            "法条2": "《xx法》第xxx条：xxx",
            ...
        }},
        "解题思考过程": "...",
        "最终答案": "...",
    }}
    ```
    """

    response = get_response(modelr1, sys_prompt, judge_answer_prompt + answer_format_prompt + 
                            "<问题>"+question+"</问题>"+"<法条>"+result_str+"</法条>")

    json_start = response.find('```json')
    json_end = response.find('```', json_start + 7)

    if json_start != -1 and json_end != -1:
        json_str = response[json_start + 7:json_end].strip()
        response_json = json.loads(json_str)
    else:
        # Try to parse the whole response
        response_json = json.loads(response)

    # Extract the reasoning process
    # reasoning_process = response_json.get("思考过程", "")
    reasoning_process = {k:v for k,v in response_json.items() if k!='最终答案'}
    # Extract all law articles (not just 3)
    # queries = response_json.get("参考法条", {})
    # Extract the final answer
    answer = response_json.get("最终答案", "")
    # print("思考过程:", reasoning_process)
    # print("参考法条:", queries)
    # print("最终答案:", answer)
    return reasoning_process, answer

# verify if the answer match the ground truth


def verify_answer(answer, ground_truth='D'):
    # Match one or more capital letters A-D
    answer_pattern = re.compile(r'[A-D]+')
    match = answer_pattern.search(answer)
    if match:
        answer = match.group(0)  # Get the matched letter(s)
    if answer == ground_truth:
        print("答案正确")
        return True
    else:
        print("答案错误")
        return False

# revise: analyze law wrong or reasoning wrong, law wrong get new law
# then continue reasoning based on all previous thing
# then goto verify
# input: previous thing, question


def revise(previous_all, question=test_question):
    sys_prompt = '你是一名法学专家。'
    revise_prompt = """请你解答一道司法考试的不定项选择题。
        下面是你之前的回答，你的最终答案是不正确的。不要重复你之前的错误。
        你需要根据你之前的回答，重新分析，判断你之前使用的法条（# 有用的法条）是否正确且足够支撑你的分析。如果正确，
        如果你认为不需要新的法条，在"参考法条"中再次给出这些正确的法条，并在你之前的推理基础上继续思考，给出新的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。
        如果你认为需要新的法条，给出新的法条（不包括司法解释）。"""

    revise_format_prompt = """你的输出格式必须严格按照以下的两种json输出格式之一\
    如果你认为不需要新的法条：```json
    {{
        "分析之前的法条": "...",
        "参考法条": {{
            "法条1": "《xx法》第xxx条（xxx为中文数字）：xxx",
            "法条2": "《xx法》第xxx条：xxx",
            ...
        }},
        "继续思考": "...",
        "最终答案": "...",
    }}
    ```
    如果你认为需要新的法条：```json
    {{
        "分析之前的法条": "...",
        "法条1": "《中华人民共和国民法典》第xxx条：xxx",
        "法条2": "《中华人民共和国刑法》第xxx条：xxx",
        ...
    }}
    ```
    """
    response = get_response(modelr1, sys_prompt, revise_prompt + revise_format_prompt + 
                            "<问题>"+question+"</问题>\n"
                            + "<之前的回答>"+previous_all+"</之前的回答>")
    # print("修正后的回答:", response)

    json_start = response.find('```json')
    json_end = response.find('```', json_start + 7)

    if json_start != -1 and json_end != -1:
        json_str = response[json_start + 7:json_end].strip()
        response_json = json.loads(json_str)
    else:
        # Try to parse the whole response
        response_json = json.loads(response)


    # 解析返回的 JSON 响应
    if '"最终答案":' in response:
        reasoning_process = {k:v for k,v in response_json.items() if k!='最终答案'}
        answer = response_json.get("最终答案", "")
        # print("思考过程:", reasoning_process)
        # print("查询请求:", last_query)
        # print("检索法条:", last_result)
        # print("筛选思考:", last_judge_thinking)
        # print("筛选法条:", last_filtered_law)
        # print("最终答案:", answer)
        newCOT = '<think>'+json.dumps(reasoning_process, ensure_ascii=False) + '</think>'+'\n' + \
            '<answer>' + answer+'</answer>'
        return newCOT, answer
    else:
        # 重新检索法条
        reasoning_process = response_json.get("分析之前的法条", "")
        # Extract all law articles (not just 3)
        queries = []
        for key, value in response_json.items():
            if key.startswith("法条") and value:
                queries.append(value)
        if not queries:
            queries = [question]

        result = retrieve(queries)
        judge_thinking, answer = judge_and_answer(
            result, question)
        # print("思考过程:", reasoning_process)
        # print("查询请求:", queries)
        # print("检索法条:", result)
        # print("筛选思考:", judge_thinking)
        # print("筛选法条:", filtered_law)
        # print("最终答案:", answer)
        newCOT = '<think>'+reasoning_process + '</think>'+'\n' + \
            '<search>'+json.dumps(queries, ensure_ascii=False) + '</search>'+'\n' +\
            '<information>' + json.dumps(result, ensure_ascii=False) + '</information>'+'\n' +\
            '<think>' + judge_thinking + '</think>'+'\n' +\
            '<answer>' + answer+'</answer>'
        return newCOT, answer


def save_answer(previous_all, ground_truth):
    # 用deepseek r1模型整合COT，保存答案
    sys_prompt = '你是一名法学专家。'
    save_answer_prompt = '下面是你之前的回答，你的最终答案是正确的。请确保你本次推理出的答案与之前的一致。\
        你需要根据你之前的回答，进行分析，整理你的思维过程，合并为如下格式的连贯回答。\
        '
    save_answer_format_prompt = """你的输出格式必须严格按照以下的json输出格式\
    <think>reasoning</think>
    <search>this is a query</search>
    <information>法条1,2,3。。。</information>
    <think>reasoning</think>
    <search>this is a query</search>
    <information>法条1,2,3。。。</information>
    ...
    <answer>BC<answer>"""

    response = get_response(modelv3, sys_prompt+save_answer_prompt, save_answer_format_prompt+\
                            "<之前的推理>"+json.dumps(previous_all, ensure_ascii=False)+"</之前的推理>"+"<正确答案>"+ground_truth+"</正确答案>")
    print("保存的答案:", response)
    return response


if __name__ == "__main__":
    # Read questions and answers from JSON file
    data_file_path = "data/demo.json"

    try:
        with open(data_file_path, "r", encoding="utf-8") as f:
            questions = json.load(f)
        print(
            f"Successfully loaded {len(questions)} questions from {data_file_path}")
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        questions = []

    # Create a list to store all results
    all_results = []

    # Process each question from the JSON file
    for item in questions:
        question_id = item.get("id", "unknown")
        statement = item["statement"]
        options = item["option_list"]
        # This is a list like ["D"] or ["A", "B", "C", "D"]
        ground_truth = item["answer"]

        # Format question with options
        formatted_question = statement + '\n'
        for key, value in options.items():
            formatted_question += f'{key}: {value}\n'

        print(f"\n\nProcessing question ID: {question_id}")
        print(f"Question: {formatted_question}")
        print(f"Ground truth: {ground_truth}")

        # Run the pipeline
        thinking1, queries = init_query(formatted_question)
        result = retrieve(queries)
        thinking2, answer = judge_and_answer(
            result, formatted_question)

        def json_to_string(json_obj):
            ret = ''
            for k, v in json_obj.items():
                ret+=f'# {k}: {v}\n'
            return ret

        thinking1 = json_to_string(thinking1)
        thinking2 = json_to_string(thinking2)
        # Verify answer against ground truth
        # Convert list to sorted string
        ground_truth_str = ''.join(sorted(ground_truth))
        flag = verify_answer(answer, ground_truth_str)
        previous_all = '<think>'+thinking1 + '</think>'+'\n' + \
            '<search>'+json.dumps(queries, ensure_ascii=False) + '</search>'+'\n' +\
            '<information>' + json.dumps(result, ensure_ascii=False) + '</information>'+'\n' +\
            '<think>' + thinking2 + '</think>'+'\n' +\
            '<answer>' + answer+'</answer>'

        # Try to improve if needed
        max_iterations = 3
        for i in range(max_iterations):
            print(f"Iteration {i+1}")
            if flag:
                print("COT:", previous_all)
                # Answer is correct, save it
                final_response = save_answer(previous_all, ground_truth_str)

                # Add to results list instead of saving individually
                all_results.append({
                    "question_id": question_id,
                    "question": statement,
                    "options": options,
                    "ground_truth": ground_truth,
                    "COT": previous_all,
                    "revised_COT": final_response,
                    "success": True
                })

                break
            else:
                # Revise the answer
                newCOT, answer = revise(previous_all, formatted_question)
                previous_all += '\n' + newCOT
                flag = verify_answer(answer, ground_truth_str)

            # If we've reached max iterations and still incorrect
            if i == max_iterations - 1 and not flag:
                print(
                    f"Failed to get correct answer for question {question_id} after {max_iterations} iterations")
                print("COT:", previous_all)
                # Add the best result we have so far
                all_results.append({
                    "question_id": question_id,
                    "question": statement,
                    "options": options,
                    "ground_truth": ground_truth,
                    "COT": previous_all,
                    "revised_COT": None,
                    "success": False
                })

    # Save all results to a single JSON file
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "all_results.json")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"All results saved to {output_file}")
    except Exception as e:
        print(f"Error saving results: {e}")
