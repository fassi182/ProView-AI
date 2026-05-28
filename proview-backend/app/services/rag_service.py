import io
import os
import torch
from pypdf import PdfReader
from transformers import AutoTokenizer, AutoModel
from app.database import supabase
from app.config import ProViewConfig

class RagService:

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> list[str]:
        """
        Splits raw document text into overlapping segments.
        Overlap ensures sentences cut off at a boundary aren't lost contextually.
        """
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    @classmethod
    def process_and_store_pdf(cls, file_bytes: bytes, filename: str, user_email: str):
        """
        Extracts raw text from an uploaded PDF, chunks it, generates vector 
        embeddings LOCALLY via Transformers, and saves them directly to Supabase cloud.
        """
        # 1. Parse text natively from binary memory stream
        pdf_stream = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_stream)
        raw_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                raw_text += page_text + "\n"

        if not raw_text.strip():
            raise ValueError("Could not extract any clean text from the uploaded PDF document.")

        # 2. Divide the text into manageable blocks
        text_chunks = cls.chunk_text(raw_text)

        # 3. Load the Tokenizer and Model locally (Cached on first run)
        ProViewConfig.validate()
        model_name = ProViewConfig.EMBEDDING_MODEL
        
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)

        # 4. Generate mathematical vector calculations locally on CPU
        vectors = []
        for chunk in text_chunks:
            # Tokenize input text segment
            inputs = tokenizer(chunk, padding=True, truncation=True, return_tensors="pt", max_length=512)
            
            # Compute token embeddings without tracking gradients (saves computing power)
            with torch.no_grad():
                model_output = model(**inputs)
            
            # Perform Mean Pooling to transform raw token matrices into a single sentence vector
            token_embeddings = model_output[0]
            input_mask_expanded = inputs['attention_mask'].unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            
            # Convert pooled tensor directly into a standard Python list of numbers
            embedding_vector = (sum_embeddings / sum_mask).flatten().tolist()
            vectors.append(embedding_vector)

        # 5. Structure payload arrays for batch insertion into Supabase
        records_to_insert = []
        for chunk, embedding in zip(text_chunks, vectors):
            records_to_insert.append({
                "user_email": user_email.strip().lower(),
                "document_name": filename,
                "content_chunk": chunk,
                "embedding": embedding  # Perfectly matching 384 dimensions natively
            })

        if not records_to_insert:
            raise ValueError("Failed to compile valid vector matrices from the document.")

        # 6. Execute bulk transaction insert onto the cloud
        supabase.table("document_vectors").insert(records_to_insert).execute()
        return len(records_to_insert)