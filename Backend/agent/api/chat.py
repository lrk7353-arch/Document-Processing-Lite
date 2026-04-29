from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio
from sqlalchemy.orm import Session
from agent.db.session import get_db
from agent.utils.sse import sse_manager
from agent.models.agui import AGUIEvent

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ChatSendReq(BaseModel):
    sessionId: str | None = None
    userText: str

@router.post("/send")
async def chat_send(body: ChatSendReq, db: Session = Depends(get_db)):
    session_id = body.sessionId or f"chat-{asyncio.get_event_loop().time()}"
    await sse_manager.create_queue(session_id)
    async def run_flow():
        step1 = AGUIEvent(type="system", data={"step":"receive","status":"running","message":"接收用户输入"})
        await sse_manager.send_event(session_id, step1)
        await asyncio.sleep(0.3)
        step2 = AGUIEvent(type="system", data={"step":"reasoning","status":"running","message":"分析语义意图"})
        await sse_manager.send_event(session_id, step2)
        await asyncio.sleep(0.3)
        step3 = AGUIEvent(type="system", data={"step":"generate","status":"success","message":"生成回复"})
        await sse_manager.send_event(session_id, step3)
        final = AGUIEvent(type="system", data={"final":True,"answer":f"已收到：{body.userText}"})
        await sse_manager.send_event(session_id, final)
    asyncio.create_task(run_flow())
    return JSONResponse(status_code=200, content={"code":0, "sessionId": session_id})

@router.get("/history")
async def chat_history(sessionId: str):
    return JSONResponse(status_code=200, content={"code":0, "sessionId": sessionId, "messages": []})