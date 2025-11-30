from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_openai import ChatOpenAI
from pyvis.network import Network
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import asyncio
import uuid
import json

# Load the .env file
load_dotenv()
# Get API key from environment variable
api_key = os.getenv("OPENAI_API_KEY")
# Get Neo4j connection details from environment variables
neo4j_uri = os.getenv("NEO4J_URI")
neo4j_user = os.getenv("NEO4J_USER")
neo4j_password = os.getenv("NEO4J_PASSWORD")

llm = ChatOpenAI(temperature=0, model_name="gpt-4o")

graph_transformer = LLMGraphTransformer(llm=llm)


# Extract graph data from input text
async def extract_graph_data(text):
    """
    Asynchronously extracts graph data from input text using a graph transformer.

    Args:
        text (str): Input text to be processed into graph format.

    Returns:
        list: A list of GraphDocument objects containing nodes and relationships.
    """
    documents = [Document(page_content=text)]
    graph_documents = await graph_transformer.aconvert_to_graph_documents(documents)
    return graph_documents


def _prepare_properties(properties):
    """
    Sanitizes properties to be stored in Neo4j.
    Removes complex objects and keeps only primitive types.
    """
    sanitized = {}
    for key, value in properties.items():
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
    return sanitized

def persist_graph(graph_documents, graph_id, graph_name):
    """
    Persists the generated graph to a Neo4j database.

    Args:
        graph_documents (list): A list of GraphDocument objects with nodes and relationships.
        graph_id (str): The unique ID for the graph.
        graph_name (str): The user-defined name for the graph.
    """
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    with driver.session() as session:
        # Create a metadata node for the graph for easy retrieval and management
        session.run("MERGE (:GraphMetadata {id: $id, name: $name})", id=graph_id, name=graph_name)

        for doc in graph_documents:
            # Create nodes
            for node in doc.nodes:
                properties = _prepare_properties(vars(node))
                properties['graph_id'] = graph_id
                session.run("MERGE (n:GraphResource:`%s` {id: $id}) SET n += $properties" % node.type, id=node.id, properties=properties)

            # Create relationships
            for rel in doc.relationships:
                properties = _prepare_properties(vars(rel))
                properties['graph_id'] = graph_id
                session.run(
                    "MATCH (a:GraphResource {id: $source_id}), (b:GraphResource {id: $target_id}) "
                    "MERGE (a)-[r:`%s`]->(b) SET r += $properties" % (rel.type),
                    source_id=rel.source.id,
                    target_id=rel.target.id,
                    properties=properties
                )
    driver.close()

def get_all_graphs():
    """
    Fetches all graphs' metadata from the Neo4j database.

    Returns:
        list: A list of dictionaries, each representing a graph with 'graph_id' and 'name'.
    """
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    with driver.session() as session:
        result = session.run("MATCH (g:GraphMetadata) RETURN g.id AS graph_id, g.name AS name ORDER BY g.name")
        graphs = [{"graph_id": record["graph_id"], "name": record["name"]} for record in result]
    driver.close()
    return graphs

def _convert_to_graph_document(nodes_data, relationships_data):
    """Converts lists of nodes and relationships into a GraphDocument."""
    # Create Node objects
    node_objects = [Node(id=n['id'], type=n['type']) for n in nodes_data]
    
    # Create a lookup for node objects by id
    node_lookup = {node.id: node for node in node_objects}

    # Create Relationship objects
    relationship_objects = []
    for r in relationships_data:
        source_node = node_lookup.get(r['source'])
        target_node = node_lookup.get(r['target'])
        if source_node and target_node:
            relationship_objects.append(Relationship(
                source=source_node,
                target=target_node,
                type=r['type']
            ))

    # Create a dummy source document
    source_doc = Document(page_content="Loaded from database")

    # Create a GraphDocument
    return [GraphDocument(nodes=node_objects, relationships=relationship_objects, source=source_doc)]


