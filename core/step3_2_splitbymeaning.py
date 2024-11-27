import sys,os,math
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import concurrent.futures
from core.ask_gpt import ask_gpt
from core.prompts_storage import get_split_prompt
from difflib import SequenceMatcher
import math
from core.spacy_utils.load_nlp_model import init_nlp
from core.config_utils import load_key, get_joiner
from rich.console import Console
from rich.table import Table
import time

console = Console()

def tokenize_sentence(sentence, nlp):
    # tokenizer counts the number of words in the sentence
    doc = nlp(sentence)
    return [token.text for token in doc]

def find_split_positions(original, modified):
    split_positions = []
    parts = modified.split('[br]')
    start = 0
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language
    joiner = get_joiner(language)

    for i in range(len(parts) - 1):
        max_similarity = 0
        best_split = None

        for j in range(start, len(original)):
            original_left = original[start:j]
            modified_left = joiner.join(parts[i].split())

            left_similarity = SequenceMatcher(None, original_left, modified_left).ratio()

            if left_similarity > max_similarity:
                max_similarity = left_similarity
                best_split = j

        if max_similarity < 0.9:
            console.print(f"[yellow]Warning: low similarity found at the best split point: {max_similarity}[/yellow]")
        if best_split is not None:
            split_positions.append(best_split)
            start = best_split
        else:
            console.print(f"[yellow]Warning: Unable to find a suitable split point for the {i+1}th part.[/yellow]")

    return split_positions

def split_sentence(sentence: str, max_length: int, nlp, retry_attempt: int = 0) -> dict:
    """使用 LLM 分割句子"""
    if len(sentence) <= max_length:
        return {"original": sentence, "split": sentence}
        
    # 构建提示词
    prompt = f"""请将以下句子分成两部分，在最合适的位置用 || 分隔。确保分割后的句子语义完整且长度相近。
句子：{sentence}
要求：
1. 只能分成两部分
2. 只能用 || 分隔
3. 不要改变原文
4. 不要添加任何其他标点或空格
5. 直接返回分割后的句子，不要有任何其他内容

示例输入：This is a long sentence that needs to be split into two parts with similar lengths
示例输出：This is a long sentence || that needs to be split into two parts with similar lengths"""

    try:
        response = ask_gpt(prompt)
        # 确保响应中包含 ||
        if "||" not in response:
            raise ValueError("Response does not contain separator")
            
        # 直接使用响应文本，不需要解析 JSON
        return {
            "original": sentence,
            "split": response.strip()
        }
        
    except Exception as e:
        if retry_attempt < 2:  # 最多重试2次
            print(f"[red]Attempt {retry_attempt + 1} failed: {str(e)}[/red]")
            print(f"[yellow]Retrying in 3 seconds...[/yellow]")
            time.sleep(3)
            return split_sentence(sentence, max_length, nlp, retry_attempt + 1)
        else:
            # 如果重试失败，使用简单的长度分割
            mid = len(sentence) // 2
            return {
                "original": sentence,
                "split": f"{sentence[:mid]} || {sentence[mid:]}"
            }

def parallel_split_sentences(sentences: list, max_length: int, max_workers: int, nlp, retry_attempt: int = 0) -> list:
    """并行处理句子分割"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 移除 index 参数，只传入必要的参数
        futures = [
            executor.submit(
                split_sentence, 
                sentence, 
                max_length, 
                nlp, 
                retry_attempt
            ) for sentence in sentences
        ]
        
        results = []
        for future in futures:
            try:
                split_result = future.result()
                if "||" in split_result["split"]:
                    # 如果句子被分割了，添加两个部分
                    parts = split_result["split"].split("||")
                    results.extend([part.strip() for part in parts])
                else:
                    # 如果句子没有被分割，直接添加原句
                    results.append(split_result["split"].strip())
            except Exception as e:
                console.print(f"[red]Error processing sentence: {str(e)}[/red]")
                results.append(sentences[len(results)])  # 发生错误时使用原句
                
    return results

def split_sentences_by_meaning():
    """The main function to split sentences by meaning."""
    # read input sentences
    with open('output/log/sentence_splitbynlp.txt', 'r', encoding='utf-8') as f:
        sentences = [line.strip() for line in f.readlines()]

    nlp = init_nlp()
    # 🔄 process sentences multiple times to ensure all are split
    for retry_attempt in range(3):
        sentences = parallel_split_sentences(sentences, max_length=load_key("max_split_length"), max_workers=load_key("max_workers"), nlp=nlp, retry_attempt=retry_attempt)

    # 💾 save results
    with open('output/log/sentence_splitbymeaning.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sentences))
    console.print('[green]✅ All sentences have been successfully split![/green]')

if __name__ == '__main__':
    # print(split_sentence('Which makes no sense to the... average guy who always pushes the character creation slider all the way to the right.', 2, 22))
    split_sentences_by_meaning()