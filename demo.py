import chromadb

# Connect to the Chroma server
client = chromadb.HttpClient(host='localhost', port=8000)

# Create a collection
collection = client.create_collection("demo_collection")

# Add documents
collection.add(
    documents=["This is a document about AI.", "This is a document about machine learning."],
    metadatas=[{"source": "ai"}, {"source": "ml"}],
    ids=["doc1", "doc2"]
)

# Query the collection
results = collection.query(
    query_texts=["Tell me about AI"],
    n_results=2
)

print("Query results:")
print(results)
