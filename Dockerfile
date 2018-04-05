FROM python:3.6.4-stretch
ADD . /code
WORKDIR /code
#ENV TZ America/Los_Angeles
RUN pip install -r requirements.txt
CMD ["python", "app.py"]