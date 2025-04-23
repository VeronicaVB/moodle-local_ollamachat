import requests
import sys
import json
from urllib.parse import urlparse
from difflib import SequenceMatcher
from functools import lru_cache

"""
This script is more robust than the original, as it filters the words first to only include elements items
that are relevant.
"""
# Encoding configuration for output
sys.stdout.reconfigure(encoding='utf-8')

def calculate_relevance(text, prompt):
    """Calculate relevance score between text and prompt"""
    return SequenceMatcher(None, text.lower(), prompt.lower()).ratio()

def clean_text(text):
    """Cleans text by removing problematic characters"""
    return (text.replace('\r', ' ')
            .replace('\n', ' ')
            .replace('\t', ' ')
            .strip())


def filter_items_by_keywords(items, keywords):
    """
    Filters articles by matching keywords in the title, content, and keywords fields.
    Only articles containing at least one keyword from the query in any of these three fields are retained.
    """
    filtered_items = []
    for item in items:
        title = item.get('title', '').lower()
        content = item.get('content', '').lower()
        item_keywords = item.get('keywords', '').lower()

        # Check if any keyword appears in the title, content, or keywords
        if any(keyword.lower() in title or keyword.lower() in content or keyword.lower() in item_keywords for keyword in keywords):
            filtered_items.append(item)

    return filtered_items

def process_knowledge(items, prompt):
    """Processes articles with relevance scores after filtering by relevant keywords in title, content, and keywords"""
    scored_items = []

    keywords = prompt.split()

    # Filtrar artículos por palabras clave en título, contenido y keywords antes de calcular la relevancia
    filtered_items = filter_items_by_keywords(items, keywords)

    for item in filtered_items:
        title = clean_text(item.get('title', ''))
        url = item.get('url', '')
        content = clean_text(item.get('content', ''))
        keywords = clean_text(item.get('keywords', ''))

        # Calcular puntuaciones de relevancia para los diferentes componentes
        title_score = calculate_relevance(title, prompt) * 1.5
        content_score = calculate_relevance(content, prompt) * 1.2
        keyword_score = calculate_relevance(keywords, prompt) * 1.3
        url_score = calculate_relevance(url, prompt)

        # Puntuación total combinada
        total_score = (title_score + content_score + keyword_score + url_score) / 5

        if total_score > 0.2:
            scored_items.append({
                'title': title,
                'url': url,
                'content': content[:2000],
                'keywords': keywords,
                'score': total_score
            })

    # Ordenar por la puntuación de relevancia
    scored_items.sort(key=lambda x: x['score'], reverse=True)

    # Preparar el contexto y recolectar fuentes
    context = []
    sources = []
    for item in scored_items[:3]:  # Limitar a los 3 más relevantes
        entry = (
            f"### {item['title']}\n"
            f"Content: {item['content'][:800]}...\n"
        )
        context.append(entry)
        sources.append(item['url'])

    return "\n".join(context), sources


