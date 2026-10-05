import os
import base64
import hashlib
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from fastapi import FastAPI, Query, Request, Response
from Crypto.Cipher import AES

app = FastAPI()

CORP_ID = os.getenv("CORP_ID", "").strip()
AGENT_ID = os.getenv("AGENT_ID", "").strip()
SECRET = os.getenv("SECRET", "").strip()
TOKEN = os.getenv("TOKEN", "").strip()
ENCODING_AES_KEY = os.getenv("ENCODING_AES_KEY", "").strip()
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "").strip()

def decrypt_data(encrypt_b64):
    try:
        raw_b64 = urllib.parse.unquote(encrypt_b64)
        key = base64.b64decode(ENCODING_AES_KEY + "=")
        iv = key[:16]
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(base64.b64decode(raw_b64))
        
        pad = decrypted[-1]
        if pad < 1 or pad > 32:
            pad = 0
        decrypted = decrypted[:-pad] if pad else decrypted
        
        content = decrypted[16:]
        msg_len = int.from_bytes(content[:4], byteorder='big')
        
        msg_bytes = content[4:4+msg_len]
        return msg_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Decrypt Error: {e}")
        return None

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
    msg_signature: str = Query(None),
    timestamp: str = Query(None),
    nonce: str = Query(None),
    echostr: str = Query(...)
):
    reply = decrypt_data(echostr)
    if reply:
        return Response(content=reply, media_type="text/plain")
    return Response(content="Verification failed", status_code=400)

@app.post("/wecom")
async def receive(request: Request):
    try:
        body = await request.body()
        xml_root = ET.fromstring(body.decode('utf-8'))
        encrypt_node = xml_root.find("Encrypt")
        
        if encrypt_node is not None:
            xml_str = decrypt_data(encrypt_node.text)
            if xml_str:
                inner_root = ET.fromstring(xml_str)
                from_user = inner_root.find("FromUserName").text
                msg_type = inner_root.find("MsgType").text
                
                if msg_type == "text":
                    content = inner_root.find("Content").text
                    
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
                    answer = dify_res.get("answer", "Prišlo je do napake pri obdelavi v Dify-ju.")
                    
                    # Pošiljanje odgovora nazaj v WeCom klepet
                    send_wecom_message(from_user, answer)
                    
        return Response(content="success", media_type="text/plain")
    except Exception as e:
        print(f"Receive Error: {e}")
        return Response(content="success", media_type="text/plain")
