#FROM nicolargo/glances
#COPY glances.conf /glances/conf/glances.conf
#FROM python:3.8
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./main.py /code/main.py
#RUN python -m glances -C /glances/conf/glances.conf -w --disable-webui
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]