"""
This script is a similar version to the original but using anothr model and options
"""
import requests
import sys
import json
from urllib.parse import urlparse
from difflib import SequenceMatcher
from functools import lru_cache

sys.stdout.reconfigure(encoding='utf-8')

def calculate_relevance(text, prompt):
    return SequenceMatcher(None, text.lower(), prompt.lower()).ratio()

def clean_text(text):
    return (text.replace('\r', ' ')
                .replace('\n', ' ')
                .replace('\t', ' ')
                .strip())

def process_knowledge(items, prompt):
    scored_items = []
    for item in items:
        title = clean_text(item.get('title', ''))
        url = item.get('url', '')
        content = clean_text(item.get('content', ''))
        keywords = clean_text(item.get('keywords', ''))

        title_score = calculate_relevance(title, prompt) * 1.5
        content_score = calculate_relevance(content, prompt) * 1.2
        keyword_score = calculate_relevance(keywords, prompt) * 1.3
        url_score = calculate_relevance(url, prompt)

        total_score = (title_score + content_score + keyword_score + url_score) / 4

        if total_score > 0.2:
            scored_items.append({
                'title': title,
                'url': url,
                'content': content[:800],
                'keywords': keywords,
                'score': total_score
            })

    scored_items.sort(key=lambda x: x['score'], reverse=True)

    context = []
    sources = []
    for item in scored_items[:3]:
        entry = (
            f"### {item['title']}\n"
            f"Content: {item['content'][:400]}...\n"
        )
        context.append(entry)
        sources.append(item['url'])

    return "\n".join(context), sources

@lru_cache(maxsize=500)
def fetch_knowledge_cached(url):
    try:
        if not urlparse(url).scheme:
            return []
        response = requests.get(
            url,
            timeout=10,
            headers={
                'Accept': 'application/json; charset=utf-8',
                'User-Agent': 'Mozilla/5.0'
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results', []) if isinstance(data, dict) else data if isinstance(data, list) else []
    except Exception as e:
        print(f"Knowledge API Error: {str(e)}", file=sys.stderr)
        return []

def format_response_with_sources(response_text, knowledge, sources):
    if not sources:
        return response_text
    if any(src in response_text for src in sources):
        return response_text
    source_intro = "\n\nSources consulted:"
    return response_text + source_intro + "\n" + "\n".join([f"{url}" for url in sources[:3]])

def generate_response(prompt, knowledge_url=None):
    try:
        knowledge = ""
        sources = []
        if knowledge_url:
            data = fetch_knowledge_cached(knowledge_url)
            if data:
                knowledge, sources = process_knowledge(data, prompt)

        full_prompt = (
            "You are a helpful and knowledgeable assistant for a school platform. You have access to a knowledge base with useful guides.\n"
            "Your task is:\n"
            "1. Carefully read the user's question.\n"
            "2. Review the CONTEXT which may contain detailed instructions.\n"
            "3. If any steps or relevant guidance exist in the context, explain them clearly, step by step.\n"
            "4. If partial information is found, supplement it with your general knowledge.\n"
            "5. Always respond in the same language as the user’s question.\n"
            "6. At the end, list any source URLs you used.\n\n"
            f"CONTEXT:\n{knowledge if knowledge else 'No additional context available.'}\n\n"
            f"USER QUESTION: {prompt}\n\n"
            "Please provide a clear, step-by-step explanation that helps the user accomplish their task:"
        )

        ollama_response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral:7b-instruct",
                "prompt": full_prompt,
                "stream": False,
                "options": {# https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values
                    "temperature": 0.5,
                    "num_ctx": 2048,
                    "top_k": 20,
                    "repeat_penalty": 1.2,
                    "num_threads": 8,
                    "stop": ["###"]  # Ensure we capture all the response
                }
            },
            timeout=3060  # Timeout increased to avoid timeouts
        )

        response_data = ollama_response.json()
        response_text = response_data.get("response", "")
        response_text = format_response_with_sources(response_text, knowledge, sources)

        return {
            "success": True,
            "response": response_text,
            "sources": sources,
            "context_used": bool(knowledge.strip())
        }

    except requests.exceptions.RequestException:
        return {
            "success": False,
            "response": "I'm having trouble accessing the knowledge base. Please try again later.",
            "sources": []
        }
    except Exception:
        return {
            "success": False,
            "response": "An unexpected error occurred. Please try again or contact support.",
            "sources": []
        }

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print(json.dumps({
                "success": False,
                "response": "Please provide your question as an argument.",
                "sources": []
            }))
            sys.exit(1)

        prompt = sys.argv[1]
        knowledge_url = sys.argv[2] if len(sys.argv) > 2 else None

        result = generate_response(prompt, knowledge_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception:
        print(json.dumps({
            "success": False,
            "response": "We're experiencing technical difficulties. Please try again later.",
            "sources": []
        }, ensure_ascii=False))
