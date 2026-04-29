from typing import List, Tuple, Optional
from agent.config import settings
try:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import create_engine, Column, Integer, String, Text
    from sqlalchemy.orm import declarative_base, sessionmaker
except Exception:
    Vector = None
    create_engine = None

Base = declarative_base() if 'declarative_base' in globals() else None

class DocumentChunk(Base):  # type: ignore
    __tablename__ = 'chunks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(64))
    text = Column(Text)
    embedding = Column(Vector(1024)) if Vector else Column(Text)

class PGVectorStore:
    def __init__(self):
        self.url = settings.pgvector_url
        self.available = bool(self.url and create_engine)
        if self.available:
            self.engine = create_engine(self.url)
            self.SessionLocal = sessionmaker(bind=self.engine)
            try:
                Base.metadata.create_all(self.engine)
            except Exception:
                self.available = False

    def upsert_chunks(self, doc_id: str, chunks: List[Tuple[str, List[float]]]):
        if not self.available:
            return False
        s = self.SessionLocal()
        try:
            for text, emb in chunks:
                s.add(DocumentChunk(doc_id=doc_id, text=text, embedding=emb))
            s.commit()
            return True
        finally:
            s.close()

    def query(self, query_emb: List[float], top_k: int = 5) -> List[str]:
        if not self.available:
            return []
        s = self.SessionLocal()
        try:
            rows = s.execute("SELECT text FROM chunks ORDER BY embedding <-> :q LIMIT :k", {"q": query_emb, "k": top_k}).fetchall()
            return [r[0] for r in rows]
        finally:
            s.close()

vector_store = PGVectorStore()