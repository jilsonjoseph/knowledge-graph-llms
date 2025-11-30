# Import necessary modules
import streamlit as st
import streamlit.components.v1 as components
from generate_knowledge_graph import generate_knowledge_graph, load_graph_from_db
import uuid

# Set up Streamlit page configuration
st.set_page_config(
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
    menu_items=None
)

# Initialize session state if it doesn't exist
if "history" not in st.session_state:
    st.session_state.history = []
if "net" not in st.session_state:
    st.session_state.net = None
if "current_graph_id" not in st.session_state:
    st.session_state.current_graph_id = None

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

st.sidebar.title("History")
if not st.session_state.history:
    st.sidebar.write("No past entries yet.")
    selected_graph_name = None
else:
    history_names = [item["name"] for item in st.session_state.history]
    selected_graph_name = st.sidebar.selectbox("Select a past entry:", history_names)


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
            # Generate the new graph and update the session state
            st.session_state.net = generate_knowledge_graph(text, graph_id)
            st.session_state.current_graph_id = graph_id
            # Add the new graph to the history
            st.session_state.history.append({"graph_id": graph_id, "name": graph_name, "text": text})
            st.success("Knowledge graph generated and persisted successfully!")

# Priority 2: User selects a different graph from history.
# This runs only if the 'Generate' button was not clicked.
elif selected_graph_name:
    selected_graph = next((item for item in st.session_state.history if item["name"] == selected_graph_name), None)
    
    # Only reload from the database if the selected graph is not already the one being displayed
    if selected_graph and selected_graph["graph_id"] != st.session_state.current_graph_id:
        with st.spinner(f"Loading '{selected_graph_name}'..."):
            # Load the selected graph and update the session state
            st.session_state.net = load_graph_from_db(selected_graph["graph_id"])
            st.session_state.current_graph_id = selected_graph["graph_id"]

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
