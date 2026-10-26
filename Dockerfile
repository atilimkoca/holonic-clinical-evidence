FROM python:3.11-slim

WORKDIR /app

COPY project_1_crawling/requirements.txt /tmp/requirements-p1.txt
COPY project_2_semantic/requirements.txt /tmp/requirements-p2.txt
COPY project_3_llm/requirements.txt /tmp/requirements-p3.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
       -r /tmp/requirements-p1.txt \
       -r /tmp/requirements-p2.txt \
       -r /tmp/requirements-p3.txt

COPY . /app

CMD ["python", "integration/src/end_to_end_pipeline.py", "--sample-size", "20"]

