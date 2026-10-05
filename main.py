import os
import requests
from fastapi import FastAPI, Query, Request, Response
from Crypto.Cipher import AES
import base64

app = FastAPI()

CORP_ID = os.getenv("CORP_ID")
AGENT_ID = os.getenv("AGENT_ID")
SECRET = os.getenv("SECRET")
TOKEN = os.getenv("TOKEN")
ENCODING_AES_KEY = os.getenv("ENCODING_AES_KEY")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")

def decrypt_msg(echo_str):
    key = base64.b64decode(ENCODING_AES_KEY + "=")
    cipher = AES.new(key, AES.MODE_CBC, key[:16])
    decrypted = cipher.decrypt(base64.b64decode(echo_str))
    pad = decrypted[-1]
    content = decrypted[20:-pad]
    xml_len = int.from_bytes(content[:4], byteorder='big')
    return content[4:4+xml_len].decode('utf-8')

@app.get("/wecom")
async def verify(msg_signature: str = Query(...), timestamp: str = Query(...), nonce: str = Query(...), echostr: str = Query(...)):
    try:
        reply = decrypt_msg(echostr)
        return Response(content=reply, media_type="text/plain")
    except Exception as e:
        return Response(content=str(e), status_code=400)

@app.post("/wecom")
async def receive(request: Request):
    return Response(content="success", media_type="text/plain")
