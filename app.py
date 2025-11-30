# Import necessary modules
import streamlit as st
import streamlit.components.v1 as components
from generate_knowledge_graph import generate_knowledge_graph, load_graph_from_db, get_all_graphs
import uuid

# Set up Streamlit page configuration
st.set_page_config(
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
    menu_items=None
)

# Initialize session state (history is now managed via the database)
if "net" not in st.session_state:
    st.session_state.net = None
if "current_graph_id" not in st.session_state:
    st.session_state.current_graph_id = None

# Function to load all graphs from DB, cached by Streamlit for performance
@st.cache_data
def load_all_graphs_from_db():
    return get_all_graphs()

# Set the title of the app
st.title("Knowledge Graph From Text")

# --- Sidebar UI Elements ---
st.sidebar.title("Input document")
input_method = st.sidebar.radio(
    "Choose an input method:",
    ["Upload txt", "Input text"],
)

graph_name = st.sidebar.text_input("Enter a name for the graph:")

text = None
if input_method == "Upload txt":
    uploaded_file = st.sidebar.file_uploader(label="Upload file", type=["txt"])
    if uploaded_file is not None:
        text = uploaded_file.read().decode("utf-8")
else:
    text = st.sidebar.text_area("Input text", height=300)

generate_button_clicked = st.sidebar.button("Generate Knowledge Graph")

# --- History UI, now powered by the database ---
all_graphs = load_all_graphs_from_db()

st.sidebar.title("History")
clicked_history_item = None
if not all_graphs:
    st.sidebar.write("No saved graphs yet.")
else:
    # Create a clickable button for each history item
    for item in all_graphs:
        if st.sidebar.button(item["name"], key=f"history_btn_{item['graph_id']}"):
            clicked_history_item = item


# --- Action Handling Logic ---

# Priority 1: User clicks the 'Generate' button.
if generate_button_clicked:
    if not text:
        st.sidebar.warning("Please provide text to generate a graph.")
    elif not graph_name:
        st.sidebar.warning("Please enter a name for the graph.")
    else:
        with st.spinner("Generating knowledge graph..."):
            graph_id = str(uuid.uuid4())
            # Pass graph_name to the generation function
            st.session_state.net = generate_knowledge_graph(text, graph_id, graph_name)
            st.session_state.current_graph_id = graph_id
            st.success("Knowledge graph generated and persisted successfully!")
            # Clear cache and rerun to refresh the history list from the DB
            st.cache_data.clear()
            st.rerun()

# Priority 2: User clicks a history item button.
elif clicked_history_item:
    # Only reload if the selected graph is not already the one being displayed
    if clicked_history_item["graph_id"] != st.session_state.current_graph_id:
        with st.spinner(f"Loading '{clicked_history_item['name']}'..."):
            st.session_state.net = load_graph_from_db(clicked_history_item["graph_id"])
            st.session_state.current_graph_id = clicked_history_item["graph_id"]
            # Rerun to ensure the main panel updates correctly
            st.rerun()

# --- Main Panel for Displaying the Graph ---
# This section simply renders whatever graph is currently in the session state.
if st.session_state.net:
    output_file = "knowledge_graph.html"
    st.session_state.net.save_graph(output_file) 

    with open(output_file, 'r', encoding='utf-8') as HtmlFile:
        source_code = HtmlFile.read()
        components.html(source_code, height=1000)
else:
    st.info("Generate a new graph or select one from history to display it here.")
