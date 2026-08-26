FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
WORKDIR /workspace
COPY packages/contracts /workspace/packages/contracts
COPY backend /workspace/backend
WORKDIR /workspace/backend
RUN uv pip install --system -e ../packages/contracts -e .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
