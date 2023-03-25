#FROM nicolargo/glances
#COPY glances.conf /glances/conf/glances.conf
#FROM python:3.8
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9
WORKDIR /code
RUN apt-get update && apt-get install -y jq
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./main.py /code/main.py
COPY ./utils.py /code/utils.py
RUN mkdir -p /tmp/mocked-outputs/df-outputs
RUN mkdir -p /tmp/fstab-contents/
RUN mkdir -p /tmp/nvme-outputs
RUN mv /etc/fstab /etc/fstab_bak
COPY test/mocked-outputs/fstab /tmp/fstab-contents/
COPY test/mocked-outputs/fstab /etc/
COPY test/mocked-outputs/lsblk-output.json /tmp/mocked-outputs/
COPY test/mocked-outputs/nvme_outputs/* /tmp/nvme-outputs/
COPY test/mocked-outputs/df-outputs/* /tmp/mocked-outputs/df-outputs/
COPY test/bin/* /usr/local/bin/
COPY bin/* /usr/local/bin/
#RUN /usr/local/bin/replace-files

#RUN python -m glances -C /glances/conf/glances.conf -w --disable-webui
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]