import os
import base64
import hashlib
import xml.etree.ElementTree as ET
import requests
from fastapi import FastAPI, Query, Request, Response
from Crypto.Cipher import AES

app = FastAPI()

CORP_ID = os.getenv("CORP_ID", "")
AGENT_ID = os.getenv("AGENT_ID", "")
SECRET = os.getenv("SECRET", "")
TOKEN = os.getenv("TOKEN", "")
ENCODING_AES_KEY = os.getenv("ENCODING_AES_KEY", "")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")

def verify_signature(msg_signature, timestamp, nonce, echostr):
    sort_list = sorted([TOKEN, timestamp, nonce, echostr])
    sort_str = "".join(sort_list)
    sha1 = hashlib.sha1()
    sha1.update(sort_str.encode('utf-8'))
    return sha1.hexdigest() == msg_signature

def decrypt_msg(echostr):
    key = base64.b64decode(ENCODING_AES_KEY + "=")
    cipher = AES.new(key, AES.MODE_CBC, key[:16])
    decrypted = cipher.decrypt(base64.b64decode(echostr))
    pad = decrypted[-1]
    content = decrypted[20:-pad]
    xml_len = int.from_bytes(content[:4], byteorder='big')
    return content[4:4+xml_len].decode('utf-8')

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
        "agentid": int(AGENT_ID) if AGENT_ID.isdigit() else AGENT_ID,
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
    try:
        if verify_signature(msg_signature, timestamp, nonce, echostr):
            reply = decrypt_msg(echostr)
            return Response(content=reply, media_type="text/plain")
        return Response(content="Invalid signature", status_code=400)
    except Exception as e:
        return Response(content=str(e), status_code=400)

@app.post("/wecom")
async def receive(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    try:
        body = await request.body()
        xml_root = ET.fromstring(body.decode('utf-8'))
        encrypt_node = xml_root.find("Encrypt")
        
        if encrypt_node is not None:
            xml_str = decrypt_msg(encrypt_node.text)
            inner_root = ET.fromstring(xml_str)
            from_user = inner_root.find("FromUserName").text
            msg_type = inner_root.find("MsgType").text
            
            if msg_type == "text":
                content = inner_root.find("Content").text
                
                # Pošiljanje v Dify
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
                answer = dify_res.get("answer", "Napaka pri obdelavi odgovora.")
                
                send_wecom_message(from_user, answer)
                
        return Response(content="success", media_type="text/plain")
    except Exception:
        return Response(content="success", media_type="text/plain")
