import os
import re
import requests
import cascadio
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="CAD STEP-to-GLB Conversion Service")

# 1. BẬT CORS CHUẨN (TƯƠNG THÍCH HOÀN TOÀN VỚI IFRAME GOOGLE APPS SCRIPT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Đảm bảo mọi lỗi hệ thống (500, 400) đều trả kèm header CORS
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"}
    )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def extract_drive_id(raw_input: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", raw_input)
    if match:
        return match.group(1)
    match_id = re.search(r"id=([a-zA-Z0-9_-]+)", raw_input)
    if match_id:
        return match_id.group(1)
    return raw_input.strip()

def download_drive_file(file_id: str, dest_path: str):
    session = requests.Session()
    url = "https://docs.google.com/uc?export=download"
    response = session.get(url, params={'id': file_id}, stream=True)

    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            response = session.get(url, params={'id': file_id, 'confirm': value}, stream=True)
            break

    if response.status_code != 200:
        raise HTTPException(
            status_code=400, 
            detail="Không thể tải file từ Google Drive. Vui lòng kiểm tra quyền chia sẻ 'Bất kỳ ai có liên kết'."
        )

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)

@app.get("/convert")
def convert_step_to_glb(file_id: str = Query(..., description="Google Drive File ID")):
    real_id = extract_drive_id(file_id)
    step_path = os.path.join(CACHE_DIR, f"{real_id}.step")
    glb_path = os.path.join(CACHE_DIR, f"{real_id}.glb")

    if os.path.exists(glb_path):
        return FileResponse(glb_path, media_type="model/gltf-binary", filename=f"{real_id}.glb")

    # 1. Tải file từ Drive
    download_drive_file(real_id, step_path)

    # 2. Chuyển đổi CAD sang GLB
    try:
        if hasattr(cascadio, "step_to_glb"):
            try:
                cascadio.step_to_glb(step_path, glb_path, 0.1, 0.5)
            except TypeError:
                cascadio.step_to_glb(step_path, glb_path)
        elif hasattr(cascadio, "to_glb"):
            with open(step_path, "rb") as f_in:
                glb_data = cascadio.to_glb(f_in.read())
            with open(glb_path, "wb") as f_out:
                f_out.write(glb_data)
        else:
            raise AttributeError("Không tìm thấy hàm chuyển đổi GLB trong cascadio")

        if os.path.exists(step_path):
            os.remove(step_path)

        return FileResponse(glb_path, media_type="model/gltf-binary", filename=f"{real_id}.glb")
    except Exception as e:
        if os.path.exists(step_path):
            os.remove(step_path)
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển đổi CAD: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CAD Step Converter"}
