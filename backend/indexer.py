from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

def indexer(results):
    # Qdrant IN RAM
    client = QdrantClient(":memory:")

    # Code-Strong model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    if client.collection_exists("tempCollection"):
        client.delete_collection("tempCollection")
        
    client.create_collection(
        collection_name="tempCollection",
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    points = [] 
    for i, entry in enumerate(results):
        vector = model.encode(entry['content']).tolist()
        points.append(
            PointStruct(
                id=i, 
                vector=vector, 
                payload=entry
            )
        )
    client.upsert(collection_name="tempCollection", points=points)
    return client, model