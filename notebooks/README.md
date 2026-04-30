# Notebooks

Jupyter notebook สำหรับ iterate logic ของ worker ตอน dev — ปรับ threshold + visualize ผลทันทีโดยไม่ต้อง restart Celery.

## Setup

จาก repo root:

```bash
uv sync --all-packages           # ติดตั้ง jupyterlab + matplotlib + ipykernel
uv run jupyter lab               # เปิด UI ที่ http://localhost:8888
```

เปิด `notebooks/process_video.ipynb` แล้ว Run All cells

## Notebooks ที่มี

| File | ทำอะไร |
|---|---|
| `process_video.ipynb` | เรียก pipeline ของ worker (`worker_app.pipeline.*`) ตรงๆ — audio onset → pose verify → dedupe → cut clip. Visualize waveform + onsets + pose landmarks. ใช้ทดสอบ video ใหม่ก่อนปล่อย production |

## เพิ่ม notebook ใหม่

import จาก `worker_app.pipeline.*` ได้เลยเพราะ `golf-worker` เป็น uv workspace member ที่ติดตั้ง editable. ไม่ต้อง mock Mongo/Redis/R2 ถ้าใช้แค่ pipeline classes — มัน pure-CV/audio code

ถ้าต้อง class ที่ touch infra (`MongoSessionRepository`, `R2Storage`, ...) ใช้ in-memory fakes จาก `apps/api/tests/fakes/` แทน
