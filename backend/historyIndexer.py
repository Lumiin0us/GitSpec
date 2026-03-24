import json
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

def indexHistory(commitsFile, client, model):
    """
    Reads a JSONL file of filtered commits and indexes them into Qdrant.
    """
    collectionName = "historyIndex"

    if client.collection_exists(collectionName):
        client.delete_collection(collectionName)
        
    client.create_collection(
        collection_name=collectionName,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    points = []
    
    with open(commitsFile, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            commit = json.loads(line)
            
            vector = model.encode(commit['embedText']).tolist()
            
            points.append(
                PointStruct(
                    id=i, 
                    vector=vector, 
                    payload=commit
                )
            )

    if points:
        client.upsert(collection_name=collectionName, points=points)
        print(f"Successfully indexed {len(points)} commits into {collectionName}")
    else:
        print("No commits found in file to index.")

    return client, model 