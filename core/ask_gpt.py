import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from threading import Lock
import json_repair
import json 
from openai import OpenAI
import time
from requests.exceptions import RequestException
from core.config_utils import load_key
from typing import Union, Dict

LOG_FOLDER = 'output/gpt_log'
LOCK = Lock()

def save_log(model, prompt, response, log_title = 'default', message = None):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    log_data = {
        "model": model,
        "prompt": prompt,
        "response": response,
        "message": message
    }
    log_file = os.path.join(LOG_FOLDER, f"{log_title}.json")
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    else:
        logs = []
    logs.append(log_data)
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)
        
def check_ask_gpt_history(prompt, model, log_title):
    # check if the prompt has been asked before
    if not os.path.exists(LOG_FOLDER):
        return False
    file_path = os.path.join(LOG_FOLDER, f"{log_title}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item["prompt"] == prompt and item["model"] == model:
                    return item["response"]
    return False

def ask_gpt(prompt: str, response_json: bool = False, valid_def=None, log_title: str = None) -> Union[str, Dict]:
    # 检查历史记录
    history_response = check_ask_gpt_history(prompt, load_key("api.model"), log_title)
    if history_response:
        return history_response

    # 设置环境变量跳过代理
    os.environ['no_proxy'] = '*'
    
    # 打印详细的 API 设置
    print("\n[blue]Using API settings:[/blue]")
    print(f"base_url: {load_key('api.base_url')}")
    print(f"model: {load_key('api.model')}")
    print(f"key: {load_key('api.key')[:8]}...")  # 只显示 key 的前几位
    
    try:
        client = OpenAI(
            api_key=load_key("api.key"),
            base_url=load_key("api.base_url"),
            timeout=120.0,
            max_retries=5
        )
        
        # 测试连接
        print(f"\n[yellow]Testing connection to {load_key('api.base_url')}...[/yellow]")
        
        max_retries = 5
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=load_key("api.model"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    timeout=120.0
                )
                
                result = response.choices[0].message.content
                print("[green]✓ API connection successful[/green]")
                
                # 保存成功的响应到历史记录
                if log_title:
                    save_log(load_key("api.model"), prompt, result, log_title)
                
                if response_json:
                    try:
                        response_data = json_repair.loads(result)
                        if valid_def:
                            valid_response = valid_def(response_data)
                            if valid_response['status'] != 'success':
                                save_log(load_key("api.model"), prompt, response_data, log_title="error", message=valid_response['message'])
                                raise ValueError(f"❎ API response error: {valid_response['message']}")
                        return response_data
                    except Exception as e:
                        print(f"❎ json_repair parsing failed. Retrying: '''{result}'''")
                        save_log(load_key("api.model"), prompt, result, log_title="error", message=f"json_repair parsing failed.")
                        raise
                
                return result
                
            except Exception as e:
                print(f"[red]Attempt {attempt + 1} failed: {str(e)}[/red]")
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    print(f"[yellow]Retrying in {delay} seconds...[/yellow]")
                    time.sleep(delay)
                    continue
                raise
                
    except Exception as e:
        print(f"[red]Failed to initialize OpenAI client: {str(e)}[/red]")
        raise


if __name__ == '__main__':
    print(ask_gpt('hi there hey response in json format, just return 200.' , response_json=True, log_title=None))