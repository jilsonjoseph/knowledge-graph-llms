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

# Initialize session state for history if it doesn't exist
if "history" not in st.session_state:
    st.session_state.history = []

# Set the title of the app
st.title("Knowledge Graph From Text")

# Sidebar section for user input method
st.sidebar.title("Input document")
input_method = st.sidebar.radio(
    "Choose an input method:",
    ["Upload txt", "Input text"],
)

# Text input for naming the graph
graph_name = st.sidebar.text_input("Enter a name for the graph:")

# Case 1: User chooses to upload a .txt file
if input_method == "Upload txt":
    # File uploader widget in the sidebar
    uploaded_file = st.sidebar.file_uploader(label="Upload file", type=["txt"])
    
    if uploaded_file is not None:
        # Read the uploaded file content and decode it as UTF-8 text
        text = uploaded_file.read().decode("utf-8")
 
        # Button to generate the knowledge graph
        if st.sidebar.button("Generate Knowledge Graph"):
            if not graph_name:
                st.sidebar.warning("Please enter a name for the graph.")
            else:
                with st.spinner("Generating knowledge graph..."):
                    graph_id = str(uuid.uuid4())
                    # Call the function to generate the graph from the text
                    net = generate_knowledge_graph(text, graph_id)
                    st.session_state.history.append({"graph_id": graph_id, "name": graph_name, "text": text})
                    st.success("Knowledge graph generated and persisted successfully!")
                    
                    # Save the graph to an HTML file
                    output_file = "knowledge_graph.html"
                    net.save_graph(output_file) 

                    # Open the HTML file and display it within the Streamlit app
                    HtmlFile = open(output_file, 'r', encoding='utf-8')
                    components.html(HtmlFile.read(), height=1000)

# Case 2: User chooses to directly input text
else:
    # Text area for manual input
    text = st.sidebar.text_area("Input text", height=300)

    if text:  # Check if the text area is not empty
        if st.sidebar.button("Generate Knowledge Graph"):
            if not graph_name:
                st.sidebar.warning("Please enter a name for the graph.")
            else:
                with st.spinner("Generating knowledge graph..."):
                    graph_id = str(uuid.uuid4())
                    # Call the function to generate the graph from the input text
                    net = generate_knowledge_graph(text, graph_id)
                    st.session_state.history.append({"graph_id": graph_id, "name": graph_name, "text": text})
                    st.success("Knowledge graph generated and persisted successfully!")
                    
                    # Save the graph to an HTML file
                    output_file = "knowledge_graph.html"
                    net.save_graph(output_file) 

                    # Open the HTML file and display it within the Streamlit app
                    HtmlFile = open(output_file, 'r', encoding='utf-8')
                    components.html(HtmlFile.read(), height=1000)

# History section in the sidebar
st.sidebar.title("History")
if not st.session_state.history:
    st.sidebar.write("No past entries yet.")
else:
    # Create a list of graph names for the selectbox
    history_names = [item["name"] for item in st.session_state.history]
    selected_graph_name = st.sidebar.selectbox("Select a past entry:", history_names)

    if selected_graph_name:
        # Find the selected graph's data from the history
        selected_graph = next((item for item in st.session_state.history if item["name"] == selected_graph_name), None)
        if selected_graph:
            with st.spinner(f"Loading '{selected_graph_name}'..."):
                # Regenerate the graph from the database using its ID
                net = load_graph_from_db(selected_graph["graph_id"])
                
                output_file = "knowledge_graph.html"
                net.save_graph(output_file)

                HtmlFile = open(output_file, 'r', encoding='utf-8')
                components.html(HtmlFile.read(), height=1000)

