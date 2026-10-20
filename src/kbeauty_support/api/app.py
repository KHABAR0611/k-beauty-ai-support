"""Bounded, single-worker RAG API; dependency failures never become successful answers."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hmac
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .models import ChatRequest, ChatResponse
from .runtime import Settings, build_service
from kbeauty_support.generation.control import OutcomeMetrics

LOG=logging.getLogger("kbeauty.api")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    handler=logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(handler)
LOG.propagate=False


def error_body(request_id: str, code: str) -> dict:
    return ChatResponse(answer="Запрос не может быть обработан безопасно.",sources=[],status="system_error",
                        grounding_status="error",request_id=request_id,latency_ms={},error_code=code).model_dump()


class RateLimiter:
    def __init__(self, limit: int, *, clock=time.monotonic, max_clients: int = 1024):
        self.limit,self.clock,self.max_clients=limit,clock,max_clients
        self.clients=OrderedDict()

    def allow(self, key: str) -> bool:
        now=self.clock()
        while self.clients and next(iter(self.clients.values()))[0]<=now-60:
            self.clients.popitem(last=False)
        if key not in self.clients:
            if len(self.clients)>=self.max_clients:
                return False
            self.clients[key]=(now,0)
        start,n=self.clients[key]
        if n>=self.limit:
            return False
        self.clients[key]=(start,n+1)
        return True


class BoundaryMiddleware:
    def __init__(self, app, *, settings: Settings, owner):
        self.app,self.settings,self.owner=app,settings,owner
        self.limiter=RateLimiter(settings.rate_limit)

    async def __call__(self, scope, receive, send):
        if scope["type"]!="http":
            return await self.app(scope,receive,send)
        rid=str(uuid4());scope.setdefault("state",{})["request_id"]=rid
        headers=dict(scope.get("headers",[]))
        started=time.perf_counter()
        recorded=False
        async def reply(code,status):
            nonlocal recorded
            await JSONResponse(error_body(rid,code),status_code=status)(scope,receive,wrapped_send)
        async def wrapped_send(message):
            nonlocal recorded
            if message["type"]=="http.response.start":
                message["headers"]=list(message.get("headers",[]))+[(b"x-request-id",rid.encode())]
                # Deliberately no URL, query, body, auth headers, exception text or client address.
                LOG.info(json.dumps({"event":"http_response","request_id":rid,"http_status":message["status"],
                                     "latency_ms":round((time.perf_counter()-started)*1000,3)}))
            if message["type"]=="http.response.body" and scope.get("path")=="/chat" and not recorded:
                try:
                    category=json.loads(message.get("body",b""))["status"]
                    self.owner.state.outcomes.record(category)
                    recorded=True
                except (ValueError,KeyError,TypeError):
                    pass
            await send(message)
        if scope.get("path") in ("/chat","/metrics"):
            token=headers.get(b"authorization",b"").decode("latin1")
            if not self.settings.api_key:
                return await reply("api_key_not_configured",503)
            if not hmac.compare_digest(token.encode("latin1"),("Bearer "+self.settings.api_key).encode("utf8")):
                return await reply("unauthorized",401)
            # One configured bearer credential: a global per-process budget cannot be evaded with X-Forwarded-For.
            if not self.limiter.allow("authenticated-api-key"):
                return await reply("rate_limit_exceeded",429)
            try:
                declared=int(headers.get(b"content-length",b"0"))
                if declared<0 or declared>self.settings.body_limit:
                    return await reply("request_too_large",413)
            except ValueError:
                return await reply("invalid_content_length",400)
            raw=bytearray()
            body_deadline=time.monotonic()+5
            while True:
                try:
                    message=await asyncio.wait_for(receive(),timeout=max(0.001,body_deadline-time.monotonic()))
                except TimeoutError:
                    return await reply("request_body_timeout",408)
                if message["type"]=="http.disconnect":
                    return
                raw.extend(message.get("body",b""))
                if len(raw)>self.settings.body_limit:
                    return await reply("request_too_large",413)
                if not message.get("more_body",False):
                    break
            delivered=False
            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered=True
                    return {"type":"http.request","body":bytes(raw),"more_body":False}
                return await receive()
            return await self.app(scope,bounded_receive,wrapped_send)
        return await self.app(scope,receive,wrapped_send)


def create_app(service=None, settings: Settings | None = None) -> FastAPI:
    settings=settings or Settings.environment()
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="rag-worker")
    @asynccontextmanager
    async def lifespan(app):
        app.state.service=service
        app.state.busy=asyncio.Semaphore(1)
        initialization=None
        if app.state.service is None:
            async def initialize():
                try:
                    app.state.service=await asyncio.get_running_loop().run_in_executor(executor,build_service,settings)
                except Exception as exc:
                    LOG.error(json.dumps({"event":"startup_dependency_error","category":type(exc).__name__}))
            initialization=asyncio.create_task(initialize())
        yield
        if initialization:
            await initialization
        executor.shutdown(wait=True,cancel_futures=True)
        current=app.state.service
        if current and hasattr(current.retriever,"close"):
            current.retriever.close()
    app=FastAPI(title="K-Beauty AI Support",version="0.7.0",lifespan=lifespan)
    app.state.service=service
    app.state.outcomes=service if service is not None else OutcomeMetrics()
    app.add_middleware(BoundaryMiddleware,settings=settings,owner=app)
    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(error_body(request.state.request_id,"invalid_request"),status_code=422)
    @app.get("/health")
    async def health(request: Request):
        return {"status":"ok","request_id":request.state.request_id}
    @app.get("/ready")
    async def ready(request: Request):
        current=app.state.service
        if current is None:
            return JSONResponse({"ready":False,"code":"startup_dependencies_unavailable","request_id":request.state.request_id},status_code=503)
        try:
            state=await asyncio.wait_for(asyncio.to_thread(current.ready),timeout=8)
        except Exception:
            state={"ready":False,"code":"dependency_probe_failed"}
        state["ready"]=bool(state["ready"] and settings.api_key)
        state.setdefault("dependencies",{})["api_access"]={"ready":bool(settings.api_key)}
        return JSONResponse({**state,"request_id":request.state.request_id},status_code=200 if state["ready"] else 503)
    @app.get("/metrics")
    async def metrics():
        return app.state.outcomes.metrics()
    @app.post("/chat",response_model=ChatResponse)
    async def chat(request: Request, payload: ChatRequest):
        current=app.state.service
        if current is None:
            return JSONResponse(error_body(request.state.request_id,"startup_dependencies_unavailable"),status_code=503)
        try:
            await asyncio.wait_for(app.state.busy.acquire(),timeout=0.05)
        except TimeoutError:
            return JSONResponse(error_body(request.state.request_id,"service_busy"),status_code=503)
        future=asyncio.get_running_loop().run_in_executor(executor,current.chat,payload,request.state.request_id)
        # A timed-out native inference still owns the slot until it really finishes.
        def completed(finished):
            app.state.busy.release()
            if not finished.cancelled():
                finished.exception()  # Consume late failures without logging vendor exception contents.
        future.add_done_callback(completed)
        try:
            status,response=await asyncio.wait_for(asyncio.shield(future),timeout=settings.request_timeout)
            return JSONResponse(response.model_dump(),status_code=status)
        except TimeoutError:
            return JSONResponse(error_body(request.state.request_id,"request_deadline_exceeded"),status_code=504)
        except Exception:
            return JSONResponse(error_body(request.state.request_id,"service_execution_failed"),status_code=503)
    return app


app=create_app()
