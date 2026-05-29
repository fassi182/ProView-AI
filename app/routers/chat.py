#chat.py 
import re
import json
import torch
from fastapi import APIRouter, HTTPException, status
from transformers import AutoTokenizer, AutoModel
from app.schemas import MessageModel, ChatResponse, ProViewCoachOutput
from app.database import supabase
from app.config import ProViewConfig
from app.llm_logic import get_proview_chain, format_chat_history

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Interview Coach AI Engine"]
)

tokenizer = AutoTokenizer.from_pretrained(ProViewConfig.EMBEDDING_MODEL)
model = AutoModel.from_pretrained(ProViewConfig.EMBEDDING_MODEL)

def generate_local_embedding(text: str) -> list[float]:
    inputs = tokenizer(text, padding=True, truncation=True, return_tensors="pt", max_length=512)
    with torch.no_grad():
        model_output = model(**inputs)
    token_embeddings = model_output[0]
    input_mask_expanded = inputs['attention_mask'].unsqueeze(-1).expand(token_embeddings.size()).float()
    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    return (sum_embeddings / sum_mask).flatten().tolist()

def extract_valid_json(raw_text: str) -> str:
    """Helper to ensure markdown wrappers are cleanly peeled off if they slip past Groq JSON mode."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        return match.group(0)
    return raw_text

@router.post("/message", response_model=ChatResponse)
async def process_chat_message(session_id: str, payload: MessageModel):
    try:
        # 1. Retrieve the session configuration
        session_lookup = supabase.table("chat_sessions") \
            .select("user_email", "job_title", "difficulty_level", "interview_focus") \
            .eq("session_id", session_id) \
            .limit(1) \
            .execute()

        if not session_lookup.data:
            raise HTTPException(status_code=404, detail="Active interview session reference not found.")
        
        session_info = session_lookup.data[0]
        user_email = session_info["user_email"]
        job_title = session_info["job_title"]
        difficulty = session_info["difficulty_level"]
        focus = session_info["interview_focus"]

        # 2. Extract historical conversation logs
        history_response = supabase.table("chat_messages") \
            .select("role", "interviewer_chat") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()

        chat_history = [
            {"role": row["role"], "content": row["interviewer_chat"]}
            for row in history_response.data
        ]

        # 3. Vectorization & RAG Context Lookup
        query_vector = generate_local_embedding(payload.content)
        rpc_response = supabase.rpc("match_documents", {
            "query_embedding": query_vector,
            "match_threshold": 0.35,
            "match_count": 3,
            "filter_email": user_email
        }).execute()

        retrieved_context = "\n---\n".join([row["content_chunk"] for row in rpc_response.data]) if rpc_response.data else "No document context found."

        # 4. Invoke LLM Chain cleanly
        formatted_history = format_chat_history(chat_history)
        chain = get_proview_chain()
        
        chain_output = chain.invoke({
            "input": (
                f"INTERVIEW CONFIGURATION PROFILE:\n"
                f"- Target Job Title: {job_title}\n"
                f"- Set Difficulty Tier: {difficulty}\n"
                f"- Selected Focus Lens: {focus}\n\n"
                f"Retrieved Document Context:\n{retrieved_context}\n\n"
                f"User Current Answer:\n{payload.content}"
            ),
            "history": formatted_history
        })
        
        raw_llm_string = chain_output.content.strip()
        cleaned_json_string = extract_valid_json(raw_llm_string)
        
        # 5. Parse and build schema payload seamlessly
        parsed_dict = json.loads(cleaned_json_string)
        ai_structured_output = ProViewCoachOutput(**parsed_dict)

        # 6. Record conversation turns back to Supabase logs
        supabase.table("chat_messages").insert({
            "session_id": session_id,
            "role": "user",
            "interviewer_chat": payload.content
        }).execute()

        supabase.table("chat_messages").insert({
            "session_id": session_id,
            "role": "assistant",
            "interviewer_chat": ai_structured_output.interviewer_chat,
            "score": ai_structured_output.score,
            "suggested_replies": ai_structured_output.suggested_replies
        }).execute()

        return ChatResponse(ai_response=ai_structured_output)

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Interview core execution failure: {str(e)}"
        )