# app/services.py
import logging
from typing import List, Dict
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
        try:
            _proview_chain = get_proview_chain()
            logger.info("✅ ProView chain loaded")
        except Exception as e:
            logger.error(f"❌ Failed to initialize chain: {str(e)}", exc_info=True)
            raise
    return _proview_chain

def get_proview_response(
    user_input: str, 
    chat_history: List[Dict], 
    session_id: str
) -> ProViewCoachOutput:
    """
    Generate AI coach response with RAG context
    
    Args:
        user_input: User's message
        chat_history: Previous conversation messages (list of dicts with 'role' and 'content')
        session_id: Session ID for context retrieval
        
    Returns:
        Structured AI response (ProViewCoachOutput)
        
    Raises:
        Exception: If response generation fails critically
    """
    try:
        # Validate inputs
        if not user_input or not user_input.strip():
            logger.warning("Empty user input received")
            return ProViewCoachOutput(
                interviewer_chat="I didn't receive your message. Could you please try again?",
                suggested_replies=["Tell me about yourself", "I need help preparing for an interview"]
            )
        
        if not session_id:
            logger.error("No session_id provided")
            return ProViewCoachOutput(
                interviewer_chat="Session error. Please refresh and try again.",
                suggested_replies=["Refresh page"]
            )
        
        # Retrieve relevant context from vector database
        logger.info(f"Retrieving context for session {session_id[:8]}...")
        context = get_retrieved_context(user_input, session_id, k=3)
        logger.debug(f"Context retrieved: {len(context)} characters")
        
        # Format chat history for LangChain
        logger.info(f"Formatting {len(chat_history)} messages from history")
        formatted_history = format_chat_history(chat_history)
        logger.debug(f"Formatted history: {len(formatted_history)} messages")
        
        # Get ProView chain
        chain = get_chain()
        
        # Prepare input
        chain_input = {
            "input": user_input.strip(),
            "history": formatted_history,
            "context": context
        }
        
        logger.info(f"Invoking chain for session {session_id[:8]}...")
        
        # Generate response
        response = chain.invoke(chain_input)
        
        # Validate response
        if not isinstance(response, ProViewCoachOutput):
            logger.error(f"Chain returned unexpected type: {type(response)}")
            raise TypeError(f"Expected ProViewCoachOutput, got {type(response)}")
        
        # Ensure interviewer_chat is not empty
        if not response.interviewer_chat or not response.interviewer_chat.strip():
            logger.error("Chain returned empty interviewer_chat")
            response.interviewer_chat = "I'm processing your request. Could you please provide more details?"
            if not response.suggested_replies:
                response.suggested_replies = ["Tell me more", "What role are you preparing for?"]
        
        logger.info(f"✅ Generated response for session {session_id[:8]}...")
        logger.debug(f"Response: {response.interviewer_chat[:100]}...")
        
        return response
        
    except TypeError as te:
        # Type errors (wrong response format)
        logger.error(f"❌ Type error in response generation: {str(te)}", exc_info=True)
        return ProViewCoachOutput(
            interviewer_chat="I encountered a formatting error. Let's start fresh. What role are you interviewing for?",
            suggested_replies=["Software Engineer", "Product Manager", "Data Scientist", "Other role"]
        )
        
    except ValueError as ve:
        # Validation errors
        logger.error(f"❌ Validation error: {str(ve)}", exc_info=True)
        return ProViewCoachOutput(
            interviewer_chat="I couldn't process that input. Could you rephrase your message?",
            suggested_replies=["Tell me about yourself", "I'm preparing for a job interview"]
        )
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"❌ Unexpected error generating response: {str(e)}", exc_info=True)
        
        # Return user-friendly fallback response
        return ProViewCoachOutput(
            interviewer_chat="I apologize, but I encountered an issue. Let's try again. What would you like help with?",
            suggested_replies=[
                "Start interview practice", 
                "Upload my resume",
                "Get feedback on my answer"
            ]
        )

def validate_response(response: ProViewCoachOutput) -> ProViewCoachOutput:
    """
    Validate and clean up AI response
    
    Args:
        response: AI generated response
        
    Returns:
        Validated and cleaned response
    """
    # Ensure interviewer_chat is never empty
    if not response.interviewer_chat or not response.interviewer_chat.strip():
        response.interviewer_chat = "I'm here to help you prepare for your interview. What would you like to work on?"
    
    # Ensure suggested_replies is a list
    if response.suggested_replies is None:
        response.suggested_replies = []
    
    # Validate score format if present
    if response.score:
        import re
        if not re.match(r'^\d{1,2}/10$', response.score):
            logger.warning(f"Invalid score format: {response.score}")
            response.score = None
    
    return response