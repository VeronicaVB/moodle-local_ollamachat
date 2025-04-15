#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import sys
import json
from urllib.parse import urlparse
from difflib import SequenceMatcher
from functools import lru_cache

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

def process_knowledge(items, prompt):
    """Processes knowledge items with relevance scoring"""
    scored_items = []

    for item in items:
        # Extract all possible relevant fields
        title = clean_text(item.get('title', ''))
        url = item.get('url', '')
        content = clean_text(item.get('content', ''))
        keywords = clean_text(item.get('keywords', ''))

        # Calculate relevance scores for different components
        title_score = calculate_relevance(title, prompt) * 1.5
        content_score = calculate_relevance(content, prompt) * 1.2
        keyword_score = calculate_relevance(keywords, prompt) * 1.3
        url_score = calculate_relevance(url, prompt)

        # Combined weighted score
        total_score = (title_score + content_score + keyword_score + url_score) / 4

        if total_score > 0.2:
            scored_items.append({
                'title': title,
                'url': url,
                'content': content[:800],  # Reduced from 1000 to 800
                'keywords': keywords,
                'score': total_score
            })

    # Sort by relevance score
    scored_items.sort(key=lambda x: x['score'], reverse=True)

    # Prepare context and collect sources
    context = []
    sources = []
    for item in scored_items[:3]:  # Reduced from 5 to 3 most relevant
        entry = (
            f"### {item['title']}\n"
            f"Content: {item['content'][:400]}...\n"  # Reduced from 500 to 400
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
    """Enhances the response with source information"""
    if not sources:
        return response_text

    # Check if sources are already mentioned
    if any(src in response_text for src in sources):
        return response_text

    # Add sources with context
    source_intro = "\n\nFor more information, you can refer to:"
    if knowledge:
        first_title = knowledge.split('###')[1].split('\n')[0].strip() if '###' in knowledge else ""
        source_intro = f"\n\nBased on our resources about {first_title}, you can refer to:"

    return response_text + source_intro + "\n" + "\n".join([f" {url}" for url in sources[:3]])

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

        # 2. Your original full_prompt
        full_prompt = (
            "You are a knowledgeable assistant that integrates information from provided context with your own knowledge.\n"
            "Instructions:\n"
            "1. First carefully analyze the user's question to understand what information is being requested\n"
            "2. Thoroughly search through ALL provided context including titles, URLs, keywords, and content\n"
            "3. If relevant information exists in the context, you MUST use it and cite the source URLs\n"
            "4. If the context has partial information, use what's available and supplement with your knowledge\n"
            "5. Structure your response clearly with:\n"
            "   - Direct answer to the question\n"
            "   - Supporting evidence from context (when available)\n"
            "   - Additional helpful information\n"
            "6. Always respond in the same language as the question\n\n"
            f"CONTEXT:\n{knowledge if knowledge else 'No additional context was provided.'}\n\n"
            f"USER QUESTION: {prompt}\n\n"
            "Please provide a comprehensive response that directly addresses the user's question:"
        )

        # 3. Query Ollama with optimized parameters
        ollama_response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi3:3.8b-instruct",  # Faster model
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Slightly lower for more precise answers
                    "num_ctx": 2048,     # Sufficient context window
                    "top_k": 20,         # Reduced from 30
                    "repeat_penalty": 1.2,
                    "num_threads": 8,    # Optimized for your CPU
                    "stop": ["\n", "###"]
                }
            },
            timeout=30  # Reduced from 150
        )

        response_data = ollama_response.json()
        response_text = response_data.get("response", "")

        # 4. Enhance response with sources if needed
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