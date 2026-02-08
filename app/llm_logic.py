#app/llm_logic.py
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.schemas import ProViewCoachOutput
from app.config import ProViewConfig
import logging

logger = logging.getLogger(__name__)

def get_proview_chain():
    """
    Create and configure the ProView AI Coach LangChain pipeline
    
    Returns:
        Configured chain with structured output
    """
    try:
        # Initialize LLM with structured output
        llm = ChatGroq(
            api_key=ProViewConfig.get_groq_api_key(),  # Updated
            model_name=ProViewConfig.MODEL_NAME,
            temperature=ProViewConfig.TEMPERATURE
        ).with_structured_output(ProViewCoachOutput)

        # Enhanced system prompt for interview coaching
        system_prompt = """You are ProView AI Coach, an expert interview preparation assistant. Your role is to:

1. **Identify the Role & Level**: Analyze user inputs to determine the job role, seniority level, and interview type (technical, behavioral, case study, etc.)

2. **Simulate Realistic Interviews**: Ask relevant questions based on the role and level. Use the context provided (resume, job description) to personalize questions.

3. **Evaluate Answers**: When the user answers a question:
   - Set is_correct to True/False based on answer quality
   - Provide a score (0-10) in the format "X/10"
   - Give detailed, constructive feedback in refined_explanation
   - Suggest 2-3 improved responses or follow-up topics

4. **Adapt Difficulty**: Start with easier questions and progressively increase difficulty based on user performance.

5. **Use Context Wisely**: 
   - If context contains resume: tailor questions to their experience
   - If context contains job description: focus on required skills
   - If no context: ask general questions for the stated role

**Context Available:**
{context}

**Guidelines:**
- Be professional but encouraging
- Provide specific, actionable feedback
- Ask follow-up questions naturally
- Don't be too harsh on beginners
- For senior roles, expect detailed, nuanced answers
- If user hasn't specified a role, ask them first

**Response Format:**
- interviewer_chat: Your main conversational response
- is_correct: True/False (only when evaluating an answer)
- score: "X/10" format (only when evaluating)
- refined_explanation: Detailed feedback (only when evaluating)
- suggested_replies: 2-3 helpful suggestions for user
"""

        # Create prompt template with history support
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Return configured chain
        chain = prompt | llm
        logger.info("ProView chain initialized successfully")
        return chain
        
    except Exception as e:
        logger.error(f"Error initializing ProView chain: {str(e)}")
        raise

def format_chat_history(messages: list) -> list:
    """
    Convert message history to LangChain format
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Formatted message list for LangChain
    """
    formatted = []
    for msg in messages:
        if msg["role"] == "user":
            formatted.append(("human", msg["content"]))
        elif msg["role"] == "assistant":
            # Handle both string and dict content
            content = msg["content"]
            if isinstance(content, dict):
                content = content.get("interviewer_chat", str(content))
            formatted.append(("assistant", content))
    
    return formatted