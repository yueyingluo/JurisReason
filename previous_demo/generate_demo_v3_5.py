# v3 update
# 2025.4.29
# 1.取消query条数限制
# 2.把question放进judge_and_answer函数中
# 3.revise说清楚哪里是之前的推理，哪里是question（把所有prompt都<>按需标出了<需要解决的问题>/<可以参考的法条>/<之前的回答>）
# 4.批量处理输入输出(line 396) data from data/demo.json; saved to output/all_results.json

# 整体逻辑：
# 1. init_query：输入question，输出法条作为多个query
# 2. retrieve：输入多个query，输出result（检索出的法条）（json）
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
        ...
    }}
    ```"""

    response = get_response(modelv3, ini_prompt + format_request, "<需要解决的问题>"+question+"</需要解决的问题>" )
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
        
        # Extract all law articles (not just 3)
        queries = []
        for key, value in response_json.items():
            if key.startswith("法条") and value:
                queries.append(value)
        
    except Exception as e:
        print(f"Error parsing JSON response: {e}. Retrying...")
        # Retry with the same prompt
        response = get_response(modelv3, ini_prompt + format_request, "<需要解决的问题>"+question+"</需要解决的问题>" )
        try:
            json_start = response.find('```json')
            json_end = response.find('```', json_start + 7)
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start + 7:json_end].strip()
                response_json = json.loads(json_str)
            else:
                response_json = json.loads(response)
            
            # Extract all law articles
            queries = []
            for key, value in response_json.items():
                if key.startswith("法条") and value:
                    queries.append(value)
                    
        except Exception as e:
            print(f"Failed to parse JSON response again: {e}. Using question as query.")
            queries = [question]
            
    # If no valid queries were found, use the question
    if not queries:
        queries = [question]
            
    return queries

import requests
import json
import re

def retrieve(queries):
    # API 服务的地址（确保 Flask 或 FastAPI 服务已在 localhost 上运行）
    api_url = "http://localhost:5000/retrieve"

    # 请求体，包含查询文本和返回结果的数量
    data = {
        "queries": queries,
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

def judge_and_answer(result, question=test_question):
    # 将检索到的法条转换为字符串格式
    result_str = json.dumps(result, ensure_ascii=False)

    judge_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。请你阅读一道司法考试题目和它的选项，充分发挥你的能力，认真阅读每一个选项，有逻辑地思考。\
    你会看到一些相关的法条，排除对你没有帮助的法条，只参考你认为对你分析这道题有帮助的法条。你需要在“思考过程”中说明为什么参考或者不参考某条法条。 \
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

    response = get_response(modelv3, judge_answer_prompt + answer_format_prompt, "<需要解决的问题>"+question+"</需要解决的问题>"+"<可以参考的法条>"+result_str+"</可以参考的法条>" )
    
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
        下面是你之前的回答，你的最终答案是不正确的。不要重复你之前的错误。\
        你需要根据你之前的回答，重新分析，判断你之前使用的法条是否正确且足够支撑你的分析。\
        如果你认为不需要检索新的法条，在你之前的推理基础上继续思考，给出新的答案。你需要在回答的最后根据你对题目和每一个选项的分析，给出你的答案。注意：这是不定项选择题，你的最终答案必须是大写字母的组合。\
        如果你认为需要检索新的法条，给出新的检索问题。\
        '
    
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
    response = get_response(modelr1, revise_prompt + revise_format_prompt, \
        "<需要解决的问题>"+question+"</需要解决的问题>" \
        + "之前的回答"+json.dumps(response, ensure_ascii=False)+"</之前的回答>" )
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
        
            # Extract all law articles
            queries = []
            for key, value in response_json.items():
                if key.startswith("法条") and value:
                    queries.append(value)
                
        except Exception as e:
            print(f"Error parsing JSON response: {e}. Retrying...")
            # Retry with the same prompt
            response = get_response(modelr1, revise_prompt + revise_format_prompt, \
                "<需要解决的问题>"+question+"</需要解决的问题>" \
                + "之前的回答"+json.dumps(response, ensure_ascii=False)+"</之前的回答>" )
            try:
                json_start = response.find('```json')
                json_end = response.find('```', json_start + 7)
            
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start + 7:json_end].strip()
                    response_json = json.loads(json_str)
                else:
                    response_json = json.loads(response)
            
                queries = []
                for key, value in response_json.items():
                    if key.startswith("法条") and value:
                        queries.append(value)
            except Exception as e:
                print(f"Failed to parse JSON response again: {e}. Using question as query.")
                queries = [question]

        # If no valid queries were found, use the question
        if not queries:
            queries = [question]
            
        result = retrieve(queries)
        response = judge_and_answer(result)
        return result, response

