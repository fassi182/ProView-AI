from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.config import ProViewConfig

def format_chat_history(history_list: list[dict]) -> list:
    """Transforms raw database dictionary matrices into standard LangChain message roles."""
    formatted = []
    for msg in history_list:
        if msg["role"] == "user":
            formatted.append(("user", msg["content"]))
        else:
            formatted.append(("assistant", msg["content"]))
    return formatted

def get_proview_chain():
    """
    Compiles the interview orchestration prompt layout.
    Enforces absolute JSON format compliance via Groq's native response_format.
    """
    ProViewConfig.validate()
    
    # Enforce Groq API level JSON mode constraint
    llm = ChatGroq(
        model=ProViewConfig.MODEL_NAME,
        temperature=0.2,
        groq_api_key=ProViewConfig.GROQ_API_KEY,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    system_instruction = (
        "You are the expert technical interviewer and executive coaching engine for ProView AI.\n"
        "Your sole task is to conduct an immersive, high-fidelity interview simulation.\n\n"
        
        "CRITICAL BEHAVIORAL EXPECTATIONS:\n"
        "1. Carefully analyze the incoming 'INTERVIEW CONFIGURATION PROFILE' (Job Title, Difficulty, and Focus Lens).\n"
        "2. You MUST dynamically adapt your technical depth, question complexity, tone, and grading strictness to match that profile.\n"
        "3. If the profile is set to 'Hard' or 'Senior', ask challenging, real-world scenario questions targeting system design, scalability bottlenecks, production edge-cases, and architectural trade-offs.\n"
        "4. If no document context is found, do not complain about it. Simply ask highly tailored questions matching the Target Job Title and Difficulty tier directly.\n\n"
        
        "CONVERSATIONAL STATE ENGINE:\n"
        "- If the 'history' variable is empty, this is the opening turn. Greet the user concisely and launch directly into your first high-impact, profile-matched question.\n"
        "- If history exists, evaluate the user's latest input response critically. Provide a realistic numeric string score out of 10 (e.g., '8/10') and offer comprehensive, highly tactical feedback in 'refined_explanation' on what specific edge cases they missed, then ask your next progressive question.\n\n"
        
        "CRITICAL FORMATTING RULE:\n"
        "You MUST respond with a valid JSON object matching the exact keys below. Do not wrap in markdown or add extra text.\n\n"
        "REQUIRED JSON KEYS:\n"
        "{{\n"
        '  "interviewer_chat": "Your next question or greeting string goes here",\n'
        '  "score": "Provide a score like \'9/10\' or null if it\'s the first greeting turn",\n'
        '  "refined_explanation": "Detailed professional analysis feedback string or null if it\'s the first turn",\n'
        '  "suggested_replies": ["Suggestion chip 1", "Suggestion chip 2", "Suggestion chip 3"]\n'
        "}}"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        MessagesPlaceholder(variable_name="history"),
        ("user", "{input}")
    ])
    
    return prompt | llm