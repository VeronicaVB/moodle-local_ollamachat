"""
    This script is more advanced, uses embedding and Faiss to make the search faster
    https://github.com/facebookresearch/faiss
"""
import requests
import sys
import json
import os
import logging
import numpy as np
import datetime

# log_file_path = r"C:\xampp\moodledata\local_ollamachat\semantic_context.log"

# with open(log_file_path, "a", encoding="utf-8") as log_file:
#     log_file.write(f"\n[{datetime.datetime.now()}] --- Script started ---\n")
#     log_file.write(f"[{datetime.datetime.now()}] Python version: {sys.version}\n")
#     log_file.write(f"[{datetime.datetime.now()}] Python executable: {sys.executable}\n")

import faiss
from urllib.parse import urlparse
from difflib import SequenceMatcher
from functools import lru_cache
from sklearn.metrics.pairwise import cosine_similarity
from light_embed import TextEmbedding


# print(f"Using Python version: {sys.version}")
# print(f"Python executable: {sys.executable}")

# Ensure stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

# Log file path (hardcoded for now)
LOG_FILE_PATH = r"C:\xampp\moodledata\local_ollamachat\ollamachat_error.log"

# Logging configuration
logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


# --- Basic helpers for fallback and cleaning ---

def calculate_relevance(text, prompt):
    """Calculate relevance score between text and prompt using string similarity"""
    return SequenceMatcher(None, text.lower(), prompt.lower()).ratio()

def clean_text(text):
    """Cleans text by removing problematic characters"""
    return (text.replace('\r', ' ')
            .replace('\n', ' ')
            .replace('\t', ' ')
            .strip())

# --- Semantic embedding context retrieval using light_embed its less powerfull than Faiss ---

