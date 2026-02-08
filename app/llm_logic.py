# app/llm_logic.py
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from app.schemas import ProViewCoachOutput
from app.config import ProViewConfig
import logging
from typing import List, Tuple, Union

logger = logging.getLogger(__name__)

def get_proview_chain():
    """
    Create and configure the ProView AI Coach LangChain pipeline
    
    Returns:
        Configured chain with structured output
        
    Raises:
        Exception: If chain initialization fails
    """
    try:
        # Initialize LLM with structured output
        llm = ChatGroq(
            api_key=ProViewConfig.GROQ_API_KEY, 
            model_name=ProViewConfig.MODEL_NAME,
            temperature=ProViewConfig.TEMPERATURE
        )
        
        # Apply structured output schema
        structured_llm = llm.with_structured_output(ProViewCoachOutput)

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
- interviewer_chat: Your main conversational response (REQUIRED - never empty)
- is_correct: True/False (only when evaluating an answer, otherwise null)
- score: "X/10" format (only when evaluating, otherwise null)
- refined_explanation: Detailed feedback (only when evaluating, otherwise null)
- suggested_replies: 2-3 helpful suggestions for user (can be empty list if not applicable)

IMPORTANT: The interviewer_chat field must ALWAYS contain a meaningful response. Never leave it empty.
"""

        # Create prompt template with history support
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Return configured chain
        chain = prompt | structured_llm
        logger.info("✅ ProView chain initialized successfully")
        return chain
        
    except Exception as e:
        logger.error(f"❌ Error initializing ProView chain: {str(e)}", exc_info=True)
        raise

def format_chat_history(messages: List[dict]) -> List[Union[HumanMessage, AIMessage]]:
    """
    Convert message history to LangChain format
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        Formatted message list for LangChain
    """
    formatted = []
    
    if not messages:
        return formatted
    
    try:
        for msg in messages:
            # Validate message structure
            if not isinstance(msg, dict):
                logger.warning(f"Skipping invalid message format: {type(msg)}")
                continue
                
            role = msg.get("role")
            content = msg.get("content")
            
            if not role or not content:
                logger.warning(f"Skipping message with missing role or content")
                continue
            
            # Extract content string
            if isinstance(content, dict):
                # If content is a dict (from AI response), extract interviewer_chat
                content_str = content.get("interviewer_chat", "")
                if not content_str:
                    # Fallback to string representation if no interviewer_chat
                    content_str = str(content)
            else:
                content_str = str(content)
            
            # Create appropriate message type
            if role == "user":
                formatted.append(HumanMessage(content=content_str))
            elif role == "assistant":
                formatted.append(AIMessage(content=content_str))
            else:
                logger.warning(f"Unknown role: {role}")
                
    except Exception as e:
        logger.error(f"Error formatting chat history: {str(e)}", exc_info=True)
        # Return what we have so far
        
    return formatted