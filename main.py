import os
import re
import requests
import cascadio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI(title="CAD STEP-to-GLB Conversion Service")

# 1. Cho phép Web App Google Apps Script gọi API (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Khởi tạo thư mục Cache cục bộ tương thích Windows
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def extract_drive_id(raw_input: str) -> str:
    """Bóc tách File ID từ URL Google Drive hoặc chuỗi thô."""
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", raw_input)
    if match:
        return match.group(1)
    match_id = re.search(r"id=([a-zA-Z0-9_-]+)", raw_input)
    if match_id:
        return match_id.group(1)
    return raw_input.strip()

def download_drive_file(file_id: str, dest_path: str):
    """Tải file dung lượng lớn (>50MB) từ Google Drive, tự vượt cảnh báo dung lượng."""
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
            detail="Không thể tải file từ Google Drive. Đảm bảo file đã bật chia sẻ 'Bất kỳ ai có liên kết'."
        )

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)

@app.get("/convert")
def convert_step_to_glb(file_id: str = Query(..., description="Google Drive File ID hoặc Link")):
    real_id = extract_drive_id(file_id)
    step_path = os.path.join(CACHE_DIR, f"{real_id}.step")
    glb_path = os.path.join(CACHE_DIR, f"{real_id}.glb")

    # Trả kết quả ngay nếu file đã được chuyển đổi trước đó (Cache)
    if os.path.exists(glb_path):
        return FileResponse(glb_path, media_type="model/gltf-binary", filename=f"{real_id}.glb")

    # 1. Tải file .STEP từ Google Drive về máy
    try:
        download_drive_file(real_id, step_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải file: {str(e)}")

    # 2. Chuyển đổi trực tiếp .STEP sang .GLB (Tự động nhận diện cú pháp cascadio)
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
            raise AttributeError("Không tìm thấy hàm xuất GLB trong thư viện cascadio")

        # Xóa file .STEP thô để giải phóng bộ nhớ đĩa
        if os.path.exists(step_path):
            os.remove(step_path)

        return FileResponse(glb_path, media_type="model/gltf-binary", filename=f"{real_id}.glb")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển đổi CAD sang GLB: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CAD Step Converter"}