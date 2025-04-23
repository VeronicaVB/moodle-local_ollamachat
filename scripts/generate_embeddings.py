import sys
import os
import json
import requests
import numpy as np
from light_embed import TextEmbedding
# print("Python executable being used:", sys.executable)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_embeddings.py <knowledge_base_url>")
        sys.exit(1)

    kb_url = sys.argv[1]
    output_file = sys.argv[2]
    output_dir = os.path.dirname(output_file)

    try:
        response = requests.get(kb_url)
        response.raise_for_status()
        kb_data = response.json()
    except Exception as e:
        print(f"Error fetching KB from {kb_url}: {e}")
        sys.exit(1)

    model_dir = r"C:\xampp\htdocs\moodle\local\ollamachat\models\all-MiniLM-L6-v2-onnx"
    config_path = os.path.join(model_dir, "config.json")

    # turn the json into a dictionary to be able to load the  configuration
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = json.load(f)

    config_dict["onnx_file"] = "model.onnx" # Add it explicity to avoid error onnx_file must be present in model_config

    model = TextEmbedding(model_name_or_path=model_dir, model_config=config_dict)

    documents = []
    metadata = []

    for item in kb_data:
        text = f"{item['title']}\n{item['keywords']}\n{item['content']}"
        documents.append(text)
        metadata.append({
            "extid": item["extid"],
            "title": item["title"],
            "url": item["url"]
        })

    embeddings = model.encode(documents)
    embeddings_path = os.path.join(output_dir, "embeddings.npy")
    metadata_path = os.path.join(output_dir, "metadata.json")

    np.save(embeddings_path, embeddings)

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("Embeddings saved to:", embeddings_path)
    print("Metadata saved to:", metadata_path)

if __name__ == "__main__":
    main()