def load_graph_from_db(graph_id):
    """
    Loads a graph from the Neo4j database and visualizes it.

    Args:
        graph_id (str): The unique ID of the graph to load.

    Returns:
        pyvis.network.Network: The visualized network graph object.
    """
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    nodes, relationships = [], []
    with driver.session() as session:
        # Query for all nodes and relationships with the given graph_id
        result = session.run("MATCH (n {graph_id: $graph_id}) "
                             "OPTIONAL MATCH (n)-[r {graph_id: $graph_id}]->(m {graph_id: $graph_id}) "
                             "RETURN n, r, m", graph_id=graph_id)
        
        processed_nodes = set()
        for record in result:
            node1 = record["n"]
            rel = record["r"]
            node2 = record["m"]

            if node1 and node1.id not in processed_nodes:
                nodes.append({"id": node1["id"], "type": list(node1.labels if 'GraphResource' not in node1.labels else [l for l in node1.labels if l != 'GraphResource'])[0], "properties": dict(node1)})
                processed_nodes.add(node1.id)

            if node2 and node2.id not in processed_nodes:
                nodes.append({"id": node2["id"], "type": list(node2.labels if 'GraphResource' not in node2.labels else [l for l in node2.labels if l != 'GraphResource'])[0], "properties": dict(node2)})
                processed_nodes.add(node2.id)
            
            if rel:
                relationships.append({"source": rel.start_node["id"], "target": rel.end_node["id"], "type": rel.type, "properties": dict(rel)})

    driver.close()
    # Remove duplicate relationships
    unique_relationships_str = {json.dumps(d, sort_keys=True) for d in relationships}
    unique_relationships = [json.loads(s) for s in unique_relationships_str]
    
    graph_documents = _convert_to_graph_document(nodes, unique_relationships)
    return visualize_graph(graph_documents)


def visualize_graph(graph_documents):
    """
    Visualizes a knowledge graph using PyVis based on the extracted graph documents.

    Args:
        graph_documents (list): A list of GraphDocument objects with nodes and relationships.

    Returns:
        pyvis.network.Network: The visualized network graph object.
    """
    # Create network
    net = Network(height="1200px", width="100%", directed=True,
                      notebook=False, bgcolor="#222222", font_color="white", filter_menu=True, cdn_resources='remote') 

    nodes = graph_documents[0].nodes
    relationships = graph_documents[0].relationships

    # Build lookup for valid nodes
    node_dict = {node.id: node for node in nodes}
    
    # Filter out invalid edges and collect valid node IDs
    valid_edges = []
    valid_node_ids = set()
    for rel in relationships:
        if rel.source.id in node_dict and rel.target.id in node_dict:
            valid_edges.append(rel)
            valid_node_ids.update([rel.source.id, rel.target.id])

    # Track which nodes are part of any relationship
    connected_node_ids = set()
    for rel in relationships:
        connected_node_ids.add(rel.source.id)
        connected_node_ids.add(rel.target.id)

    # Add valid nodes to the graph
    for node_id in valid_node_ids:
        node = node_dict[node_id]
        try:
            net.add_node(node.id, label=node.id, title=node.type, group=node.type)
        except:
            continue  # Skip node if error occurs

    # Add valid edges to the graph
    for rel in valid_edges:
        try:
            net.add_edge(rel.source.id, rel.target.id, label=rel.type.lower())
        except:
            continue  # Skip edge if error occurs

    # Configure graph layout and physics
    net.set_options("""
        {
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -100,
                    "centralGravity": 0.01,
                    "springLength": 200,
                    "springConstant": 0.08
                },
                "minVelocity": 0.75,
                "solver": "forceAtlas2Based"
            }
        }
    """)

    output_file = "knowledge_graph.html"
    try:
        net.save_graph(output_file)
        print(f"Graph saved to {os.path.abspath(output_file)}")
        return net
    except Exception as e:
        print(f"Error saving graph: {e}")
        return None


def generate_knowledge_graph(text, graph_id, graph_name):
    """
    Generates and visualizes a knowledge graph from input text.

    This function runs the graph extraction asynchronously and then visualizes
    the resulting graph using PyVis.

    Args:
        text (str): Input text to convert into a knowledge graph.
        graph_id (str): The unique ID for the graph.
        graph_name (str): The user-defined name for the graph.

    Returns:
        pyvis.network.Network: The visualized network graph object.
    """
    graph_documents = asyncio.run(extract_graph_data(text))
    persist_graph(graph_documents, graph_id, graph_name)
    net = visualize_graph(graph_documents)
    return net