def save_answer(result, response, question=test_question):
    # 用deepseek r1模型整合COT，保存答案
    save_answer_prompt='你是一名法学专家。你非常擅长阅读法律案例，并判断有关这个案例的表述是否正确。\
        下面是你之前的回答，你的最终答案是正确的。请确保你本次推理出的答案与之前的一致。\
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
    # save_answer_format_prompt="""你的输出格式必须严格按照以下的json输出格式\
    # ```json
    # {{
    #     "思考过程": "...",
    #     “参考法条": {{
    #         "法条1": "《xx法》第xxx条：xxx",
    #         "法条2": "《xx法》第xxx条：xxx",
    #         ...
    #     }},
    #     "最终答案": "...",
    # }}
    # ```"""

    response = get_response(modelr1, save_answer_prompt + save_answer_format_prompt, \
        "<需要解决的问题>"+question+"</需要解决的问题>"+ "<参考的法条>"+json.dumps(result, ensure_ascii=False)+"</参考的法条>" + "<之前的回答>"+json.dumps(response, ensure_ascii=False)+"</之前的回答>" )
    print("保存的答案:", response)
    return response
 

if __name__ == "__main__":
    # Read questions and answers from JSON file
    data_file_path = "data/demo.json"
    
    try:
        with open(data_file_path, "r", encoding="utf-8") as f:
            questions = json.load(f)
        print(f"Successfully loaded {len(questions)} questions from {data_file_path}")
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        questions = []
    
    # Create a list to store all results
    all_results = []
    
    # Process each question or use test question if no questions loaded
    if not questions:
        print("Using test question...")
        queries = init_query()
        result = retrieve(queries)
        response = judge_and_answer(result)
        
        # Verify answer
        max_iterations = 3
        flag = verify_answer(response)
        
        for i in range(max_iterations):
            print(f"Iteration {i+1}")
            if flag:
                final_response = save_answer(result, response)
                all_results.append({
                    "question_id": "test",
                    "question": test_question,
                    "ground_truth": "D",
                    "result": final_response
                })
                break
            else:
                result, response = revise(result, response)
                flag = verify_answer(response)
    else:
        # Process each question from the JSON file
        for item in questions:
            question_id = item.get("id", "unknown")
            statement = item["statement"]
            options = item["option_list"]
            ground_truth = item["answer"]  # This is a list like ["D"] or ["A", "B", "C", "D"]
            
            # Format question with options
            formatted_question = statement + '\n'
            for key, value in options.items():
                formatted_question += f'{key}: {value}\n'
                
            print(f"\n\nProcessing question ID: {question_id}")
            print(f"Question: {formatted_question}")
            print(f"Ground truth: {ground_truth}")
            
            # Run the pipeline
            queries = init_query(formatted_question)
            result = retrieve(queries)
            response = judge_and_answer(result, formatted_question)
            
            # Verify answer against ground truth
            ground_truth_str = ''.join(sorted(ground_truth))  # Convert list to sorted string
            flag = verify_answer(response, ground_truth_str)
            
            # Try to improve if needed
            max_iterations = 3
            for i in range(max_iterations):
                print(f"Iteration {i+1}")
                if flag:
                    # Answer is correct, save it
                    final_response = save_answer(result, response, formatted_question)
                    
                    # Add to results list instead of saving individually
                    all_results.append({
                        "question_id": question_id,
                        "question": statement,
                        "options": options,
                        "ground_truth": ground_truth,
                        "result": final_response,
                        "success": True
                    })
                    
                    break
                else:
                    # Revise the answer
                    result, response = revise(result, response, formatted_question)
                    flag = verify_answer(response, ground_truth_str)
                    
                # If we've reached max iterations and still incorrect
                if i == max_iterations - 1 and not flag:
                    print(f"Failed to get correct answer for question {question_id} after {max_iterations} iterations")
                    # Add the best result we have so far
                    all_results.append({
                        "question_id": question_id,
                        "question": statement,
                        "options": options,
                        "ground_truth": ground_truth,
                        "result": response,
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