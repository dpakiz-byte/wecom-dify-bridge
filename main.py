import os
import xml.etree.ElementTree as ET
import requests
from fastapi import FastAPI, Query, Request, Response
from WXBizMsgCrypt import WXBizMsgCrypt

app = FastAPI()

CORP_ID = os.getenv("CORP_ID")
AGENT_ID = os.getenv("AGENT_ID")
SECRET = os.getenv("SECRET")
TOKEN = os.getenv("TOKEN")
ENCODING_AES_KEY = os.getenv("ENCODING_AES_KEY")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")

wxcpt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, CORP_ID)

def get_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={SECRET}"
    res = requests.get(url).json()
    return res.get("access_token")

def send_wecom_message(to_user, content):
    access_token = get_access_token()
    if not access_token:
        return
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
    data = {
        "touser": to_user,
        "msgtype": "text",
        "agentid": int(AGENT_ID),
        "text": {"content": content}
    }
    requests.post(url, json=data)

@app.get("/wecom")
async def verify(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    ret, sEchoStr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
    if ret == 0:
        return Response(content=sEchoStr.decode('utf-8'), media_type="text/plain")
    return Response(content="Verification failed", status_code=400)

@app.post("/wecom")
async def receive(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    try:
        body = await request.body()
        ret, xml_str = wxcpt.DecryptMsg(body.decode('utf-8'), msg_signature, timestamp, nonce)
        if ret != 0:
            return Response(content="Decrypt error", status_code=400)
            
        root = ET.fromstring(xml_str)
        from_user = root.find("FromUserName").text
        msg_type = root.find("MsgType").text
        
        if msg_type == "text":
            content = root.find("Content").text
            
            # Pošiljanje v Dify API
            dify_url = "https://api.dify.ai/v1/chat-messages"
            headers = {
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json"
            }
            dify_data = {
                "inputs": {},
                "query": content,
                "response_mode": "blocking",
                "user": from_user
            }
            
            dify_res = requests.post(dify_url, json=dify_data, headers=headers).json()
            answer = dify_res.get("answer", "Prišlo je do napake pri obdelavi.")
            
            send_wecom_message(from_user, answer)
            
        return Response(content="success", media_type="text/plain")
    except Exception:
        return Response(content="success", media_type="text/plain")
