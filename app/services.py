#app/services.py
from typing import List, Dict
from app.llm_logic import get_proview_chain, format_chat_history
from app.schemas import ProViewCoachOutput

_chain = None

def get_chain():
    global _chain
    if _chain is None:
        _chain = get_proview_chain()
    return _chain


def get_proview_response(user_input: str, chat_history: List[Dict]) -> ProViewCoachOutput:
    try:
        if not user_input.strip():
            return ProViewCoachOutput(
                interviewer_chat="Please enter a message.",
                suggested_replies=["Tell me about yourself"]
            )

        formatted_history = format_chat_history(chat_history)

        chain = get_chain()

        response = chain.invoke({
            "input": user_input,
            "history": formatted_history
        })

        return response

    except Exception as e:
        return ProViewCoachOutput(
            interviewer_chat=f"Error: {str(e)}",
            suggested_replies=["Try again"]
        )