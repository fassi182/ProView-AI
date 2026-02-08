#app/services.py
import logging
from app.llm_logic import get_proview_chain, format_chat_history
from app.rag_storage import get_retrieved_context
from app.schemas import ProViewCoachOutput

logger = logging.getLogger(__name__)

# Initialize chain once (singleton pattern)
_proview_chain = None

def get_chain():
    """Lazy load the ProView chain"""
    global _proview_chain
    if _proview_chain is None:
        _proview_chain = get_proview_chain()
    return _proview_chain

def get_proview_response(
    user_input: str, 
    chat_history: list, 
    session_id: str
) -> ProViewCoachOutput:
    """
    Generate AI coach response with RAG context
    
    Args:
        user_input: User's message
        chat_history: Previous conversation messages
        session_id: Session ID for context retrieval
        
    Returns:
        Structured AI response
    """
    try:
        # Retrieve relevant context from vector database
        context = get_retrieved_context(user_input, session_id, k=3)
        
        # Format chat history for LangChain
        formatted_history = format_chat_history(chat_history)
        
        # Get ProView chain
        chain = get_chain()
        
        # Generate response
        response = chain.invoke({
            "input": user_input,
            "history": formatted_history,
            "context": context
        })
        
        logger.info(f"Generated response for session {session_id[:8]}...")
        return response
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        
        # Fallback response
        return ProViewCoachOutput(
            interviewer_chat="I apologize, but I encountered an error processing your request. Please try again or reset the session.",
            suggested_replies=["Reset session", "Try different question"]
        )