"""Environment configuration and real retrieval composition, without a test provider switch."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

from kbeauty_support.generation.context import Snapshot, APPROVED_PREPARATION
from kbeauty_support.generation.errors import ServiceError
from kbeauty_support.generation.provider import DisabledProvider, OllamaProvider
from kbeauty_support.generation.service import ChatService
from kbeauty_support.generation.tokenization import REVISION as TOKENIZER_REVISION


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="",repr=False)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_key: str = field(default="",repr=False)
    alias: str = "kbeauty_active"
    data_dir: Path = Path("data")
    model_dir: Path = Path("model-cache/bge-m3/5617a9f61b028005a4858fdac845db406aefb181")
    reranker_dir: Path = Path("model-cache/mmarco-minilm/1427fd652930e4ba29e8149678df786c240d8825")
    rerank_enabled: bool = False
    provider: str = "disabled"
    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:0.6b"
    llm_digest: str = ""
    llm_tokenizer_dir: Path = Path("model-cache/qwen3-tokenizer")/TOKENIZER_REVISION
    llm_timeout: float = 60
    request_timeout: float = 90
    rate_limit: int = 30
    body_limit: int = 32768

    def __post_init__(self):
        parsed=urlsplit(self.qdrant_url)
        if (parsed.scheme not in ("http","https") or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("","/") or (parsed.scheme=="http" and parsed.hostname not in ("127.0.0.1","localhost","::1"))):
            raise ServiceError("invalid_qdrant_url",422)
        if self.provider not in ("disabled","ollama") or not 1<=self.request_timeout<=180 or not 1<=self.rate_limit<=1000:
            raise ServiceError("invalid_service_configuration",422)
        if not 1024<=self.body_limit<=65536:
            raise ServiceError("invalid_body_limit",422)

    @classmethod
    def environment(cls):
        flag=os.getenv("RERANK_ENABLED","false").casefold()
        if flag not in ("true","false"):
            raise ServiceError("invalid_reranker_flag",422)
        return cls(api_key=os.getenv("API_ACCESS_KEY",""),qdrant_url=os.getenv("QDRANT_URL","http://127.0.0.1:6333"),
            qdrant_key=os.getenv("QDRANT_API_KEY",""),alias=os.getenv("QDRANT_COLLECTION_ALIAS","kbeauty_active"),
            data_dir=Path(os.getenv("KBEAUTY_DATA_DIR","data")),model_dir=Path(os.getenv("KBEAUTY_MODEL_DIR",str(cls.model_dir))),
            reranker_dir=Path(os.getenv("KBEAUTY_RERANKER_DIR",str(cls.reranker_dir))),
            rerank_enabled=flag=="true",provider=os.getenv("LLM_PROVIDER","disabled"),
            ollama_url=os.getenv("OLLAMA_URL","http://127.0.0.1:11434"),llm_model=os.getenv("LLM_MODEL","qwen3:0.6b"),
            llm_digest=os.getenv("LLM_MODEL_DIGEST",""),llm_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS","60")),
            llm_tokenizer_dir=Path(os.getenv("LLM_TOKENIZER_DIR",str(cls.llm_tokenizer_dir))),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT_SECONDS","90")),rate_limit=int(os.getenv("API_RATE_PER_MINUTE","30")))


class RuntimeRetriever:
    def __init__(self, settings: Settings, snapshot: Snapshot):
        from qdrant_client import QdrantClient
        from kbeauty_support.retrieval.hybrid import HybridIndex
        self.settings,self.snapshot=settings,snapshot
        # Explicit version/readback checks happen in readiness, not a constructor network call.
        self.client=QdrantClient(url=settings.qdrant_url,api_key=settings.qdrant_key or None,timeout=5,
                                 trust_env=False,check_compatibility=False)
        self.index=HybridIndex(self.client,alias=settings.alias)
        self.encoder=None
        self.scorer=None

    def warm(self):
        if self.encoder is None:
            from kbeauty_support.retrieval.dense import BgeM3Encoder
            encoder=BgeM3Encoder(self.settings.model_dir)
            encoder.encode(["Готовность поиска K-Beauty"])
            self.encoder=encoder

    def ready(self) -> dict:
        try:
            if self.client.info().version!="1.15.1":
                raise ServiceError("unsupported_qdrant_version")
            name=self.index.resolve()
            if name is None:
                raise ServiceError("published_index_missing")
            points,_=self.client.scroll(name,limit=64,with_payload=True)
            if any(p.payload["index"]["preparation_generation"]!=APPROVED_PREPARATION for p in points):
                raise ServiceError("index_snapshot_mismatch")
            self.snapshot.validate([p.payload for p in points])
            return {"ready":self.encoder is not None,"code":"ok" if self.encoder else "encoder_not_warmed","points":len(points)}
        except Exception:
            return {"ready":False,"code":"retrieval_unavailable"}

    def retrieve(self, question: str) -> dict:
        self.warm()
        # Exhaustive candidate pool is intentional for this 20-document corpus, not improved top5 ranking.
        if self.settings.rerank_enabled:
            from kbeauty_support.retrieval.rerank import MiniLMCrossEncoder, RerankedSearch, RerankConfig
            if self.scorer is None:
                self.scorer=RerankedSearch(self.index,self.encoder,lambda:MiniLMCrossEncoder(self.settings.reranker_dir),
                                           RerankConfig(candidate_pool=20,final_k=20))
            return self.scorer.search(question)
        return self.index.search(question,self.encoder,mode="hybrid",limit=20,prefetch=20)

    def close(self):
        self.client.close()


def build_service(settings: Settings) -> ChatService:
    snapshot=Snapshot(settings.data_dir)
    provider=DisabledProvider() if settings.provider=="disabled" else OllamaProvider(settings.ollama_url,
        model=settings.llm_model,expected_digest=settings.llm_digest,timeout=settings.llm_timeout,tokenizer_dir=settings.llm_tokenizer_dir)
    retriever=RuntimeRetriever(settings,snapshot)
    if isinstance(provider,OllamaProvider):
        provider.warm()
        retriever.warm()
    return ChatService(snapshot,retriever,provider)