@lru_cache(maxsize=500)
def fetch_knowledge_cached(url):
    """Cached version of knowledge fetching"""
    try:
        if not urlparse(url).scheme:
            return []

        response = requests.get(
            url,
            timeout=10,  # Reduced from 15 to 10 seconds
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
    """Enhances the response with source information and ensures proper explanation"""
    # Check if response already has substantial content
    if len(response_text.strip()) < 100 and sources:  # If response is too short but we have sources
        # Extract comprehensive content from knowledge
        knowledge_content = ""
        if knowledge:
            # Extract all relevant information from the knowledge sections
            sections = knowledge.split('###')[1:] if '###' in knowledge else []
            for section in sections:
                if section.strip():
                    parts = section.split('\n', 1)
                    if len(parts) > 1:
                        content = parts[1].strip()
                        if "Content:" in content:
                            content = content.split("Content:")[1].strip()
                        knowledge_content += content + " "

        # Use the combined knowledge to create a more comprehensive response
        if knowledge_content:
            # Replace brief response with a more comprehensive one
            topics = [src.split('/')[-1].replace('-', ' ').title() for src in sources if '/' in src]
            topic_text = ", ".join(topics) if topics else "your question"

            response_text = (
                f"Here's a comprehensive explanation about {topic_text}:\n\n" +
                knowledge_content.strip() + "\n\n" +
                "This information should help you complete the task effectively."
            )

    # Add sources with proper context
    if sources and not any(src in response_text for src in sources):
        source_intro = "\n\nFor more detailed information, you can refer to these resources:"
        return response_text + source_intro + "\n" + "\n".join([f" {url}" for url in sources[:3]])

    return response_text

def generate_response(prompt, knowledge_url=None):
    """Generates response using Ollama with enhanced knowledge integration"""
    try:
        # 1. Get and process knowledge
        knowledge = ""
        sources = []

        if knowledge_url:
            data = fetch_knowledge_cached(knowledge_url)
            if data:
                knowledge, sources = process_knowledge(data, prompt)

        # 2. Enhanced prompt
        full_prompt = (
            "You are a knowledgeable school assistant that ONLY uses the provided context from the knowledge base to answer the user's question.\n"
            "Instructions:\n"
            "1. First, carefully analyze the user's question to understand what task they need help with.\n"
            "2. Search ONLY the CONTEXT provided below (titles, URLs, and content) to find relevant information.\n"
            "3. If you find relevant information in the CONTEXT, use it to answer the user's question.\n"
            "4. If the context does not provide sufficient information to answer the user's question, you must respond by saying that you can only provide information from the knowledge base.\n"
            "5. Do not add any general knowledge or information that is not present in the CONTEXT.\n"
            "6. If multiple context sources (titles, URLs, or content) provide useful information, COMBINE them into one coherent answer.\n"
            "7. Always respond in the same language as the user's question.\n\n"
            f"CONTEXT:\n{knowledge if knowledge else 'No additional context available.'}\n\n"
            f"USER QUESTION: {prompt}\n\n"
            "Please provide a clear and coherent answer based strictly on the context above. If the information is not available, clearly state that your answer is based solely on the knowledge in the provided context."
        )


        # 3. Query Ollama with optimized parameters (unchanged)
        ollama_response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi3:3.8b-instruct",  # Faster model
                "prompt": full_prompt,
                "stream": True,
                "options": { # https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values
                    "temperature": 0.5,  # The temperature of the model. Increasing the temperature will make the model answer more creatively
                    "num_ctx": 2048,     # Sets the size of the context window used to generate the next token.
                    "top_k": 20,         # Reduces the probability of generating nonsense. A higher value (e.g. 100) will give more diverse answers, while a lower value (e.g. 10) will be more conservative. (Default: 40)
                    "repeat_penalty": 1.2, #Sets how strongly to penalize repetitions. A higher value (e.g., 1.5) will penalize repetitions more strongly, while a lower value (e.g., 0.9) will be more lenient. (Default: 1.1)
                    "num_threads": 8,    # Optimized for laptop
                    "stop": ["\n", "###"] # Sets the stop sequences to use. When this pattern is encountered the LLM will stop generating text and return. Multiple stop patterns may be set by specifying multiple separate stop parameters in a modelfile.
                }
            },
            timeout=300
        )

        response_data = ollama_response.json()
        response_text = response_data.get("response", "")

        # 4. Enhance response with synthesized content and sources
        response_text = format_response_with_sources(response_text, knowledge, sources)

        return {
            "success": True,
            "response": response_text,
            "sources": sources,
            "context_used": bool(knowledge.strip())
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "response": "I'm having trouble accessing our knowledge base. Please try again later.",
            "sources": []
        }
    except Exception as e:
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
                "response": "Please provide your question as an argument",
                "sources": []
            }))
            sys.exit(1)

        prompt = sys.argv[1]
        knowledge_url = sys.argv[2] if len(sys.argv) > 2 else None

        result = generate_response(prompt, knowledge_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(json.dumps({
            "success": False,
            "response": "We're experiencing technical difficulties. Please try again later.",
            "sources": []
        }, ensure_ascii=False))