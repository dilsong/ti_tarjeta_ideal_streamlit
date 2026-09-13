FROM python:3.11-slim-bookworm
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render inyecta RENDER_GIT_COMMIT en el build; lo grabamos para la UI del PIN.
ARG RENDER_GIT_COMMIT=
RUN if [ -n "$RENDER_GIT_COMMIT" ]; then \
      echo -n "$RENDER_GIT_COMMIT" | cut -c1-7 > app/build_id.txt; \
    elif [ -d .git ]; then \
      git rev-parse --short=7 HEAD > app/build_id.txt 2>/dev/null || echo -n unknown > app/build_id.txt; \
    else \
      echo -n unknown > app/build_id.txt; \
    fi

ENV PORT=10000
ENV TI_BUILD_ID_FILE=app/build_id.txt
EXPOSE 10000
CMD streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false
