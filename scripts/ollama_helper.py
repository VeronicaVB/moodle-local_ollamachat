#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import sys
import json
from urllib.parse import urlparse
from difflib import SequenceMatcher

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

        # Combine all searchable text
        searchable_text = f"{title} {keywords} {content} {url}"

        # Calculate relevance scores for different components
        title_score = calculate_relevance(title, prompt) * 1.5  # Higher weight for title
        content_score = calculate_relevance(content, prompt) * 1.2
        keyword_score = calculate_relevance(keywords, prompt) * 1.3
        url_score = calculate_relevance(url, prompt)

        # Combined weighted score
        total_score = (title_score + content_score + keyword_score + url_score) / 4

        # Only include items with some minimal relevance
        if total_score > 0.2:  # Adjust threshold as needed
            scored_items.append({
                'title': title,
                'url': url,
                'content': content[:1000],  # Limit length but keep more context
                'keywords': keywords,
                'score': total_score
            })

    # Sort by relevance score
    scored_items.sort(key=lambda x: x['score'], reverse=True)

    # Prepare context and collect sources
    context = []
    sources = []
    for item in scored_items[:5]:  # Take top 5 most relevant
        entry = (
            f"### {item['title']} (Relevance: {item['score']:.2f})\n"
            f"- **URL:** {item['url']}\n"
            f"- **Keywords:** {item['keywords']}\n"
            f"- **Content:** {item['content'][:500]}...\n"
        )
        context.append(entry)
        sources.append(item['url'])

    return "\n\n".join(context), sources

def fetch_knowledge(url):
    """Fetches knowledge from API with enhanced error handling"""
    try:
        # Basic URL validation
        if not urlparse(url).scheme:
            raise ValueError("Invalid URL")

        response = requests.get(
            url,
            timeout=15,
            headers={
                'Accept': 'application/json; charset=utf-8',
                'User-Agent': 'Mozilla/5.0 (compatible; KnowledgeIntegration/1.0)'
            }
        )
        response.encoding = 'utf-8'
        response.raise_for_status()

        # Handle different response formats
        data = response.json()
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        elif isinstance(data, list):
            return data
        else:
            return []

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {str(e)}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print("API returned invalid JSON", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        return []

def generate_response(prompt, knowledge_url=None):
    """Generates response using Ollama with enhanced knowledge integration"""
    try:
        # 1. Get and process knowledge if URL provided
        knowledge = ""
        sources = []

        if knowledge_url:
            data = fetch_knowledge(knowledge_url)
            if data:
                knowledge, sources = process_knowledge(data, prompt)
            else:
                knowledge = "\n[NOTE: No valid knowledge data was retrieved from the provided URL]"

        # 2. Build enhanced prompt with clearer instructions
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

        # 3. Query Ollama with better parameters
        ollama_response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:latest",
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.5,  # Slightly higher for creativity when needed
                    "num_ctx": 8192,     # Larger context window
                    "top_k": 50,         # Consider more tokens
                    "repeat_penalty": 1.1  # Reduce repetition
                }
            },
            timeout=600
        )
        ollama_response.encoding = 'utf-8'
        ollama_response.raise_for_status()

        response_data = ollama_response.json()
        response_text = response_data.get("response", "")

        # 4. Post-process the response to ensure quality
        if "no information" in response_text.lower() and knowledge:
            # If the model missed relevant context, try to extract it
            response_text = (
                "Based on the provided context, here's what I found:\n\n"
                f"{knowledge[:2000]}\n\n"
                "Please let me know if you'd like me to analyze this information further."
            )

        # Add sources if we have them and they're not already mentioned
        if sources and not any(src in response_text for src in sources):
            response_text += "\n\nRelevant sources from context:\n- " + "\n- ".join(sources[:3])

        return {
            "success": True,
            "response": response_text,
            "sources": sources,
            "context_used": bool(knowledge.strip()) if knowledge else False
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "response": f"Connection Error: Failed to communicate with Ollama - {str(e)}",
            "sources": []
        }
    except Exception as e:
        return {
            "success": False,
            "response": f"System Error: {str(e)}",
            "sources": []
        }

if __name__ == "__main__":
    try:
        # Argument handling
        if len(sys.argv) < 2:
            print(json.dumps({
                "success": False,
                "response": "Error: Please provide at least a prompt as argument",
                "sources": []
            }))
            sys.exit(1)

        prompt = sys.argv[1]
        knowledge_url = sys.argv[2] if len(sys.argv) > 2 else None

        # Generate and print response
        result = generate_response(prompt, knowledge_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        error_response = {
            "success": False,
            "response": f"Critical Error: {str(e)}",
            "sources": []
        }
        print(json.dumps(error_response, ensure_ascii=False))