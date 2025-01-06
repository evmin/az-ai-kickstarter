import logging
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from orchestrator import SemanticOrchestrator
from util import load_dotenv_from_azd

load_dotenv_from_azd()

orchestrator = SemanticOrchestrator()

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:   %(name)s - %(message)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()

@app.get("/echo")
async def http_trigger(request_body: dict = Body(...)):
    logger.info('API request received with body %s', request_body)

    return JSONResponse(
        content=request_body,
        status_code=200
    )
    
@app.post("/blog")
async def http_blog(request_body: dict = Body(...)):
    logger.info('API request received with body %s', request_body)
    
    topic = request_body.get('topic', 'Tesla')
    content = f"Write a blog post about {topic}."
    
    conversation_messages = []
    conversation_messages.append({'role': 'user', 'name': 'user', 'content': content})
    
    reply = await orchestrator.process_conversation(conversation_messages)
    
    conversation_messages.append(reply)

    return JSONResponse(
        content=reply,
        status_code=200
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")