def get_semantic_context_NORMAL(prompt, embeddings_dir, top_n=3, min_score=0.4):
    """Uses precomputed embeddings and metadata to find the most relevant context for the prompt"""
    try:
        embeddings_path = os.path.join(embeddings_dir, 'embeddings.npy')
        metadata_path = os.path.join(embeddings_dir, 'metadata.json')
        model_dir = os.path.join(os.path.dirname(__file__), '../models/all-MiniLM-L6-v2-onnx')

        # Load saved embedding matrix and corresponding metadata
        embeddings = np.load(embeddings_path)
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Load ONNX embedding model with configuration
        config_path = os.path.join(model_dir, 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        config_dict["onnx_file"] = "model.onnx"

        model = TextEmbedding(model_name_or_path=model_dir, model_config=config_dict)

        # Encode user input prompt
        prompt_embedding = model.encode([prompt])

        # Compute cosine similarity between user prompt and all saved knowledge embeddings
        similarities = cosine_similarity(prompt_embedding, embeddings)[0]

        # Apply min_score filter
        filtered_indices = [i for i, score in enumerate(similarities) if score >= min_score]

        # Log similarities for debugging
        # Select top 3 most relevant entries
        # top_indices = similarities.argsort()[-3:][::-1]
        top_indices = sorted(filtered_indices, key=lambda i: similarities[i], reverse=True)[:top_n]

        context = []
        sources = []

        for idx in top_indices:
            item = metadata[idx]
            score = similarities[idx]
            context.append(
                f"### {item['title']}\nContent: Similarity Score: {score:.2f} | Source: {item['url']}"
            )
            sources.append(item['url'])

        return "\n".join(context), sources

    except Exception as e:
        logging.error(f"Error loading semantic context: {str(e)}")
        return "", []

def get_semantic_context(prompt, embeddings_dir, top_n=500, min_score=0.9):
    """Uses FAISS to find the most relevant contexts."""
    try:
        logging.info(f"Running semantic search for prompt: {prompt}")

        embeddings_path = os.path.join(embeddings_dir, 'embeddings.npy')
        metadata_path = os.path.join(embeddings_dir, 'metadata.json')
        model_dir = os.path.join(os.path.dirname(__file__), '../models/all-MiniLM-L6-v2-onnx')

        # Load the saved embeddings
        logging.info(f"Loading embeddings from: {embeddings_path}")
        embeddings = np.load(embeddings_path).astype('float32')
        logging.info(f"Embeddings shape: {embeddings.shape}")

        logging.info(f"Loading metadata from: {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        logging.info(f"Metadata items loaded: {len(metadata)}")

        # Load ONNX model
        config_path = os.path.join(model_dir, 'config.json')
        logging.info(f"Loading ONNX model config from: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        config_dict["onnx_file"] = "model.onnx"

        model = TextEmbedding(model_name_or_path=model_dir, model_config=config_dict)

        # Encode the query
        logging.info("Encoding prompt...")
        prompt_embedding = model.encode([prompt]).astype('float32')
        logging.info(f"Prompt embedding shape: {prompt_embedding.shape}")

        # Create the FAISS index
        logging.info("Creating FAISS index...")
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)
        logging.info("Index created and embeddings added.")

        # Search for the top_n nearest neighbors
        distances, indices = index.search(prompt_embedding, top_n)
        logging.info(f"FAISS raw distances: {distances}")
        logging.info(f"FAISS raw indices: {indices}")

        # Filter the results using the score threshold
        filtered_indices = [i for i, score in zip(indices[0], distances[0]) if score <= min_score]
        logging.info(f"Filtered indices (score <= {min_score}): {filtered_indices}")

        if not filtered_indices:
            logging.warning("No relevant context found (filtered_indices is empty).")

        # Select the closest indices
        top_indices = sorted(filtered_indices, key=lambda i: distances[0][indices[0].tolist().index(i)])[:top_n]

        # Prepare the context information
        context = []
        sources = []

        for idx in top_indices:
            item = metadata[idx]
            score = distances[0][indices[0].tolist().index(idx)]
            context_line = f"### {item['title']}\nContent: Similarity Score: {score:.2f} | Source: {item['url']}"
            context.append(context_line)
            sources.append(item['url'])
            logging.info(f"Selected context item: {context_line}")

        full_context = "\n".join(context)
        logging.info(f"Final context length: {len(full_context)} characters")

        return full_context, sources

    except Exception as e:
        logging.error(f"Error loading semantic context: {str(e)}", exc_info=True)
        return "", []
# --- Optional fallback in case embedding-based search fails ---

@lru_cache(maxsize=500)
def fetch_knowledge_cached(url):
    """Cached version of knowledge fetching via API"""
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
        logging.error(f"Knowledge API Error: {str(e)}")
        return []

# --- Final response formatting helpers ---

def format_response_with_sources(response_text, knowledge, sources):
    """Enhances the response with source information and ensures proper explanation"""
    if len(response_text.strip()) < 100 and sources:
        # Fallback: use context content directly if model response is too short
        knowledge_content = ""
        sections = knowledge.split('###')[1:] if '###' in knowledge else []
        for section in sections:
            parts = section.split('\n', 1)
            if len(parts) > 1:
                content = parts[1].strip()
                if "Content:" in content:
                    content = content.split("Content:")[1].strip()
                knowledge_content += content + " "

        if knowledge_content:
            topics = [src.split('/')[-1].replace('-', ' ').title() for src in sources if '/' in src]
            topic_text = ", ".join(topics) if topics else "your question"

            response_text = (
                f"Here's a comprehensive explanation about {topic_text}:\n\n" +
                knowledge_content.strip() + "\n\n" +
                "This information should help you complete the task effectively."
            )

    # Attach reference links if not already included
    if sources and not any(src in response_text for src in sources):
        source_intro = "\n\nFor more detailed information, you can refer to these resources:"
        return response_text + source_intro + "\n" + "\n".join([f" {url}" for url in sources[:3]])

    return response_text

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

        if any(keyword.lower() in title or keyword.lower() in content or keyword.lower() in item_keywords for keyword in keywords):
            filtered_items.append(item)

    return filtered_items

def process_knowledge(items, prompt):
    """Processes articles with relevance scores after filtering by relevant keywords in title, content, and keywords"""
    scored_items = []
    keywords = prompt.split()
    filtered_items = filter_items_by_keywords(items, keywords)

    for item in filtered_items:
        title = clean_text(item.get('title', ''))
        url = item.get('url', '')
        content = clean_text(item.get('content', ''))
        keywords = clean_text(item.get('keywords', ''))

        title_score = calculate_relevance(title, prompt) * 1.5
        content_score = calculate_relevance(content, prompt) * 1.2
        keyword_score = calculate_relevance(keywords, prompt) * 1.3
        url_score = calculate_relevance(url, prompt)

        total_score = (title_score + content_score + keyword_score + url_score) / 5

        if total_score > 0.2:
            scored_items.append({
                'title': title,
                'url': url,
                'content': content[:2000],
                'keywords': keywords,
                'score': total_score
            })

    scored_items.sort(key=lambda x: x['score'], reverse=True)

    context = []
    sources = []
    for item in scored_items[:3]:
        entry = (
            f"### {item['title']}\n"
            f"Content: {item['content'][:800]}...\n"
        )
        context.append(entry)
        sources.append(item['url'])

    return "\n".join(context), sources


# --- Main entry point for generating answers ---

def generate_response(prompt, knowledge_url=None, embeddings_dir=None):
    """Generates response using Ollama with enhanced semantic knowledge integration"""
    try:
        # Attempt to load context from local semantic embeddings

        knowledge, sources = get_semantic_context(prompt, embeddings_dir, top_n=5, min_score=0.9)

        # Optional fallback: fetch from remote API if embedding context is empty
        if not knowledge and knowledge_url:
            data = fetch_knowledge_cached(knowledge_url)
            if data:
                knowledge, sources = process_knowledge(data, prompt)

        # Construct full instruction-based prompt for LLM
        # full_prompt = (
        #     "You are a helpful assistant for a school platform with access to a knowledge base.\n"
        #     "Your task is to:\n"
        #     "1. Carefully read the user's question.\n"
        #     "2. Review only the CONTEXT provided below.\n"
        #     "3. If relevant instructions or details are found in the CONTEXT, explain them clearly, step by step.\n"
        #     "4. Use **markdown** or *quotations* to highlight relevant instructions.\n"
        #     "5. Do not use your own general knowledge or make assumptions.\n"
        #     "6. If the question is not covered in the CONTEXT, respond with: 'I can only answer questions related to the content in the knowledge base.'\n"
        #     "7. Always respond in the same language as the user’s question.\n"
        #     "8. At the end, list any source URLs you used.\n\n"
        #     f"CONTEXT:\n{knowledge if knowledge else 'No additional context available.'}\n\n"
        #     f"USER QUESTION: {prompt}\n\n"
        #     "Please provide an answer based solely on the content above."
        # )

        # full_prompt = (
        #     "You are a knowledgeable school assistant that ONLY uses the provided context from the knowledge base to answer the user's question.\n"
        #     "Instructions:\n"
        #     "1. First, carefully analyze the user's question to understand what task they need help with.\n"
        #     "2. Search ONLY the context provided below (titles, URLs, and content) to find relevant information.\n"
        #     "3. If you find relevant information in the CONTEXT, use it to answer the user's question.\n"
        #     "4. If the context does not provide sufficient information to answer the user's question, you must respond by saying that you can only provide information from the knowledge base.\n"
        #     "5. Do not add any general knowledge or information that is not present in the CONTEXT.\n"
        #     "6. If multiple context sources (titles, URLs, or content) provide useful information, COMBINE them into one coherent answer.\n"
        #     "7. Always respond in the same language as the user's question.\n\n"
        #     f"CONTEXT:\n{knowledge if knowledge else 'No additional context available.'}\n\n"
        #     f"USER QUESTION: {prompt}\n\n"
        #     "Please provide a clear and coherent answer based strictly on the context above. If the information is not available, clearly state that your answer is based solely on the knowledge in the provided context."
        # )

        full_prompt = f"Using ONLY this context:\n{knowledge}\n\nQ: {prompt}\nA:"


        # Call local Ollama model
        ollama_response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi3:mini",  # 35% faster than full phi3
                "prompt": full_prompt,
                "stream": False,
                "options": { # https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values
                    "temperature": 0.1,       # Maximum determinism
                    "num_ctx": 512,           # Halved context window
                    "top_k": 5,               # Very narrow sampling
                    "repeat_penalty": 1.0,    # No repetition penalty
                    "num_threads": 6,         # Fewer threads reduce overhead
                    "num_predict": 150        # Very short responses
                }
            },
            timeout=160  # Fail fast
        )

        try:
            response_data = ollama_response.json()
            response_text = response_data.get("response", "")

        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError: {str(e)} - Raw: {ollama_response.text}")
            return {
                "success": False,
                "response": "Error parsing the response from the model. Please try again later.",
                "sources": []
            }

        response_text = format_response_with_sources(response_text, knowledge, sources)

        return {
            "success": True,
            "response": response_text,
            "sources": sources,
            "context_used": bool(knowledge.strip())
        }

    except requests.exceptions.RequestException as e:
        logging.error(f"RequestException: {str(e)}")
        return {
            "success": False,
            "response":  f"RequestException: {str(e)}",#"I'm having trouble accessing our knowledge base. Please try again later.",
            "sources": []
        }
    except Exception as e:
        logging.error(f"RequestException: {str(e)}")
        return {
            "success": False,
            "response": "An unexpected error occurred. Please try again or contact support.",
            "sources": []
        }

# --- CLI entrypoint for direct execution ---

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
        embedding_path = sys.argv[3] if len(sys.argv) > 3 else None
        if not embedding_path:
            logging.error("Embedding path not received")



        result = generate_response(prompt, knowledge_url, embedding_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        logging.error(f"Main execution error: {str(e)}")
        print(json.dumps({
            "success": False,
            "response": "We're experiencing technical difficulties. Please try again later.",
            "sources": []
        }, ensure_ascii=False))